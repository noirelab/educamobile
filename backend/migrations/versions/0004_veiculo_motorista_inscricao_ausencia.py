"""Veículo, motorista, inscrição, ausência e os campos de rota e cerca.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sentido = postgresql.ENUM("ida", "volta", name="sentido")
    sentido.create(op.get_bind())
    sentido_col = postgresql.ENUM("ida", "volta", name="sentido", create_type=False)
    turno_col = postgresql.ENUM("manha", "tarde", "integral", name="turno", create_type=False)

    op.create_table(
        "veiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("capacidade", sa.Integer(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("vistoria_valida_ate", sa.Date(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("ano BETWEEN 1980 AND 2100", name="ck_veiculo_ano"),
        sa.CheckConstraint("capacidade > 0", name="ck_veiculo_capacidade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("placa"),
    )
    op.create_table(
        "motorista",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cnh", sa.String(), nullable=False),
        sa.Column("categoria_cnh", sa.String(), nullable=False),
        sa.Column("cnh_valida_ate", sa.Date(), nullable=False),
        sa.Column("curso_transporte_escolar_ate", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id"),
        sa.UniqueConstraint("cnh"),
    )
    op.create_table(
        "ausencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estudante_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("sentido", sentido_col, nullable=True),
        sa.Column("criada_por_id", sa.Integer(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["criada_por_id"], ["usuario.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["estudante_id"], ["estudante.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("estudante_id", "data", "sentido"),
    )
    op.create_index(op.f("ix_ausencia_data"), "ausencia", ["data"], unique=False)
    op.create_index(op.f("ix_ausencia_estudante_id"), "ausencia", ["estudante_id"], unique=False)

    op.add_column(
        "escola", sa.Column("raio_cerca_m", sa.Integer(), server_default=sa.text("150"), nullable=False)
    )
    # Sem dados reais: se houver rotas, escola_id, turno e sentido NOT NULL fazem a migração falhar.
    op.add_column("rota", sa.Column("escola_id", sa.Integer(), nullable=False))
    op.add_column("rota", sa.Column("turno", turno_col, nullable=False))
    op.add_column("rota", sa.Column("sentido", sentido_col, nullable=False))
    op.add_column("rota", sa.Column("veiculo_id", sa.Integer(), nullable=True))
    op.add_column("rota", sa.Column("motorista_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_rota_escola_id"), "rota", ["escola_id"], unique=False)
    op.create_foreign_key("rota_escola_id_fkey", "rota", "escola", ["escola_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("rota_veiculo_id_fkey", "rota", "veiculo", ["veiculo_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "rota_motorista_id_fkey", "rota", "motorista", ["motorista_id"], ["usuario_id"], ondelete="SET NULL"
    )
    op.add_column("rota_parada", sa.Column("horario_previsto", sa.Time(), nullable=True))
    op.add_column(
        "rota_parada", sa.Column("raio_cerca_m", sa.Integer(), server_default=sa.text("50"), nullable=False)
    )

    op.create_table(
        "inscricao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estudante_id", sa.Integer(), nullable=False),
        sa.Column("rota_id", sa.Integer(), nullable=False),
        sa.Column("parada_id", sa.Integer(), nullable=False),
        sa.Column("turno", turno_col, nullable=False),
        sa.Column("sentido", sentido_col, nullable=False),
        sa.Column("dias_semana", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
        sa.Column("ativa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("cardinality(dias_semana) BETWEEN 1 AND 7", name="ck_insc_dias"),
        sa.CheckConstraint("vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio", name="ck_insc_periodo"),
        sa.ForeignKeyConstraint(["estudante_id"], ["estudante.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parada_id"], ["parada.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rota_id"], ["rota.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inscricao_estudante_id"), "inscricao", ["estudante_id"], unique=False)
    op.create_index(op.f("ix_inscricao_rota_id"), "inscricao", ["rota_id"], unique=False)
    op.create_index(
        "uq_inscricao_ativa_por_turno_e_sentido",
        "inscricao",
        ["estudante_id", "turno", "sentido"],
        unique=True,
        postgresql_where=sa.text("ativa"),
    )


def downgrade() -> None:
    op.drop_table("inscricao")
    op.drop_column("rota_parada", "raio_cerca_m")
    op.drop_column("rota_parada", "horario_previsto")
    op.drop_constraint("rota_motorista_id_fkey", "rota", type_="foreignkey")
    op.drop_constraint("rota_veiculo_id_fkey", "rota", type_="foreignkey")
    op.drop_constraint("rota_escola_id_fkey", "rota", type_="foreignkey")
    op.drop_index(op.f("ix_rota_escola_id"), table_name="rota")
    for coluna in ("motorista_id", "veiculo_id", "sentido", "turno", "escola_id"):
        op.drop_column("rota", coluna)
    op.drop_column("escola", "raio_cerca_m")
    op.drop_table("ausencia")
    op.drop_table("motorista")
    op.drop_table("veiculo")
    op.execute("DROP TYPE sentido")
