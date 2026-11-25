"""Geração das viagens de um dia, à mão. O worker já gera as do dia sozinho, na virada da data.

    python -m app.gerar_viagens            # hoje, no fuso da escola
    python -m app.gerar_viagens 2026-11-24  # outra data

Repetir é seguro: a viagem de uma rota num dia é única.
"""

import sys
from datetime import date

from app import tempo, viagens
from app.db import SessionLocal


def main() -> None:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else tempo.hoje()
    with SessionLocal() as db:
        criadas = viagens.gerar(db, dia)
        db.commit()
        print(f"{len(criadas)} viagem(ns) para {dia.isoformat()}")


if __name__ == "__main__":
    main()
