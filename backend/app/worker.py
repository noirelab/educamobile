"""Processo do worker: regras de alerta no tempo e envio das notificações.

    python -m app.worker

Roda em loop: acorda por mensagem no Redis (uma emergência, por exemplo) ou a cada ciclo. As
regras rodam no intervalo configurado; o envio de push roda a cada despertar. As viagens do dia
são geradas quando o worker sobe, na virada de data no fuso da escola e a cada 5 minutos. Mais
de um worker pode rodar ao mesmo tempo: o envio usa `SKIP LOCKED`, cada regra abre um alerta só
e a viagem de uma rota num dia é única.
"""

import logging
import time
from datetime import date

import redis

from app import alertas, notificacoes, retencao, sessoes, tempo, tempo_real, viagens
from app.db import SessionLocal

log = logging.getLogger("worker")
CICLO_S = 5
REGRAS_A_CADA_S = 15
MANUTENCAO_A_CADA_S = 3600
# Repetir a geração pega a rota que ganhou o primeiro inscrito depois da virada do dia.
GERAR_A_CADA_S = 300


def ciclo(enviador: notificacoes.Enviador, rodar_regras: bool) -> None:
    # Transações separadas: uma falha no envio do push não pode jogar fora os alertas já abertos.
    if rodar_regras:
        try:
            with SessionLocal() as db:
                alertas.executar_regras(db)
                db.commit()
        except Exception:
            # O push (inclusive o da emergência) sai mesmo que as regras falhem.
            log.exception("falha nas regras de alerta")
    with SessionLocal() as db:
        notificacoes.enviar_pendentes(db, enviador)
        db.commit()


def gerar_viagens(dia: date) -> None:
    with SessionLocal() as db:
        criadas = viagens.gerar(db, dia)
        db.commit()
    log.info("%s viagem(ns) no dia %s", len(criadas), dia.isoformat())


def manutencao() -> None:
    """Limpezas de rotina: sessões antigas e prazos de guarda (LGPD)."""
    with SessionLocal() as db:
        apagadas = sessoes.limpar_antigas(db)
        saiu = retencao.executar(db)
        db.commit()
    log.info("manutenção: %s sessões antigas; retenção: %s", apagadas, saiu)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    enviador = notificacoes.obter_enviador()
    log.info("worker iniciado (%s)", type(enviador).__name__)
    ultima_regra = 0.0
    ultima_manutencao = float("-inf")
    dia_gerado: date | None = None
    ultima_geracao = float("-inf")
    while True:
        hoje = tempo.hoje()
        if hoje != dia_gerado or time.monotonic() - ultima_geracao >= GERAR_A_CADA_S:
            ultima_geracao = time.monotonic()
            # Falha aqui tenta de novo no próximo ciclo, sem segurar as regras de alerta.
            try:
                gerar_viagens(hoje)
                dia_gerado = hoje
            except Exception:
                log.exception("falha ao gerar as viagens de %s", hoje)
        try:
            agora = time.monotonic()
            rodar = agora - ultima_regra >= REGRAS_A_CADA_S
            if rodar:
                ultima_regra = agora
            ciclo(enviador, rodar)
            if agora - ultima_manutencao >= MANUTENCAO_A_CADA_S:
                ultima_manutencao = agora
                manutencao()
        except Exception:
            log.exception("falha no ciclo do worker")
        try:
            tempo_real.cliente().blpop([tempo_real.WORKER_ACORDAR], timeout=CICLO_S)
        except redis.RedisError:
            time.sleep(CICLO_S)


if __name__ == "__main__":
    main()
