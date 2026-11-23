"""Alertas com reconhecimento, notificações com envio, dispositivos e configuração.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# (chave, valor, descrição). Os limites das regras de alerta não ficam no código.
PADROES = [
    ("viagem_nao_iniciada_min", 10, "R6: minutos após o horário da 1ª parada sem a viagem iniciar"),
    ("sem_sinal_s", 120, "R7: segundos sem posição para considerar o ônibus sem sinal"),
    ("desvio_max_m", 300, "R8: distância máxima do trajeto previsto, em metros"),
    ("parada_nao_prevista_min", 5, "R9: minutos parado fora de qualquer parada e da escola"),
    ("parado_raio_m", 30, "R9: raio em que o ônibus conta como parado no mesmo lugar"),
    ("velocidade_max_kmh", 80, "R10: velocidade acima da qual se alerta"),
    ("atraso_aviso_min", 10, "Atraso, em minutos, a partir do qual os responsáveis são avisados"),
    ("emergencia_avisa_responsaveis", 0, "1 avisa os responsáveis numa emergência; 0 só a gestão"),
]


def upgrade() -> None:
    op.rename_table("aviso", "notificacao")
    op.execute("ALTER INDEX ix_aviso_usuario_id RENAME TO ix_notificacao_usuario_id")
    op.add_column(
        "notificacao", sa.Column("titulo", sa.String(), server_default="", nullable=False)
    )
    op.alter_column("notificacao", "titulo", server_default=None)
    op.add_column("notificacao", sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "notificacao",
        sa.Column("tentativas", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "notificacao", sa.Column("proxima_tentativa_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("notificacao", sa.Column("erro", sa.String(), nullable=True))

    op.add_column("alerta", sa.Column("reconhecido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerta", sa.Column("reconhecido_por_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "alerta_reconhecido_por_id_fkey",
        "alerta",
        "usuario",
        ["reconhecido_por_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "alerta",
        sa.Column(
            "resolvido_automaticamente", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column("alerta", sa.Column("dados", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table(
        "configuracao",
        sa.Column("chave", sa.String(), nullable=False),
        sa.Column("valor", sa.Double(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("chave"),
    )
    tabela = sa.table(
        "configuracao",
        sa.column("chave", sa.String),
        sa.column("valor", sa.Double),
        sa.column("descricao", sa.String),
    )
    op.bulk_insert(tabela, [{"chave": c, "valor": v, "descricao": d} for c, v, d in PADROES])

    op.create_table(
        "dispositivo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("plataforma", sa.String(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_dispositivo_usuario_id"), "dispositivo", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dispositivo_usuario_id"), table_name="dispositivo")
    op.drop_table("dispositivo")
    op.drop_table("configuracao")
    for coluna in ("dados", "resolvido_automaticamente", "reconhecido_por_id", "reconhecido_em"):
        if coluna == "reconhecido_por_id":
            op.drop_constraint("alerta_reconhecido_por_id_fkey", "alerta", type_="foreignkey")
        op.drop_column("alerta", coluna)
    for coluna in ("erro", "proxima_tentativa_em", "tentativas", "enviada_em", "titulo"):
        op.drop_column("notificacao", coluna)
    op.execute("ALTER INDEX ix_notificacao_usuario_id RENAME TO ix_aviso_usuario_id")
    op.rename_table("notificacao", "aviso")
