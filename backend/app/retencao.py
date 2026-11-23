"""Prazo de guarda dos dados (LGPD, art. 14). Rodado pelo worker, uma vez por hora.

Posições brutas saem em 90 dias. Viagens e tudo que depende delas (lista, eventos, alertas,
notificações, ausências) saem no prazo definido com a secretaria; o registro de auditoria fica
mais tempo porque é a prova de quem viu o quê. Os prazos moram na tabela `configuracao`.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.alertas import limites
from app.models import Auditoria, Ausencia, Notificacao, Posicao, Viagem

PADRAO = {"retencao_posicoes_dias": 90, "retencao_dados_dias": 365, "retencao_auditoria_dias": 730}


def executar(db: Session, agora: datetime | None = None) -> dict[str, int]:
    """Apaga o que passou do prazo e devolve quantas linhas saíram de cada tabela."""
    agora = agora or datetime.now(UTC)
    lim = {**PADRAO, **{k: v for k, v in limites(db).items() if k in PADRAO}}
    corte_posicoes = agora - timedelta(days=lim["retencao_posicoes_dias"])
    corte_dados = agora - timedelta(days=lim["retencao_dados_dias"])
    corte_auditoria = agora - timedelta(days=lim["retencao_auditoria_dias"])
    saiu: dict[str, int] = {}

    saiu["posicao"] = db.execute(
        delete(Posicao).where(Posicao.registrada_em < corte_posicoes)
    ).rowcount

    # Eventos de viagem só se apagam com a declaração explícita da rotina de retenção.
    db.execute(text("SET LOCAL app.retencao = 'on'"))
    viagens_velhas = select(Viagem.id).where(Viagem.data < corte_dados.date())
    saiu["evento_viagem"] = db.execute(
        text(
            "DELETE FROM evento_viagem WHERE viagem_id IN (SELECT id FROM viagem WHERE data < :d)"
        ),
        {"d": corte_dados.date()},
    ).rowcount
    saiu["viagem"] = db.execute(delete(Viagem).where(Viagem.id.in_(viagens_velhas))).rowcount
    db.execute(text("RESET app.retencao"))

    saiu["ausencia"] = db.execute(
        delete(Ausencia).where(Ausencia.data < corte_dados.date())
    ).rowcount
    saiu["notificacao"] = db.execute(
        delete(Notificacao).where(Notificacao.criado_em < corte_dados)
    ).rowcount
    saiu["auditoria"] = db.execute(delete(Auditoria).where(Auditoria.em < corte_auditoria)).rowcount
    db.flush()
    return saiu
