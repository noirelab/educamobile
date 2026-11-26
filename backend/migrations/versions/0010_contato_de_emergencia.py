"""Contato de emergência opcional do estudante.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estudante", sa.Column("contato_emergencia_nome", sa.String(), nullable=True))
    op.add_column(
        "estudante", sa.Column("contato_emergencia_telefone", sa.String(), nullable=True)
    )
    op.add_column(
        "estudante", sa.Column("contato_emergencia_parentesco", sa.String(), nullable=True)
    )
    op.create_check_constraint(
        "ck_estudante_contato_emergencia",
        "estudante",
        "(contato_emergencia_nome IS NULL) = (contato_emergencia_telefone IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_estudante_contato_emergencia", "estudante", type_="check")
    op.drop_column("estudante", "contato_emergencia_parentesco")
    op.drop_column("estudante", "contato_emergencia_telefone")
    op.drop_column("estudante", "contato_emergencia_nome")
