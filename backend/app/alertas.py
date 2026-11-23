"""Regras de alerta que dependem do tempo passar, executadas pelo worker.

R6 viagem não iniciada, R7 sem sinal, R8 desvio de rota, R9 parada não prevista, R10 velocidade.
Os limites vêm da tabela `configuracao`. Cada regra abre no máximo um alerta aberto por viagem.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import notificacoes, tempo_real
from app.config import settings
from app.models import (
    Alerta,
    Configuracao,
    RotaParada,
    Severidade,
    StatusAluno,
    StatusViagem,
    Viagem,
    ViagemAluno,
)
from app.viagens import alertar

PADRAO = {
    "viagem_nao_iniciada_min": 10,
    "sem_sinal_s": 120,
    "desvio_max_m": 300,
    "parada_nao_prevista_min": 5,
    "parado_raio_m": 30,
    "velocidade_max_kmh": 80,
    "atraso_aviso_min": 10,
    "emergencia_avisa_responsaveis": 0,
}


def limites(db: Session) -> dict[str, float]:
    """Valores da tabela; a chave que faltar usa o padrão."""
    return {**PADRAO, **{c.chave: c.valor for c in db.scalars(select(Configuracao))}}


def _aberto(db: Session, viagem_id: int, tipo: str) -> Alerta | None:
    return db.scalar(
        select(Alerta).where(
            Alerta.viagem_id == viagem_id, Alerta.tipo == tipo, Alerta.resolvido_em.is_(None)
        )
    )


def _abrir(
    db: Session,
    viagem: Viagem,
    tipo: str,
    severidade: Severidade,
    mensagem: str,
    dados: dict,
) -> Alerta | None:
    if _aberto(db, viagem.id, tipo) is not None:
        return None
    alerta = alertar(db, viagem, tipo, severidade, mensagem)
    alerta.dados = dados
    return alerta


def _resolver_sozinho(db: Session, alerta: Alerta, agora: datetime) -> None:
    alerta.resolvido_em = agora
    alerta.resolvido_automaticamente = True


def _ultima_posicao(viagem_id: int) -> dict | None:
    try:
        return tempo_real.ler_posicao(viagem_id)
    except redis.RedisError:
        return None


# R6


def viagem_nao_iniciada(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    """Passou o horário da primeira parada (mais a tolerância) e a viagem continua agendada."""
    local = agora.astimezone(ZoneInfo(settings.fuso_horario))
    criados = []
    viagens = db.scalars(
        select(Viagem).where(Viagem.status == StatusViagem.AGENDADA, Viagem.data == local.date())
    )
    for viagem in viagens:
        primeira = db.scalar(
            select(RotaParada.horario_previsto)
            .where(RotaParada.rota_id == viagem.rota_id, RotaParada.horario_previsto.is_not(None))
            .order_by(RotaParada.ordem)
            .limit(1)
        )
        if primeira is None:
            continue
        previsto = local.replace(
            hour=primeira.hour, minute=primeira.minute, second=0, microsecond=0
        )
        atraso = (local - previsto).total_seconds() / 60
        if atraso > lim["viagem_nao_iniciada_min"]:
            alerta = _abrir(
                db,
                viagem,
                "viagem_nao_iniciada",
                Severidade.AVISO,
                f"A viagem prevista para {primeira:%H:%M} ainda não foi iniciada",
                {"atraso_min": round(atraso), "limite_min": lim["viagem_nao_iniciada_min"]},
            )
            if alerta:
                criados.append(alerta)
    return criados


# R7 a R10: viagens em andamento


def _em_andamento(db: Session) -> list[Viagem]:
    return list(db.scalars(select(Viagem).where(Viagem.status == StatusViagem.EM_ANDAMENTO)))


def sem_sinal(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    """Nenhuma posição há mais que o limite. Resolve sozinho quando o sinal volta."""
    criados = []
    for viagem in _em_andamento(db):
        posicao = _ultima_posicao(viagem.id)
        ultima = (
            datetime.fromtimestamp(posicao["ts"], UTC) if posicao else (viagem.iniciada_em or agora)
        )
        parado_ha = (agora - ultima).total_seconds()
        aberto = _aberto(db, viagem.id, "sem_sinal")
        if parado_ha > lim["sem_sinal_s"]:
            alerta = _abrir(
                db,
                viagem,
                "sem_sinal",
                Severidade.AVISO,
                f"Ônibus sem sinal há {int(parado_ha // 60)} min",
                {"segundos_sem_sinal": round(parado_ha), "limite_s": lim["sem_sinal_s"]},
            )
            if alerta:
                criados.append(alerta)
        elif aberto is not None:
            _resolver_sozinho(db, aberto, agora)
    # Viagem que acabou não deve deixar "sem sinal" aberto.
    for alerta in db.scalars(
        select(Alerta)
        .join(Viagem, Viagem.id == Alerta.viagem_id)
        .where(
            Alerta.tipo == "sem_sinal",
            Alerta.resolvido_em.is_(None),
            Viagem.status != StatusViagem.EM_ANDAMENTO,
        )
    ):
        _resolver_sozinho(db, alerta, agora)
    return criados


def _posicao_fresca(posicao: dict | None, agora: datetime, lim: dict) -> bool:
    return posicao is not None and (agora.timestamp() - posicao["ts"]) <= lim["sem_sinal_s"]


def desvio_de_rota(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    criados = []
    for viagem in _em_andamento(db):
        posicao = _ultima_posicao(viagem.id)
        if not _posicao_fresca(posicao, agora, lim):
            continue
        desvio = posicao.get("desvio_m")
        if desvio is not None and desvio > lim["desvio_max_m"]:
            alerta = _abrir(
                db,
                viagem,
                "desvio_de_rota",
                Severidade.AVISO,
                f"Ônibus a {round(desvio)} m do trajeto previsto",
                {"desvio_m": round(desvio), "limite_m": lim["desvio_max_m"], **_onde(posicao)},
            )
            if alerta:
                criados.append(alerta)
    return criados


def velocidade_excessiva(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    criados = []
    for viagem in _em_andamento(db):
        posicao = _ultima_posicao(viagem.id)
        if not _posicao_fresca(posicao, agora, lim):
            continue
        v = posicao.get("velocidade_kmh")
        if v is not None and v > lim["velocidade_max_kmh"]:
            alerta = _abrir(
                db,
                viagem,
                "velocidade_acima_do_limite",
                Severidade.AVISO,
                f"Ônibus a {round(v)} km/h (limite {round(lim['velocidade_max_kmh'])} km/h)",
                {
                    "velocidade_kmh": round(v),
                    "limite_kmh": lim["velocidade_max_kmh"],
                    **_onde(posicao),
                },
            )
            if alerta:
                criados.append(alerta)
    return criados


def _onde(posicao: dict) -> dict:
    return {"latitude": posicao["latitude"], "longitude": posicao["longitude"]}


_PARADO = text(
    """
    SELECT count(*) AS n,
           min(p.registrada_em) AS primeira,
           max(p.registrada_em) AS ultima,
           max(ST_Distance(p.localizacao::geography, u.localizacao::geography)) AS espalhamento,
           bool_or(EXISTS (
               SELECT 1 FROM viagem_parada vp
               WHERE vp.viagem_id = :v
                 AND ST_DWithin(
                     vp.localizacao::geography, u.localizacao::geography, vp.raio_cerca_m
                 )
           )) AS numa_parada,
           bool_or(ST_DWithin(e.localizacao::geography, u.localizacao::geography, e.raio_cerca_m))
               AS na_escola
    FROM posicao p
    CROSS JOIN LATERAL (
        SELECT localizacao FROM posicao WHERE viagem_id = :v ORDER BY registrada_em DESC LIMIT 1
    ) u
    CROSS JOIN escola e
    WHERE p.viagem_id = :v AND p.registrada_em >= :desde AND e.id = :escola
    """
)


def parada_nao_prevista(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    """Ônibus parado no mesmo lugar por minutos, fora de qualquer parada e da escola."""
    criados = []
    janela = timedelta(minutes=lim["parada_nao_prevista_min"])
    for viagem in _em_andamento(db):
        if not _posicao_fresca(_ultima_posicao(viagem.id), agora, lim):
            continue
        r = db.execute(
            _PARADO, {"v": viagem.id, "desde": agora - janela, "escola": viagem.escola_id}
        ).first()
        if not r or r.n < 2 or r.primeira is None:
            continue
        cobre_a_janela = (r.ultima - r.primeira) >= janela * 0.9
        parado = (r.espalhamento or 0) <= lim["parado_raio_m"]
        if cobre_a_janela and parado and not r.numa_parada and not r.na_escola:
            alerta = _abrir(
                db,
                viagem,
                "parada_nao_prevista",
                Severidade.AVISO,
                f"Ônibus parado há {int(lim['parada_nao_prevista_min'])} min fora de uma parada",
                {"minutos": lim["parada_nao_prevista_min"], **_onde(_ultima_posicao(viagem.id))},
            )
            if alerta:
                criados.append(alerta)
    return criados


# Aviso de atraso aos responsáveis


def avisar_atraso(db: Session, agora: datetime, lim: dict) -> int:
    """Responsáveis dos alunos que esperam numa parada que o ônibus ainda não alcançou."""
    local = agora.astimezone(ZoneInfo(settings.fuso_horario))
    enviados = 0
    for viagem in _em_andamento(db):
        paradas = db.execute(
            text(
                """
                SELECT parada_id, horario_previsto FROM viagem_parada
                WHERE viagem_id = :v AND chegada_em IS NULL AND horario_previsto IS NOT NULL
                """
            ),
            {"v": viagem.id},
        ).all()
        for parada_id, previsto in paradas:
            ref = local.replace(hour=previsto.hour, minute=previsto.minute, second=0, microsecond=0)
            atraso = (local - ref).total_seconds() / 60
            if atraso < lim["atraso_aviso_min"]:
                continue
            alunos = db.scalars(
                select(ViagemAluno).where(
                    ViagemAluno.viagem_id == viagem.id,
                    ViagemAluno.parada_id == parada_id,
                    ViagemAluno.status == StatusAluno.AGUARDANDO,
                )
            ).all()
            for aluno in alunos:
                ja = db.scalar(
                    text(
                        "SELECT 1 FROM notificacao WHERE tipo = 'atraso' AND viagem_id = :v "
                        "AND estudante_id = :e LIMIT 1"
                    ),
                    {"v": viagem.id, "e": aluno.estudante_id},
                )
                if ja:
                    continue
                from app.models import Estudante

                nome = notificacoes.nome_curto(db.get(Estudante, aluno.estudante_id))
                enviados += notificacoes.para_responsaveis(
                    db,
                    aluno.estudante_id,
                    "atraso",
                    "Ônibus atrasado",
                    f"O ônibus de {nome} está com cerca de {round(atraso)} min de atraso.",
                    viagem_id=viagem.id,
                )
    return enviados


REGRAS = (viagem_nao_iniciada, sem_sinal, desvio_de_rota, parada_nao_prevista, velocidade_excessiva)


def executar_regras(db: Session, agora: datetime | None = None) -> list[Alerta]:
    """Roda todas as regras. Devolve os alertas abertos nesta execução."""
    agora = agora or datetime.now(UTC)
    lim = limites(db)
    criados: list[Alerta] = []
    for regra in REGRAS:
        criados += regra(db, agora, lim)
    avisar_atraso(db, agora, lim)
    db.flush()
    return criados
