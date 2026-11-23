"""Posições do ônibus, acompanhamento do responsável e painel da frota."""

import secrets
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

import redis
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import func, select, text

from app import auditoria, rastreamento, tempo_real
from app.cadastros import Db, IdRota
from app.config import settings
from app.models import (
    Alerta,
    Estudante,
    Inscricao,
    Perfil,
    Rota,
    StatusAluno,
    StatusViagem,
    Turno,
    Usuario,
    Veiculo,
    Viagem,
    ViagemAluno,
    ViagemParada,
)
from app.routers.viagens import Equipe, Gestao, _viagem
from app.schemas.rastreamento import (
    EstadoAoVivo,
    FilhoHoje,
    ItemDaFrota,
    LotePosicoes,
    OnibusDoFilho,
    PontoDoPercurso,
    PosicaoAtual,
    PosicaoDoOnibus,
    Previsao,
    ProximaParada,
    ResultadoPosicao,
    TokenRastreador,
    ViagemDoFilho,
)
from app.security import Responsavel, exigir_perfil, garantir_responsavel, hash_refresh_token

router = APIRouter(tags=["rastreamento"])
SoMotorista = Annotated[Usuario, exigir_perfil(Perfil.MOTORISTA)]
DIAS_PARA_SINCRONIZAR = 1
MAX_PERCURSO = 5000


def _para_entradas(dados: LotePosicoes) -> list[rastreamento.PosicaoEntrada]:
    return [
        rastreamento.PosicaoEntrada(
            registrada_em=p.registrada_em,
            latitude=p.latitude,
            longitude=p.longitude,
            velocidade_kmh=p.velocidade_kmh,
            precisao_m=p.precisao_m,
        )
        for p in dados.posicoes
    ]


def _resultados(rs: list[rastreamento.Resultado]) -> list[ResultadoPosicao]:
    return [
        ResultadoPosicao(registrada_em=r.registrada_em, resultado=r.resultado, motivo=r.motivo)
        for r in rs
    ]


@router.post("/viagens/{viagem_id}/posicoes")
def receber_posicoes(
    viagem_id: IdRota, dados: LotePosicoes, db: Db, motorista: SoMotorista
) -> list[ResultadoPosicao]:
    """Lote do aparelho do motorista escalado, só com a viagem em andamento."""
    viagem = _viagem(db, viagem_id, motorista, tolerancia_dias=DIAS_PARA_SINCRONIZAR, travar=True)
    if viagem.motorista_id != motorista.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viagem não encontrada")
    if viagem.status != StatusViagem.EM_ANDAMENTO:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    resultados = rastreamento.ingerir(db, viagem, _para_entradas(dados), "aparelho")
    db.commit()
    return _resultados(resultados)


@router.post("/rastreador/posicoes")
def receber_do_rastreador(
    dados: LotePosicoes,
    db: Db,
    x_token_rastreador: Annotated[str, Header(min_length=20, max_length=200)],
) -> list[ResultadoPosicao]:
    """Rastreador veicular: autentica pelo veículo e grava na viagem em andamento dele."""
    veiculo = db.scalar(
        select(Veiculo).where(
            Veiculo.token_rastreador_hash == hash_refresh_token(x_token_rastreador)
        )
    )
    if veiculo is None or not veiculo.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    viagem = db.scalar(
        select(Viagem)
        .where(
            Viagem.veiculo_id == veiculo.id,
            Viagem.status == StatusViagem.EM_ANDAMENTO,
            Viagem.data == date.today(),
        )
        .with_for_update()
    )
    if viagem is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O veículo não tem viagem em andamento")
    resultados = rastreamento.ingerir(db, viagem, _para_entradas(dados), "rastreador")
    db.commit()
    return _resultados(resultados)


@router.post("/veiculos/{veiculo_id}/token-rastreador", status_code=status.HTTP_201_CREATED)
def gerar_token_do_rastreador(
    veiculo_id: IdRota, request: Request, db: Db, gestor: Gestao
) -> TokenRastreador:
    """O token aparece só nesta resposta; o banco guarda o hash. Gerar outro revoga o anterior."""
    veiculo = db.get(Veiculo, veiculo_id)
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado")
    token = secrets.token_urlsafe(32)
    veiculo.token_rastreador_hash = hash_refresh_token(token)
    auditoria.registrar(
        db,
        "rastreador.token",
        request=request,
        usuario=gestor,
        recurso="veiculo",
        recurso_id=veiculo.id,
    )
    db.commit()
    return TokenRastreador(token=token)


@router.delete("/veiculos/{veiculo_id}/token-rastreador", status_code=status.HTTP_204_NO_CONTENT)
def revogar_token_do_rastreador(
    veiculo_id: IdRota, request: Request, db: Db, gestor: Gestao
) -> None:
    veiculo = db.get(Veiculo, veiculo_id)
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado")
    veiculo.token_rastreador_hash = None
    auditoria.registrar(
        db,
        "rastreador.revogar",
        request=request,
        usuario=gestor,
        recurso="veiculo",
        recurso_id=veiculo.id,
    )
    db.commit()


def ultima_posicao(db: Db, viagem_id: int) -> dict | None:
    """Do Redis; se ele estiver fora do ar, a última gravada no banco."""
    try:
        return tempo_real.ler_posicao(viagem_id)
    except redis.RedisError:
        linha = db.execute(
            text(
                """
                SELECT registrada_em, ST_Y(localizacao) AS lat, ST_X(localizacao) AS lon,
                       velocidade_kmh
                FROM posicao WHERE viagem_id = :v ORDER BY registrada_em DESC LIMIT 1
                """
            ),
            {"v": viagem_id},
        ).first()
        if linha is None:
            return None
        return {
            "viagem_id": viagem_id,
            "latitude": linha.lat,
            "longitude": linha.lon,
            "registrada_em": linha.registrada_em.isoformat(),
            "ts": linha.registrada_em.timestamp(),
            "velocidade_kmh": linha.velocidade_kmh,
            "desvio_m": None,
        }


@router.get("/viagens/{viagem_id}/posicao")
def posicao_atual(viagem_id: IdRota, db: Db, usuario: Equipe) -> EstadoAoVivo:
    viagem = _viagem(db, viagem_id, usuario)
    posicao = ultima_posicao(db, viagem.id)
    proxima = None
    if viagem.status == StatusViagem.EM_ANDAMENTO:
        parada = rastreamento.proxima_parada(db, viagem.id)
        if parada is not None:
            prev = rastreamento.previsao(db, viagem, parada.parada_id, posicao) if posicao else None
            proxima = ProximaParada(
                parada_id=parada.parada_id,
                nome=parada.nome,
                horario_previsto=parada.horario_previsto.isoformat()
                if parada.horario_previsto
                else None,
                previsao=Previsao(**prev) if prev else None,
            )
    return EstadoAoVivo(
        posicao=PosicaoAtual(**{k: v for k, v in posicao.items() if k != "ts"})
        if posicao
        else None,
        proxima_parada=proxima,
    )


@router.get("/viagens/{viagem_id}/percurso")
def percurso(
    viagem_id: IdRota, db: Db, usuario: Equipe, desde: datetime | None = None
) -> list[PontoDoPercurso]:
    viagem = _viagem(db, viagem_id, usuario)
    consulta = text(
        """
        SELECT registrada_em, ST_Y(localizacao) AS lat, ST_X(localizacao) AS lon, velocidade_kmh
        FROM posicao
        WHERE viagem_id = :v
          AND (CAST(:desde AS timestamptz) IS NULL OR registrada_em > :desde)
        ORDER BY registrada_em LIMIT :limite
        """
    )
    linhas = db.execute(consulta, {"v": viagem.id, "desde": desde, "limite": MAX_PERCURSO})
    return [
        PontoDoPercurso(
            registrada_em=r.registrada_em,
            latitude=r.lat,
            longitude=r.lon,
            velocidade_kmh=r.velocidade_kmh,
        )
        for r in linhas
    ]


# Acompanhamento do responsável


@router.get("/responsavel/filhos/{estudante_id}/hoje")
def filho_hoje(estudante_id: IdRota, request: Request, db: Db, usuario: Responsavel) -> FilhoHoje:
    """Situação do filho e, só enquanto ele está na viagem, a posição do ônibus.

    Fora da janela (antes do início, depois do desembarque, falta avisada) a posição não sai:
    ver o ônibus nesses momentos seria ver onde estão outras crianças.
    """
    garantir_responsavel(db, usuario, estudante_id)
    estudante = db.get(Estudante, estudante_id)
    hoje = date.today()
    na_lista = select(ViagemAluno.viagem_id).where(ViagemAluno.estudante_id == estudante_id)
    inscritas = select(Inscricao.rota_id).where(
        Inscricao.estudante_id == estudante_id, Inscricao.ativa.is_(True)
    )
    candidatas = db.scalars(
        select(Viagem)
        .where(
            Viagem.data == hoje,
            Viagem.status != StatusViagem.CANCELADA,
            (Viagem.id.in_(na_lista))
            | ((Viagem.rota_id.in_(inscritas)) & (Viagem.status == StatusViagem.AGENDADA)),
        )
        .order_by(Viagem.id)
    ).all()
    saida: list[ViagemDoFilho] = []
    for viagem in candidatas:
        aluno = db.get(ViagemAluno, (viagem.id, estudante_id))
        situacao = aluno.status if aluno else StatusAluno.AGUARDANDO
        parada_id = (
            aluno.parada_id
            if aluno
            else db.scalar(
                select(Inscricao.parada_id).where(
                    Inscricao.estudante_id == estudante_id,
                    Inscricao.rota_id == viagem.rota_id,
                    Inscricao.ativa.is_(True),
                )
            )
        )
        parada = (
            db.get(ViagemParada, (viagem.id, aluno.parada_id))
            if aluno and aluno.parada_id
            else None
        )
        veiculo = db.get(Veiculo, viagem.veiculo_id) if viagem.veiculo_id else None
        motorista = db.get(Usuario, viagem.motorista_id) if viagem.motorista_id else None
        andando = viagem.status == StatusViagem.EM_ANDAMENTO
        liberada = andando and situacao in (StatusAluno.AGUARDANDO, StatusAluno.EMBARCOU)
        posicao = prev = None
        if andando:
            auditoria.registrar(
                db,
                "posicao.consultar",
                request=request,
                usuario=usuario,
                recurso="viagem",
                recurso_id=viagem.id,
                estudante_id=estudante_id,
                liberada=liberada,
            )
        if liberada:
            bruta = ultima_posicao(db, viagem.id)
            if bruta:
                posicao = PosicaoDoOnibus(
                    latitude=bruta["latitude"],
                    longitude=bruta["longitude"],
                    registrada_em=bruta["registrada_em"],
                    velocidade_kmh=bruta["velocidade_kmh"],
                )
                if parada_id is not None:
                    calc = rastreamento.previsao(db, viagem, parada_id, bruta)
                    prev = Previsao(**calc) if calc else None
        saida.append(
            ViagemDoFilho(
                viagem_id=viagem.id,
                sentido=viagem.sentido,
                turno=viagem.turno,
                status_viagem=viagem.status,
                situacao_do_filho=situacao,
                parada_nome=parada.nome if parada else None,
                onibus=OnibusDoFilho(
                    placa=veiculo.placa if veiculo else None,
                    motorista_nome=motorista.nome if motorista else None,
                ),
                posicao=posicao,
                previsao=prev,
            )
        )
    db.commit()
    return FilhoHoje(estudante_id=estudante_id, nome=estudante.nome, data=hoje, viagens=saida)


# Painel da frota


def _atraso_min(db: Db, viagem: Viagem, agora_local: datetime) -> int | None:
    """Minutos de atraso na primeira parada que o ônibus ainda não alcançou."""
    parada = rastreamento.proxima_parada(db, viagem.id)
    if parada is None or parada.horario_previsto is None:
        return None
    previsto = agora_local.replace(
        hour=parada.horario_previsto.hour,
        minute=parada.horario_previsto.minute,
        second=0,
        microsecond=0,
    )
    atraso = (agora_local - previsto).total_seconds() / 60
    return max(0, int(atraso))


@router.get("/painel/frota")
def painel_frota(
    db: Db,
    _: Gestao,
    data: date | None = None,
    escola_id: int | None = None,
    turno: Turno | None = None,
    situacao: StatusViagem | None = None,
) -> list[ItemDaFrota]:
    dia = data or date.today()
    consulta = (
        select(Viagem, Rota.nome)
        .join(Rota, Rota.id == Viagem.rota_id)
        .where(Viagem.data == dia)
        .order_by(Viagem.id)
    )
    if escola_id is not None:
        consulta = consulta.where(Viagem.escola_id == escola_id)
    if turno is not None:
        consulta = consulta.where(Viagem.turno == turno)
    if situacao is not None:
        consulta = consulta.where(Viagem.status == situacao)
    linhas = db.execute(consulta).all()
    ids = [v.id for v, _ in linhas]
    try:
        posicoes = tempo_real.ler_posicoes(ids)
    except redis.RedisError:
        posicoes = {}
    a_bordo = {
        a: b
        for a, b in db.execute(
            select(ViagemAluno.viagem_id, func.count())
            .where(ViagemAluno.viagem_id.in_(ids), ViagemAluno.status == StatusAluno.EMBARCOU)
            .group_by(ViagemAluno.viagem_id)
        )
    }
    alertas = {
        a: b
        for a, b in db.execute(
            select(Alerta.viagem_id, func.count())
            .where(Alerta.viagem_id.in_(ids), Alerta.resolvido_em.is_(None))
            .group_by(Alerta.viagem_id)
        )
    }
    placas = {a: b for a, b in db.execute(select(Veiculo.id, Veiculo.placa))}
    nomes = {
        a: b
        for a, b in db.execute(
            select(Usuario.id, Usuario.nome).where(
                Usuario.id.in_([v.motorista_id for v, _ in linhas if v.motorista_id])
            )
        )
    }
    agora_local = datetime.now(ZoneInfo(settings.fuso_horario))
    itens = []
    for viagem, rota_nome in linhas:
        bruta = posicoes.get(viagem.id)
        itens.append(
            ItemDaFrota(
                viagem_id=viagem.id,
                rota_id=viagem.rota_id,
                rota_nome=rota_nome,
                escola_id=viagem.escola_id,
                turno=viagem.turno,
                sentido=viagem.sentido,
                status=viagem.status,
                placa=placas.get(viagem.veiculo_id),
                motorista_nome=nomes.get(viagem.motorista_id),
                posicao=PosicaoAtual(**{k: v for k, v in bruta.items() if k != "ts"})
                if bruta
                else None,
                atraso_min=_atraso_min(db, viagem, agora_local)
                if viagem.status == StatusViagem.EM_ANDAMENTO and dia == date.today()
                else None,
                alunos_a_bordo=a_bordo.get(viagem.id, 0),
                alertas_abertos=alertas.get(viagem.id, 0),
            )
        )
    return itens
