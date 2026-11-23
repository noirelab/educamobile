"""Alertas (reconhecer e resolver), emergência, limites das regras e notificações."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app import alertas, auditoria, notificacoes, tempo_real
from app.cadastros import Db, Deslocamento, IdRota, Limite
from app.models import (
    Alerta,
    Configuracao,
    Dispositivo,
    Notificacao,
    Perfil,
    Severidade,
    StatusViagem,
    Usuario,
    Veiculo,
)
from app.routers.viagens import Equipe, Gestao, _viagem
from app.schemas.viagens import (
    AlertaLer,
    ConfiguracaoAtualizar,
    ConfiguracaoLer,
    DispositivoCriar,
    Emergencia,
    EmergenciaResultado,
    NotificacaoLer,
)
from app.security import UsuarioAtual, exigir_perfil
from app.viagens import agora, alertar

router = APIRouter(tags=["alertas"])
SoAdmin = Annotated[Usuario, exigir_perfil(Perfil.ADMIN)]
MAX_DISPOSITIVOS_POR_USUARIO = 10


# Alertas


@router.get("/alertas")
def listar(
    db: Db,
    _: Gestao,
    abertos: bool = True,
    tipo: str | None = None,
    severidade: Severidade | None = None,
    viagem_id: int | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[AlertaLer]:
    """Por padrão, os que ainda não foram resolvidos (abertos e reconhecidos)."""
    consulta = (
        select(Alerta)
        .order_by(Alerta.criado_em.desc(), Alerta.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if abertos:
        consulta = consulta.where(Alerta.resolvido_em.is_(None))
    if tipo:
        consulta = consulta.where(Alerta.tipo == tipo)
    if severidade:
        consulta = consulta.where(Alerta.severidade == severidade)
    if viagem_id:
        consulta = consulta.where(Alerta.viagem_id == viagem_id)
    return [AlertaLer.model_validate(a) for a in db.scalars(consulta)]


def _alerta(db: Db, alerta_id: int) -> Alerta:
    alerta = db.get(Alerta, alerta_id, with_for_update=True)
    if alerta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta não encontrado")
    return alerta


@router.post("/alertas/{alerta_id}/reconhecer")
def reconhecer(alerta_id: IdRota, request: Request, db: Db, gestor: Gestao) -> AlertaLer:
    alerta = _alerta(db, alerta_id)
    if alerta.resolvido_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O alerta já foi resolvido")
    if alerta.reconhecido_em is None:
        alerta.reconhecido_em = agora()
        alerta.reconhecido_por_id = gestor.id
        auditoria.registrar(
            db,
            "alerta.reconhecer",
            request=request,
            usuario=gestor,
            recurso="alerta",
            recurso_id=alerta.id,
        )
        db.commit()
    return AlertaLer.model_validate(alerta)


@router.post("/alertas/{alerta_id}/resolver")
def resolver(alerta_id: IdRota, request: Request, db: Db, gestor: Gestao) -> AlertaLer:
    alerta = _alerta(db, alerta_id)
    if alerta.resolvido_em is None:
        alerta.resolvido_em = agora()
        alerta.resolvido_por_id = gestor.id
        alerta.reconhecido_em = alerta.reconhecido_em or alerta.resolvido_em
        alerta.reconhecido_por_id = alerta.reconhecido_por_id or gestor.id
        auditoria.registrar(
            db,
            "alerta.resolver",
            request=request,
            usuario=gestor,
            recurso="alerta",
            recurso_id=alerta.id,
        )
        db.commit()
    return AlertaLer.model_validate(alerta)


# Limites das regras


@router.get("/configuracao/alertas")
def ler_configuracao(db: Db, _: Gestao) -> list[ConfiguracaoLer]:
    return [
        ConfiguracaoLer(chave=c.chave, valor=c.valor, descricao=c.descricao)
        for c in db.scalars(select(Configuracao).order_by(Configuracao.chave))
    ]


@router.put("/configuracao/alertas")
def atualizar_configuracao(
    dados: ConfiguracaoAtualizar, request: Request, db: Db, admin: SoAdmin
) -> list[ConfiguracaoLer]:
    existentes = {c.chave: c for c in db.scalars(select(Configuracao))}
    desconhecidas = sorted(set(dados.valores) - set(existentes))
    if desconhecidas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Chaves desconhecidas: {desconhecidas}"
        )
    if any(v < 0 for v in dados.valores.values()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Os limites não podem ser negativos"
        )
    for chave, valor in dados.valores.items():
        existentes[chave].valor = valor
    auditoria.registrar(
        db, "configuracao.atualizar", request=request, usuario=admin, chaves=sorted(dados.valores)
    )
    db.commit()
    return ler_configuracao(db, admin)


# Emergência (R11)


@router.post("/viagens/{viagem_id}/emergencia", status_code=status.HTTP_202_ACCEPTED)
def emergencia(
    viagem_id: IdRota, dados: Emergencia, request: Request, db: Db, usuario: Equipe
) -> EmergenciaResultado:
    """Motorista ou monitor aciona. Cria o alerta crítico e as notificações e responde na hora:
    o envio do push fica com o worker, acordado logo depois do commit."""
    viagem = _viagem(db, viagem_id, usuario, travar=True)
    if viagem.status != StatusViagem.EM_ANDAMENTO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só há emergência com a viagem em andamento")
    existente = db.scalar(
        select(Alerta).where(
            Alerta.viagem_id == viagem.id,
            Alerta.tipo == "emergencia",
            Alerta.resolvido_em.is_(None),
        )
    )
    if existente is not None:
        # Toque duplo no botão: não abre outra emergência nem reenvia o push.
        return EmergenciaResultado(
            alerta_id=existente.id, gestores_avisados=0, responsaveis_avisados=0
        )
    try:
        posicao = tempo_real.ler_posicao(viagem.id)
    except Exception:
        posicao = None
    placa = db.scalar(select(Veiculo.placa).where(Veiculo.id == viagem.veiculo_id))
    contexto = {"acionada_por": usuario.id, "observacao": dados.observacao}
    if posicao:
        contexto |= {
            "latitude": posicao["latitude"],
            "longitude": posicao["longitude"],
            "posicao_registrada_em": posicao["registrada_em"],
        }
    mensagem = f"Emergência no ônibus {placa or viagem.id} acionada por {usuario.nome}"
    alerta = alertar(db, viagem, "emergencia", Severidade.CRITICO, mensagem)
    alerta.dados = contexto
    db.flush()
    gestores = notificacoes.para_gestores(
        db, "emergencia", "EMERGÊNCIA no ônibus", mensagem, viagem_id=viagem.id
    )
    avisados = 0
    if alertas.limites(db)["emergencia_avisa_responsaveis"] >= 1:
        avisados = _avisar_responsaveis(db, viagem.id)
    auditoria.registrar(
        db,
        "emergencia.acionar",
        request=request,
        usuario=usuario,
        recurso="viagem",
        recurso_id=viagem.id,
        alerta_id=alerta.id,
    )
    db.commit()
    return EmergenciaResultado(
        alerta_id=alerta.id, gestores_avisados=gestores, responsaveis_avisados=avisados
    )


def _avisar_responsaveis(db: Db, viagem_id: int) -> int:
    from app.models import ViagemAluno

    total = 0
    for estudante_id in db.scalars(
        select(ViagemAluno.estudante_id).where(ViagemAluno.viagem_id == viagem_id)
    ):
        total += notificacoes.para_responsaveis(
            db,
            estudante_id,
            "ocorrencia",
            "Ocorrência com o ônibus",
            "Houve uma ocorrência com o ônibus e a gestão do transporte já foi acionada. "
            "Você será avisado assim que houver novidades.",
            viagem_id=viagem_id,
        )
    return total


# Dispositivos e notificações


@router.post("/dispositivos", status_code=status.HTTP_204_NO_CONTENT)
def registrar_dispositivo(
    dados: DispositivoCriar, request: Request, db: Db, usuario: UsuarioAtual
) -> None:
    """Registra o token de push do aparelho. O mesmo token passa a valer para quem o enviou por
    último (um aparelho que troca de dono não recebe o que é do dono antigo)."""
    atual = db.scalar(select(Dispositivo).where(Dispositivo.token == dados.token))
    if atual is not None:
        atual.usuario_id = usuario.id
        atual.plataforma = dados.plataforma
    else:
        total = len(
            db.scalars(select(Dispositivo.id).where(Dispositivo.usuario_id == usuario.id)).all()
        )
        if total >= MAX_DISPOSITIVOS_POR_USUARIO:
            # Os mais antigos saem: o limite impede encher a tabela com tokens inventados.
            antigos = db.scalars(
                select(Dispositivo.id)
                .where(Dispositivo.usuario_id == usuario.id)
                .order_by(Dispositivo.id)
                .limit(total - MAX_DISPOSITIVOS_POR_USUARIO + 1)
            ).all()
            db.execute(delete(Dispositivo).where(Dispositivo.id.in_(antigos)))
        db.add(Dispositivo(usuario_id=usuario.id, token=dados.token, plataforma=dados.plataforma))
    auditoria.registrar(db, "dispositivo.registrar", request=request, usuario=usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # corrida com o mesmo token: o outro pedido já o gravou


@router.delete("/dispositivos", status_code=status.HTTP_204_NO_CONTENT)
def remover_dispositivo(dados: DispositivoCriar, db: Db, usuario: UsuarioAtual) -> None:
    """Chamado no logout do app: aquele aparelho deixa de receber push desta conta."""
    db.execute(
        delete(Dispositivo).where(
            Dispositivo.token == dados.token, Dispositivo.usuario_id == usuario.id
        )
    )
    db.commit()


@router.get("/notificacoes")
def minhas_notificacoes(
    db: Db,
    usuario: UsuarioAtual,
    nao_lidas: bool = False,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[NotificacaoLer]:
    consulta = (
        select(Notificacao)
        .where(Notificacao.usuario_id == usuario.id)
        .order_by(Notificacao.criado_em.desc(), Notificacao.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if nao_lidas:
        consulta = consulta.where(Notificacao.lido_em.is_(None))
    return [NotificacaoLer.model_validate(n) for n in db.scalars(consulta)]


@router.post("/notificacoes/{notificacao_id}/lida", status_code=status.HTTP_204_NO_CONTENT)
def marcar_lida(notificacao_id: IdRota, db: Db, usuario: UsuarioAtual) -> None:
    n = db.get(Notificacao, notificacao_id)
    # Notificação de outra pessoa é igual a inexistente.
    if n is None or n.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificação não encontrada")
    if n.lido_em is None:
        n.lido_em = agora()
        db.commit()
