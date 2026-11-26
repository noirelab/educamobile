"""Emergência avisa os responsáveis e a escola confirma o recebimento das crianças.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O valor novo do enum precisa estar gravado antes de a constraint abaixo usá-lo.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE perfil ADD VALUE IF NOT EXISTS 'escola'")

    op.add_column(
        "escola",
        sa.Column(
            "confirma_recebimento", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.add_column("usuario", sa.Column("escola_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "usuario_escola_id_fkey", "usuario", "escola", ["escola_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_usuario_escola_id", "usuario", ["escola_id"])
    op.create_check_constraint(
        "ck_usuario_escola_do_perfil", "usuario", "(perfil = 'escola') = (escola_id IS NOT NULL)"
    )
    op.add_column(
        "viagem_aluno", sa.Column("recebido_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("viagem_aluno", sa.Column("recebido_por_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "viagem_aluno_recebido_por_id_fkey",
        "viagem_aluno",
        "usuario",
        ["recebido_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Decisão do grupo: a emergência avisa os responsáveis.
    op.execute(
        "UPDATE configuracao SET valor = 1 WHERE chave = 'emergencia_avisa_responsaveis'"
    )
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
                "chave": "recebimento_escola_min",
                "valor": 15,
                "descricao": "Alerta crítico: minutos depois do desembarque na escola sem a "
                "escola confirmar o recebimento da criança",
            }
        ],
    )


def downgrade() -> None:
    # O Postgres não remove valor de enum, e apagar contas levaria sessões e auditoria junto:
    # desative e remova os usuários do perfil escola à mão antes de voltar.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM usuario WHERE perfil = 'escola'")):
        raise RuntimeError("Existem usuários do perfil escola: remova-os antes do downgrade")
    op.execute("DELETE FROM configuracao WHERE chave = 'recebimento_escola_min'")
    op.execute(
        "UPDATE configuracao SET valor = 0 WHERE chave = 'emergencia_avisa_responsaveis'"
    )
    op.drop_constraint("viagem_aluno_recebido_por_id_fkey", "viagem_aluno", type_="foreignkey")
    op.drop_column("viagem_aluno", "recebido_por_id")
    op.drop_column("viagem_aluno", "recebido_em")
    op.drop_constraint("ck_usuario_escola_do_perfil", "usuario", type_="check")
    op.drop_index("ix_usuario_escola_id", table_name="usuario")
    op.drop_constraint("usuario_escola_id_fkey", "usuario", type_="foreignkey")
    op.drop_column("usuario", "escola_id")
    op.drop_column("escola", "confirma_recebimento")
