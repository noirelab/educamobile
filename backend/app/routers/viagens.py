"""Viagem do dia: geração, escala, início, lista, eventos, conclusão e cancelamento.

Quem opera a viagem (motorista e monitor escalados) só alcança a própria, e só no dia. A gestão
alcança todas. Quem não tem acesso recebe 404, igual a uma viagem que não existe.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app import auditoria, fotos, viagens
from app.cadastros import Db, Deslocamento, IdRota, Limite
from app.models import (
    Alerta,
    Aviso,
    Estudante,
    EventoViagem,
    Motorista,
    Perfil,
    ResponsavelEstudante,
    StatusAluno,
    StatusViagem,
    Usuario,
    Veiculo,
    Viagem,
    ViagemAluno,
    ViagemParada,
)
from app.schemas.viagens import (
    AlertaLer,
    AvisoLer,
    Cancelamento,
    CancelamentoResultado,
    ConclusaoResultado,
    Correcao,
    Escala,
    EventoLer,
    GerarViagens,
    ItemDaLista,
    ListaDaViagem,
    LoteDeEventos,
    ParadaDaViagem,
    ResultadoDoEvento,
    Totais,
    ViagemLer,
)
from app.security import Responsavel, exigir_perfil

router = APIRouter(tags=["viagens"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
Equipe = Annotated[
    Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR, Perfil.MOTORISTA, Perfil.MONITOR)
]
# Eventos feitos offline chegam depois: a equipe ainda pode enviar os do dia anterior.
DIAS_PARA_SINCRONIZAR = 1


def _nao_encontrada() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Viagem não encontrada")


def garantir_escalado(usuario: Usuario, viagem: Viagem, *, tolerancia_dias: int = 0) -> None:
    """Gestão passa. Motorista e monitor, só na própria viagem e no dia (ou na tolerância)."""
    if usuario.perfil in (Perfil.ADMIN, Perfil.GESTOR):
        return
    escalado = (usuario.perfil == Perfil.MOTORISTA and viagem.motorista_id == usuario.id) or (
        usuario.perfil == Perfil.MONITOR and viagem.monitor_id == usuario.id
    )
    hoje = date.today()
    no_dia = hoje - timedelta(days=tolerancia_dias) <= viagem.data <= hoje
    if not (escalado and no_dia):
        raise _nao_encontrada()


def _viagem(db: Db, viagem_id: int, usuario: Usuario, *, tolerancia_dias: int = 0, travar=False):
    viagem = db.get(Viagem, viagem_id, with_for_update=travar)
    if viagem is None:
        raise _nao_encontrada()
    garantir_escalado(usuario, viagem, tolerancia_dias=tolerancia_dias)
    return viagem


def _totais(db: Db, viagem_id: int) -> Totais:
    linhas = db.execute(
        select(ViagemAluno.status, func.count())
        .where(ViagemAluno.viagem_id == viagem_id)
        .group_by(ViagemAluno.status)
    ).all()
    return Totais(**{s.value: n for s, n in linhas})


def _ler(db: Db, viagem: Viagem) -> ViagemLer:
    return ViagemLer.model_validate(viagem).model_copy(update={"totais": _totais(db, viagem.id)})


@router.post("/viagens/gerar", status_code=status.HTTP_201_CREATED)
def gerar(dados: GerarViagens, request: Request, db: Db, gestor: Gestao) -> list[ViagemLer]:
    dia = dados.data or date.today()
    resultado = viagens.gerar(db, dia, dados.rota_id)
    auditoria.registrar(
        db,
        "viagens.gerar",
        request=request,
        usuario=gestor,
        data=dia.isoformat(),
        total=len(resultado),
    )
    db.commit()
    return [_ler(db, v) for v in resultado]


@router.get("/viagens")
def listar(
    db: Db,
    _: Gestao,
    data: date | None = None,
    situacao: StatusViagem | None = None,
    rota_id: int | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[ViagemLer]:
    consulta = select(Viagem).order_by(Viagem.data.desc(), Viagem.id).limit(limit).offset(offset)
    if data is not None:
        consulta = consulta.where(Viagem.data == data)
    if situacao is not None:
        consulta = consulta.where(Viagem.status == situacao)
    if rota_id is not None:
        consulta = consulta.where(Viagem.rota_id == rota_id)
    return [_ler(db, v) for v in db.scalars(consulta)]


@router.get("/motorista/viagens-hoje")
def viagens_de_hoje(
    db: Db, usuario: Annotated[Usuario, exigir_perfil(Perfil.MOTORISTA, Perfil.MONITOR)]
) -> list[ViagemLer]:
    coluna = Viagem.motorista_id if usuario.perfil == Perfil.MOTORISTA else Viagem.monitor_id
    consulta = (
        select(Viagem).where(coluna == usuario.id, Viagem.data == date.today()).order_by(Viagem.id)
    )
    return [_ler(db, v) for v in db.scalars(consulta)]


@router.get("/viagens/{viagem_id}")
def obter(viagem_id: IdRota, db: Db, usuario: Equipe) -> ViagemLer:
    return _ler(db, _viagem(db, viagem_id, usuario))


@router.patch("/viagens/{viagem_id}/escala")
def escalar(
    viagem_id: IdRota, dados: Escala, request: Request, db: Db, gestor: Gestao
) -> ViagemLer:
    viagem = _viagem(db, viagem_id, gestor, travar=True)
    if viagem.status != StatusViagem.AGENDADA:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só viagem agendada muda de escala")
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("monitor_id") is not None:
        monitor = db.get(Usuario, campos["monitor_id"])
        if monitor is None or monitor.perfil != Perfil.MONITOR:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O usuário não é monitor")
    if campos.get("motorista_id") is not None and db.get(Motorista, campos["motorista_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Motorista sem cadastro")
    if campos.get("veiculo_id") is not None and db.get(Veiculo, campos["veiculo_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Veículo inexistente")
    for campo, valor in campos.items():
        setattr(viagem, campo, valor)
    auditoria.registrar(
        db,
        "viagem.escalar",
        request=request,
        usuario=gestor,
        recurso="viagem",
        recurso_id=viagem.id,
    )
    db.commit()
    return _ler(db, viagem)


@router.post("/viagens/{viagem_id}/iniciar")
def iniciar(viagem_id: IdRota, request: Request, db: Db, usuario: Equipe) -> ViagemLer:
    if usuario.perfil == Perfil.MONITOR:
        raise _nao_encontrada()
    viagem = _viagem(db, viagem_id, usuario, travar=True)
    try:
        viagens.iniciar(db, viagem, date.today())
    except HTTPException:
        db.rollback()
        raise
    auditoria.registrar(
        db,
        "viagem.iniciar",
        request=request,
        usuario=usuario,
        recurso="viagem",
        recurso_id=viagem.id,
    )
    db.commit()
    return _ler(db, viagem)


@router.post("/viagens/{viagem_id}/cancelar")
def cancelar(
    viagem_id: IdRota, dados: Cancelamento, request: Request, db: Db, gestor: Gestao
) -> CancelamentoResultado:
    viagem = _viagem(db, viagem_id, gestor, travar=True)
    try:
        avisados = viagens.cancelar(db, viagem, gestor, dados.motivo)
    except HTTPException:
        db.rollback()
        raise
    auditoria.registrar(
        db,
        "viagem.cancelar",
        request=request,
        usuario=gestor,
        recurso="viagem",
        recurso_id=viagem.id,
        motivo=dados.motivo,
    )
    db.commit()
    return CancelamentoResultado(viagem=_ler(db, viagem), responsaveis_avisados=avisados)


@router.get("/viagens/{viagem_id}/lista")
def lista(viagem_id: IdRota, db: Db, usuario: Equipe) -> ListaDaViagem:
    viagem = _viagem(db, viagem_id, usuario)
    paradas = {
        p.parada_id: p
        for p in db.scalars(
            select(ViagemParada)
            .where(ViagemParada.viagem_id == viagem.id)
            .order_by(ViagemParada.ordem)
        )
    }
    linhas = db.execute(
        select(ViagemAluno, Estudante)
        .join(Estudante, Estudante.id == ViagemAluno.estudante_id)
        .where(ViagemAluno.viagem_id == viagem.id)
    ).all()
    itens = []
    for aluno, estudante in linhas:
        parada = paradas.get(aluno.parada_id) if aluno.parada_id is not None else None
        foto_url = None
        if estudante.foto_arquivo:
            token, _ = fotos.assinar(estudante.id)
            foto_url = f"/fotos/{token}"
        itens.append(
            ItemDaLista(
                estudante_id=estudante.id,
                nome=estudante.nome,
                foto_url=foto_url,
                parada_id=aluno.parada_id,
                parada_nome=parada.nome if parada else None,
                ordem=parada.ordem if parada else None,
                status=aluno.status,
                fora_da_lista=aluno.fora_da_lista,
                ausencia_avisada_depois=aluno.ausencia_avisada_em is not None,
                observacoes_cuidado=estudante.observacoes_cuidado,
            )
        )
    itens.sort(key=lambda i: (i.ordem is None, i.ordem or 0, i.nome))
    return ListaDaViagem(
        viagem=_ler(db, viagem),
        paradas=[
            ParadaDaViagem(
                parada_id=p.parada_id,
                ordem=p.ordem,
                nome=p.nome,
                horario_previsto=p.horario_previsto,
                raio_cerca_m=p.raio_cerca_m,
            )
            for p in paradas.values()
        ],
        alunos=itens,
    )


@router.post("/viagens/{viagem_id}/eventos")
def registrar_eventos(
    viagem_id: IdRota, dados: LoteDeEventos, request: Request, db: Db, usuario: Equipe
) -> list[ResultadoDoEvento]:
    """Lote idempotente: reenviar o mesmo id devolve `duplicado` e não muda nada."""
    viagem = _viagem(db, viagem_id, usuario, tolerancia_dias=DIAS_PARA_SINCRONIZAR, travar=True)
    if viagem.status not in (StatusViagem.EM_ANDAMENTO, StatusViagem.CONCLUIDA):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    entradas = [
        viagens.EventoEntrada(
            id=e.id,
            tipo=e.tipo,
            hora_aparelho=e.hora_aparelho,
            estudante_id=e.estudante_id,
            parada_id=e.parada_id,
            localizacao=e.localizacao,
            justificativa=e.justificativa,
        )
        for e in dados.eventos
    ]
    resultados = viagens.aplicar_eventos(db, viagem, usuario, entradas)
    # Evento atrasado pode deixar uma criança a bordo numa viagem já concluída: não passa batido.
    if viagem.status == StatusViagem.CONCLUIDA:
        a_bordo = db.scalar(
            select(func.count())
            .select_from(ViagemAluno)
            .where(ViagemAluno.viagem_id == viagem.id, ViagemAluno.status == StatusAluno.EMBARCOU)
        )
        if a_bordo:
            viagens.alertar(
                db,
                viagem,
                "crianca_a_bordo_apos_conclusao",
                viagens.Severidade.CRITICO,
                f"Viagem concluída com {a_bordo} criança(s) registrada(s) a bordo",
            )
    auditoria.registrar(
        db,
        "viagem.eventos",
        request=request,
        usuario=usuario,
        recurso="viagem",
        recurso_id=viagem.id,
        total=len(entradas),
    )
    db.commit()
    return [
        ResultadoDoEvento(id=r.id, resultado=r.resultado, motivo=r.motivo, anomalia=r.anomalia)
        for r in resultados
    ]


@router.get("/viagens/{viagem_id}/eventos")
def listar_eventos(viagem_id: IdRota, db: Db, gestor: Gestao) -> list[EventoLer]:
    _viagem(db, viagem_id, gestor)
    eventos = db.scalars(
        select(EventoViagem)
        .where(EventoViagem.viagem_id == viagem_id)
        .order_by(EventoViagem.hora_aparelho, EventoViagem.recebido_em, EventoViagem.id)
    )
    return [EventoLer.model_validate(e) for e in eventos]


@router.post("/viagens/{viagem_id}/correcoes", status_code=status.HTTP_201_CREATED)
def corrigir(
    viagem_id: IdRota, dados: Correcao, request: Request, db: Db, gestor: Gestao
) -> ViagemLer:
    viagem = _viagem(db, viagem_id, gestor, travar=True)
    viagens.corrigir(db, viagem, gestor, dados.estudante_id, dados.status, dados.motivo)
    auditoria.registrar(
        db,
        "viagem.correcao",
        request=request,
        usuario=gestor,
        recurso="viagem",
        recurso_id=viagem.id,
        estudante_id=dados.estudante_id,
        status=dados.status.value,
        motivo=dados.motivo,
    )
    db.commit()
    return _ler(db, viagem)


@router.post("/viagens/{viagem_id}/concluir")
def concluir(viagem_id: IdRota, request: Request, db: Db, usuario: Equipe) -> ConclusaoResultado:
    viagem = _viagem(db, viagem_id, usuario, travar=True)
    try:
        viagens.concluir(db, viagem)
    except HTTPException:
        db.rollback()
        raise
    auditoria.registrar(
        db,
        "viagem.concluir",
        request=request,
        usuario=usuario,
        recurso="viagem",
        recurso_id=viagem.id,
    )
    db.commit()
    return ConclusaoResultado(viagem=_ler(db, viagem))


@router.get("/alertas")
def listar_alertas(
    db: Db, _: Gestao, abertos: bool = True, limit: Limite = 50, offset: Deslocamento = 0
) -> list[AlertaLer]:
    consulta = (
        select(Alerta)
        .order_by(Alerta.criado_em.desc(), Alerta.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if abertos:
        consulta = consulta.where(Alerta.resolvido_em.is_(None))
    return [AlertaLer.model_validate(a) for a in db.scalars(consulta)]


@router.post("/alertas/{alerta_id}/resolver")
def resolver_alerta(alerta_id: IdRota, request: Request, db: Db, gestor: Gestao) -> AlertaLer:
    alerta = db.get(Alerta, alerta_id)
    if alerta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta não encontrado")
    if alerta.resolvido_em is None:
        alerta.resolvido_em = viagens.agora()
        alerta.resolvido_por_id = gestor.id
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


@router.get("/responsavel/avisos")
def meus_avisos(
    db: Db, usuario: Responsavel, limit: Limite = 50, offset: Deslocamento = 0
) -> list[AvisoLer]:
    """Avisos só dos filhos com consentimento registrado."""
    filhos = select(ResponsavelEstudante.estudante_id).where(
        ResponsavelEstudante.responsavel_id == usuario.id,
        ResponsavelEstudante.consentimento_em.is_not(None),
    )
    consulta = (
        select(Aviso)
        .where(Aviso.usuario_id == usuario.id, Aviso.estudante_id.in_(filhos))
        .order_by(Aviso.criado_em.desc(), Aviso.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [AvisoLer.model_validate(a) for a in db.scalars(consulta)]
