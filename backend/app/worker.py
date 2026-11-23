"""Processo do worker: regras de alerta no tempo e envio das notificações.

    python -m app.worker

Roda em loop: acorda por mensagem no Redis (uma emergência, por exemplo) ou a cada ciclo. As
regras rodam no intervalo configurado; o envio de push roda a cada despertar. Mais de um worker
pode rodar ao mesmo tempo: o envio usa `SKIP LOCKED`, e cada regra abre um alerta só.
"""

import logging
import time

import redis

from app import alertas, notificacoes, tempo_real
from app.db import SessionLocal

log = logging.getLogger("worker")
CICLO_S = 5
REGRAS_A_CADA_S = 15


def ciclo(enviador: notificacoes.Enviador, rodar_regras: bool) -> None:
    with SessionLocal() as db:
        if rodar_regras:
            alertas.executar_regras(db)
        notificacoes.enviar_pendentes(db, enviador)
        db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    enviador = notificacoes.obter_enviador()
    log.info("worker iniciado (%s)", type(enviador).__name__)
    ultima_regra = 0.0
    while True:
        try:
            agora = time.monotonic()
            rodar = agora - ultima_regra >= REGRAS_A_CADA_S
            if rodar:
                ultima_regra = agora
            ciclo(enviador, rodar)
        except Exception:
            log.exception("falha no ciclo do worker")
        try:
            tempo_real.cliente().blpop([tempo_real.WORKER_ACORDAR], timeout=CICLO_S)
        except redis.RedisError:
            time.sleep(CICLO_S)


if __name__ == "__main__":
    main()
