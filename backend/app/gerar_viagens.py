"""Geração diária das viagens. Rode por agendador (cron) antes do primeiro turno.

    python -m app.gerar_viagens            # hoje
    python -m app.gerar_viagens 2026-11-24  # outra data

Repetir é seguro: a viagem de uma rota num dia é única. O processo do worker (etapa E) passa a
chamar `viagens.gerar` por conta própria.
"""

import sys
from datetime import date

from app import viagens
from app.db import SessionLocal


def main() -> None:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    with SessionLocal() as db:
        criadas = viagens.gerar(db, dia)
        db.commit()
        print(f"{len(criadas)} viagem(ns) para {dia.isoformat()}")


if __name__ == "__main__":
    main()
