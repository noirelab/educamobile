"""Posições do ônibus: recebimento, cercas virtuais, previsão de chegada e desvio de rota."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import notificacoes, tempo_real, viagens
from app.geo import Coordenadas, para_ponto
from app.models import Estudante, Posicao, StatusAluno, Viagem, ViagemAluno, ViagemParada

# Entre duas posições seguidas, mais que isso é salto impossível (GPS com defeito ou forjado).
VELOCIDADE_MAXIMA_KMH = 150.0
VELOCIDADE_INFORMADA_MAXIMA_KMH = 200.0
PRECISAO_MAXIMA_M = 100.0
TOLERANCIA_RELOGIO_S = 300
# Posição registrada antes do início da viagem não pertence a ela.
ANTECEDENCIA_MAXIMA = timedelta(minutes=10)
# Abaixo disso o ônibus está parado: dividir a distância por ela dá previsão sem sentido.
VELOCIDADE_MINIMA_PREVISAO_KMH = 3.0
JANELA_VELOCIDADE = timedelta(minutes=5)


@dataclass
class PosicaoEntrada:
    registrada_em: datetime
    latitude: float
    longitude: float
    velocidade_kmh: float | None = None
    precisao_m: float | None = None


@dataclass
class Resultado:
    registrada_em: datetime
    resultado: str  # aceita | duplicada | rejeitada
    motivo: str | None = None


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância de círculo máximo (haversine), suficiente para conferir saltos."""
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


_PONTO = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"


def _cercas(
    db: Session, viagem: Viagem, ponto: Coordenadas, momento: datetime
) -> list[tuple[str, int]]:
    """Marca chegada (entrou na cerca da parada) e partida (saiu dela). Devolve os eventos."""
    p = {"lon": ponto.longitude, "lat": ponto.latitude, "v": viagem.id, "t": momento}
    eventos: list[tuple[str, int]] = []
    chegadas = db.execute(
        text(
            f"""
            UPDATE viagem_parada vp SET chegada_em = :t
            WHERE vp.viagem_id = :v AND vp.chegada_em IS NULL
              AND ST_DWithin(vp.localizacao::geography, {_PONTO}::geography, vp.raio_cerca_m)
            RETURNING vp.parada_id
            """
        ),
        p,
    )
    eventos += [("chegada", r[0]) for r in chegadas]
    partidas = db.execute(
        text(
            f"""
            UPDATE viagem_parada vp SET partida_em = :t
            WHERE vp.viagem_id = :v AND vp.chegada_em IS NOT NULL AND vp.partida_em IS NULL
              AND vp.chegada_em < :t
              AND NOT ST_DWithin(vp.localizacao::geography, {_PONTO}::geography, vp.raio_cerca_m)
            RETURNING vp.parada_id
            """
        ),
        p,
    )
    eventos += [("partida", r[0]) for r in partidas]
    return eventos


def _avisar_chegada(db: Session, viagem: Viagem, parada_id: int) -> None:
    """Ônibus chegando: avisa quem tem criança esperando nessa parada."""
    esperando = db.scalars(
        select(ViagemAluno).where(
            ViagemAluno.viagem_id == viagem.id,
            ViagemAluno.parada_id == parada_id,
            ViagemAluno.status == StatusAluno.AGUARDANDO,
        )
    ).all()
    for aluno in esperando:
        nome = notificacoes.nome_curto(db.get(Estudante, aluno.estudante_id))
        notificacoes.para_responsaveis(
            db,
            aluno.estudante_id,
            "onibus_chegando",
            "Ônibus chegando",
            f"O ônibus chegou à parada de {nome}.",
            viagem_id=viagem.id,
        )


def desvio_m(db: Session, viagem: Viagem, ponto: Coordenadas) -> float | None:
    """Distância da posição ao trajeto previsto da rota (base do alerta de desvio, R8)."""
    return db.scalar(
        text(
            f"""
            SELECT ST_Distance(r.trajeto::geography, {_PONTO}::geography)
            FROM rota r WHERE r.id = :rota AND r.trajeto IS NOT NULL
            """
        ),
        {"lon": ponto.longitude, "lat": ponto.latitude, "rota": viagem.rota_id},
    )


def ingerir(
    db: Session,
    viagem: Viagem,
    entradas: list[PosicaoEntrada],
    fonte: str,
) -> list[Resultado]:
    """Grava o lote em ordem de tempo, recusando o impossível, e atualiza o estado ao vivo."""
    resultados: list[Resultado] = []
    agora = viagens.agora()
    limite_futuro = agora + timedelta(seconds=TOLERANCIA_RELOGIO_S)
    inicio = (viagem.iniciada_em or agora) - ANTECEDENCIA_MAXIMA
    ordenadas = sorted(entradas, key=lambda e: e.registrada_em)

    anterior = None
    if ordenadas:
        anterior = db.execute(
            text(
                """
                SELECT registrada_em, ST_Y(localizacao) AS lat, ST_X(localizacao) AS lon
                FROM posicao WHERE viagem_id = :v AND registrada_em < :t
                ORDER BY registrada_em DESC LIMIT 1
                """
            ),
            {"v": viagem.id, "t": ordenadas[0].registrada_em},
        ).first()
    ref = (anterior.registrada_em, anterior.lat, anterior.lon) if anterior else None

    aceitas: list[PosicaoEntrada] = []
    for e in ordenadas:
        if e.registrada_em > limite_futuro:
            resultados.append(Resultado(e.registrada_em, "rejeitada", "Data no futuro"))
            continue
        if e.registrada_em < inicio:
            resultados.append(
                Resultado(e.registrada_em, "rejeitada", "Anterior ao início da viagem")
            )
            continue
        if e.precisao_m is not None and e.precisao_m > PRECISAO_MAXIMA_M:
            # Um fix ruim vira ponto de referência e faria as posições boas parecerem saltos.
            resultados.append(Resultado(e.registrada_em, "rejeitada", "Precisão do GPS ruim"))
            continue
        if e.velocidade_kmh is not None and e.velocidade_kmh > VELOCIDADE_INFORMADA_MAXIMA_KMH:
            resultados.append(
                Resultado(e.registrada_em, "rejeitada", "Velocidade informada impossível")
            )
            continue
        if ref is not None:
            dt = (e.registrada_em - ref[0]).total_seconds()
            salto = distancia_m(ref[1], ref[2], e.latitude, e.longitude)
            if dt > 0 and salto / dt * 3.6 > VELOCIDADE_MAXIMA_KMH:
                resultados.append(
                    Resultado(e.registrada_em, "rejeitada", "Salto de velocidade impossível")
                )
                continue
        gravada = db.scalar(
            insert(Posicao)
            .values(
                viagem_id=viagem.id,
                registrada_em=e.registrada_em,
                localizacao=para_ponto(Coordenadas(latitude=e.latitude, longitude=e.longitude)),
                velocidade_kmh=e.velocidade_kmh,
                precisao_m=e.precisao_m,
                fonte=fonte,
            )
            .on_conflict_do_nothing(index_elements=["viagem_id", "registrada_em"])
            .returning(Posicao.id)
        )
        if gravada is None:
            resultados.append(Resultado(e.registrada_em, "duplicada"))
            continue
        resultados.append(Resultado(e.registrada_em, "aceita"))
        aceitas.append(e)
        ref = (e.registrada_em, e.latitude, e.longitude)

    mais_recente = None
    for e in aceitas:
        ponto = Coordenadas(latitude=e.latitude, longitude=e.longitude)
        for tipo, parada_id in _cercas(db, viagem, ponto, e.registrada_em):
            if tipo == "chegada":
                _avisar_chegada(db, viagem, parada_id)
            tempo_real.enfileirar(
                db,
                viagem.id,
                {"tipo": f"{tipo}_parada", "viagem_id": viagem.id, "parada_id": parada_id},
            )
        viagens.verificar_saida_da_cerca(db, viagem, ponto)
        mais_recente = e
    if mais_recente is not None:
        ponto = Coordenadas(latitude=mais_recente.latitude, longitude=mais_recente.longitude)
        dados = {
            "viagem_id": viagem.id,
            "latitude": mais_recente.latitude,
            "longitude": mais_recente.longitude,
            "registrada_em": mais_recente.registrada_em.astimezone(UTC).isoformat(),
            "ts": mais_recente.registrada_em.timestamp(),
            "velocidade_kmh": mais_recente.velocidade_kmh,
            "desvio_m": desvio_m(db, viagem, ponto),
        }
        if tempo_real.guardar_posicao(viagem.id, dados):
            tempo_real.enfileirar(db, viagem.id, {"tipo": "posicao", **dados})
    db.flush()
    return resultados


def velocidade_media_kmh(db: Session, viagem_id: int) -> float | None:
    """Velocidade média dos últimos minutos, pela distância percorrida entre as posições."""
    linhas = db.execute(
        text(
            """
            SELECT registrada_em, ST_Y(localizacao) AS lat, ST_X(localizacao) AS lon, velocidade_kmh
            FROM posicao WHERE viagem_id = :v
            ORDER BY registrada_em DESC LIMIT 30
            """
        ),
        {"v": viagem_id},
    ).all()
    if len(linhas) < 2:
        return None
    ultimo = linhas[0].registrada_em
    recentes = [r for r in linhas if ultimo - r.registrada_em <= JANELA_VELOCIDADE]
    if len(recentes) >= 2:
        percorrido = sum(
            distancia_m(a.lat, a.lon, b.lat, b.lon)
            for a, b in zip(recentes, recentes[1:], strict=False)
        )
        tempo = (recentes[0].registrada_em - recentes[-1].registrada_em).total_seconds()
        if tempo >= 30:
            return percorrido / tempo * 3.6
    informadas = [r.velocidade_kmh for r in recentes if r.velocidade_kmh is not None]
    return sum(informadas) / len(informadas) if informadas else None


def previsao(db: Session, viagem: Viagem, parada_id: int, posicao: dict) -> dict | None:
    """Distância restante no trajeto até a parada, dividida pela velocidade média recente."""
    linha = db.execute(
        text(
            f"""
            SELECT ST_LineLocatePoint(r.trajeto, {_PONTO}) AS onibus,
                   ST_LineLocatePoint(r.trajeto, vp.localizacao) AS parada,
                   ST_Length(r.trajeto::geography) AS comprimento,
                   ST_Distance(
                       ST_StartPoint(r.trajeto)::geography, {_PONTO}::geography
                   ) AS ate_o_inicio
            FROM viagem_parada vp JOIN rota r ON r.id = :rota
            WHERE vp.viagem_id = :v AND vp.parada_id = :p AND r.trajeto IS NOT NULL
            """
        ),
        {
            "lon": posicao["longitude"],
            "lat": posicao["latitude"],
            "rota": viagem.rota_id,
            "v": viagem.id,
            "p": parada_id,
        },
    ).first()
    if linha is None:
        return None
    if linha.onibus == 0:
        # Antes da primeira parada (saindo da garagem): primeiro chega ao início do trajeto.
        restante = linha.ate_o_inicio + linha.parada * linha.comprimento
    else:
        restante = max(0.0, (linha.parada - linha.onibus) * linha.comprimento)
    resultado: dict = {
        "parada_id": parada_id,
        "distancia_restante_m": round(restante),
        "eta_segundos": None,
    }
    velocidade = velocidade_media_kmh(db, viagem.id)
    if restante == 0:
        resultado["eta_segundos"] = 0
    elif velocidade is not None and velocidade >= VELOCIDADE_MINIMA_PREVISAO_KMH:
        resultado["eta_segundos"] = round(restante / (velocidade / 3.6))
    return resultado


def modo_da_lista(db: Session, viagem: Viagem) -> str:
    """Embarque até o ônibus chegar à escola (ida) ou sair dela (volta); depois, desembarque."""
    paradas = db.scalars(
        select(ViagemParada).where(ViagemParada.viagem_id == viagem.id).order_by(ViagemParada.ordem)
    ).all()
    if not paradas:
        return "embarque"
    if viagem.sentido.value == "ida":
        escola = paradas[-1]
        return "desembarque" if escola.chegada_em or viagem.dentro_da_cerca_escola else "embarque"
    return "desembarque" if paradas[0].partida_em else "embarque"


def proxima_parada(db: Session, viagem_id: int) -> ViagemParada | None:
    """A primeira parada da sequência que o ônibus ainda não alcançou."""
    return db.scalar(
        select(ViagemParada)
        .where(ViagemParada.viagem_id == viagem_id, ViagemParada.chegada_em.is_(None))
        .order_by(ViagemParada.ordem)
        .limit(1)
    )
