"""Regras de alerta que dependem do tempo passar, executadas pelo worker.

R6 viagem não iniciada, R7 sem sinal, R8 desvio de rota, R9 parada não prevista, R10 velocidade
e as regras críticas de criança possivelmente esquecida a bordo e de criança que desceu na escola
sem a escola confirmar o recebimento.
Os limites vêm da tabela `configuracao`. Cada regra abre no máximo um alerta aberto por viagem.
"""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import redis
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import notificacoes, tempo_real
from app.config import settings
from app.models import (
    Alerta,
    Configuracao,
    Escola,
    Estudante,
    EventoViagem,
    RotaParada,
    Sentido,
    Severidade,
    StatusAluno,
    StatusViagem,
    TipoEvento,
    Viagem,
    ViagemAluno,
)
from app.viagens import alertar

log = logging.getLogger(__name__)

PADRAO = {
    "viagem_nao_iniciada_min": 10,
    "sem_sinal_s": 120,
    "desvio_max_m": 300,
    "parada_nao_prevista_min": 5,
    "parado_raio_m": 30,
    "velocidade_max_kmh": 80,
    "atraso_aviso_min": 10,
    # Decisão do grupo: a emergência avisa os responsáveis (0 deixa só a gestão).
    "emergencia_avisa_responsaveis": 1,
    "crianca_a_bordo_min": 15,
    "recebimento_escola_min": 15,
}


# Faixa aceita para cada chave. Sem ela, `sem_sinal_s = 1e9` desligaria a regra sem ninguém
# perceber, e um prazo de guarda zero apagaria todas as viagens no próximo ciclo do worker.
FAIXAS: dict[str, tuple[float, float]] = {
    "viagem_nao_iniciada_min": (1, 120),
    "sem_sinal_s": (30, 1800),
    "desvio_max_m": (50, 5000),
    "parada_nao_prevista_min": (1, 60),
    "parado_raio_m": (5, 500),
    "velocidade_max_kmh": (20, 150),
    "atraso_aviso_min": (1, 120),
    "emergencia_avisa_responsaveis": (0, 1),
    "crianca_a_bordo_min": (5, 60),
    "recebimento_escola_min": (5, 120),
    "retencao_posicoes_dias": (7, 3650),
    "retencao_dados_dias": (7, 3650),
    "retencao_auditoria_dias": (7, 3650),
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
    """None = o ônibus nunca enviou. Redis fora do ar levanta erro e a regra é pulada: sem o
    Redis não dá para saber se há sinal, e abrir "sem sinal" para toda a frota seria falso."""
    return tempo_real.ler_posicao(viagem_id)


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


# Criança possivelmente esquecida a bordo (crítico)

_ESQUECIDA = text(
    """
    SELECT
        (SELECT count(*) FROM viagem_aluno
         WHERE viagem_id = :v AND status = 'embarcou') AS a_bordo,
        (SELECT max(registrada_em) FROM posicao WHERE viagem_id = :v) AS ultima_posicao,
        u.horario_previsto AS ultimo_horario,
        ST_DWithin(u.localizacao::geography, e.localizacao::geography, e.raio_cerca_m)
            AS ultima_na_escola
    FROM escola e
    LEFT JOIN LATERAL (
        SELECT horario_previsto, localizacao FROM viagem_parada
        WHERE viagem_id = :v AND horario_previsto IS NOT NULL
        ORDER BY ordem DESC LIMIT 1
    ) u ON true
    WHERE e.id = :escola
    """
)


def crianca_a_bordo(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    """Criança em `embarcou` e o ônibus sem sinal, ou já passada a hora da última parada.

    É o caso do celular desligado depois de chegar à escola: sem posição, a saída da cerca não
    dispara, e sem o motorista tentar concluir, a R2 também não. Lê a última posição do banco,
    não do Redis, para continuar valendo com o Redis fora do ar.
    """
    fuso = ZoneInfo(settings.fuso_horario)
    tolerancia = timedelta(minutes=lim["crianca_a_bordo_min"])
    criados = []
    for viagem in _em_andamento(db):
        r = db.execute(_ESQUECIDA, {"v": viagem.id, "escola": viagem.escola_id}).one()
        if not r.a_bordo:
            continue
        ultima = r.ultima_posicao or viagem.iniciada_em or agora
        sem_sinal_ha = agora - ultima
        atrasada = False
        # Na ida, a hora da última parada só vale se ela for a escola: se for a última coleta,
        # as crianças seguem a bordo até a escola, e o alerta seria falso em toda viagem.
        horario_vale = r.ultimo_horario is not None and (
            viagem.sentido.value != "ida" or r.ultima_na_escola
        )
        if horario_vale:
            # Na data da viagem, não na de hoje: a viagem pode ter ficado aberta desde ontem.
            previsto = datetime.combine(viagem.data, r.ultimo_horario, tzinfo=fuso)
            atrasada = agora - previsto > tolerancia
        if sem_sinal_ha <= tolerancia and not atrasada:
            continue
        motivo = (
            f"sem sinal há {int(sem_sinal_ha.total_seconds() // 60)} min"
            if sem_sinal_ha > tolerancia
            else f"passou da hora prevista da última parada ({r.ultimo_horario:%H:%M})"
        )
        alerta = _abrir(
            db,
            viagem,
            "crianca_a_bordo_sem_confirmacao",
            Severidade.CRITICO,
            f"{r.a_bordo} criança(s) ainda constam a bordo e o ônibus está {motivo}",
            {
                "a_bordo": r.a_bordo,
                "segundos_sem_sinal": round(sem_sinal_ha.total_seconds()),
                "passou_da_ultima_parada": atrasada,
                "limite_min": lim["crianca_a_bordo_min"],
            },
        )
        if alerta:
            criados.append(alerta)
    return criados


# Criança que desceu na escola sem a escola confirmar o recebimento (crítico)

TIPO_NAO_RECEBIDO = "crianca_nao_recebida_pela_escola"


def pendentes_de_recebimento(db: Session, viagem_id: int) -> list[tuple[int, datetime]]:
    """(estudante, hora em que o servidor recebeu o desembarque) de quem desceu na escola e
    ainda não teve o recebimento confirmado. A hora do servidor, e não a do aparelho: um
    desembarque que chega atrasado do modo offline não pode disparar o alerta na hora."""
    desceu_em = (
        select(EventoViagem.estudante_id, func.max(EventoViagem.recebido_em).label("em"))
        .where(EventoViagem.viagem_id == viagem_id, EventoViagem.tipo == TipoEvento.DESEMBARQUE)
        .group_by(EventoViagem.estudante_id)
        .subquery()
    )
    return [
        (estudante_id, em)
        for estudante_id, em in db.execute(
            select(ViagemAluno.estudante_id, desceu_em.c.em)
            .join(desceu_em, desceu_em.c.estudante_id == ViagemAluno.estudante_id)
            .where(
                ViagemAluno.viagem_id == viagem_id,
                ViagemAluno.status == StatusAluno.DESEMBARCOU,
                ViagemAluno.recebido_em.is_(None),
            )
        )
    ]


def nao_recebido_pela_escola(db: Session, agora: datetime, lim: dict) -> list[Alerta]:
    """Na ida, a criança desceu na escola e ninguém da escola confirmou que a recebeu dentro do
    prazo. Vale também com a viagem já concluída: o motorista vai embora e a criança pode não
    ter entrado. Resolve sozinho quando a escola confirma todas."""
    prazo = timedelta(minutes=lim["recebimento_escola_min"])
    hoje = agora.astimezone(ZoneInfo(settings.fuso_horario)).date()
    viagens = db.scalars(
        select(Viagem)
        .join(Escola, Escola.id == Viagem.escola_id)
        .where(
            Viagem.sentido == Sentido.IDA,
            Viagem.data == hoje,
            Viagem.status.in_([StatusViagem.EM_ANDAMENTO, StatusViagem.CONCLUIDA]),
            Escola.confirma_recebimento.is_(True),
        )
    )
    criados = []
    for viagem in viagens:
        pendentes = pendentes_de_recebimento(db, viagem.id)
        atrasados = [e for e, em in pendentes if agora - em > prazo]
        aberto = _aberto(db, viagem.id, TIPO_NAO_RECEBIDO)
        if not pendentes and aberto is not None:
            _resolver_sozinho(db, aberto, agora)
            continue
        if not atrasados:
            continue
        alerta = _abrir(
            db,
            viagem,
            TIPO_NAO_RECEBIDO,
            Severidade.CRITICO,
            f"{len(atrasados)} criança(s) desceram na escola há mais de "
            f"{int(lim['recebimento_escola_min'])} min e a escola não confirmou o recebimento",
            {"estudante_ids": atrasados, "limite_min": lim["recebimento_escola_min"]},
        )
        if alerta:
            # A gestão já recebe o push do alerta crítico; a escola é quem pode ir conferir.
            notificacoes.para_equipe_da_escola(
                db,
                viagem.escola_id,
                "confirmar_recebimento",
                "Confirme o recebimento",
                f"{len(atrasados)} criança(s) desceram do ônibus e o recebimento ainda não foi "
                "confirmado. Confira e confirme no app.",
                viagem_id=viagem.id,
            )
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
                    # Ausência avisada depois da saída: os pais já sabem que a criança não vai.
                    ViagemAluno.ausencia_avisada_em.is_(None),
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


# A crítica vem primeiro: uma falha nas outras não pode atrasá-la.
REGRAS = (
    crianca_a_bordo,
    nao_recebido_pela_escola,
    viagem_nao_iniciada,
    sem_sinal,
    desvio_de_rota,
    parada_nao_prevista,
    velocidade_excessiva,
)


def executar_regras(db: Session, agora: datetime | None = None) -> list[Alerta]:
    """Roda todas as regras. Devolve os alertas abertos nesta execução."""
    agora = agora or datetime.now(UTC)
    # Duas instâncias do worker não rodam as regras ao mesmo tempo (evita alerta duplicado).
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(7001)")):
        return []
    lim = limites(db)
    criados: list[Alerta] = []
    for regra in (*REGRAS, avisar_atraso):
        # Cada regra no próprio savepoint: um erro numa delas não leva as outras nem o que elas
        # já abriram. Redis fora do ar só pula a regra que depende dele.
        try:
            with db.begin_nested():
                resultado = regra(db, agora, lim)
        except redis.RedisError:
            continue
        except Exception:
            log.exception("falha na regra %s", regra.__name__)
            continue
        if isinstance(resultado, list):
            criados += resultado
    db.flush()
    return criados
