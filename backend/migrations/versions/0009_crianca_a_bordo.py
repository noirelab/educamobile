"""Limite da regra crítica de criança a bordo sem confirmação.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tabela = sa.table(
        "configuracao",
        sa.column("chave", sa.String),
        sa.column("valor", sa.Double),
        sa.column("descricao", sa.String),
    )
    op.bulk_insert(
        tabela,
        [
            {
                "chave": "crianca_a_bordo_min",
                "valor": 15,
                "descricao": "Alerta crítico: minutos sem sinal, ou depois da hora da última "
                "parada, com criança ainda a bordo",
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM configuracao WHERE chave = 'crianca_a_bordo_min'")
