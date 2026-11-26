"""estudante com dados minimos

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sem dados reais em produção (ver issue #2). Se houver estudantes, escola_id e turno
    # NOT NULL fazem a migração falhar em vez de inventar valores para crianças.
    turno = postgresql.ENUM("manha", "tarde", "integral", name="turno")
    turno.create(op.get_bind())
    op.add_column("estudante", sa.Column("escola_id", sa.Integer(), nullable=False))
    op.add_column("estudante", sa.Column("turno", turno, nullable=False))
    op.add_column("estudante", sa.Column("observacoes_cuidado", sa.String(), nullable=True))
    op.add_column("estudante", sa.Column("foto_arquivo", sa.String(), nullable=True))
    op.drop_geospatial_index(
        "idx_estudante_localizacao",
        table_name="estudante",
        postgresql_using="gist",
        column_name="localizacao",
    )
    op.create_index(op.f("ix_estudante_escola_id"), "estudante", ["escola_id"], unique=False)
    op.create_foreign_key(
        "estudante_escola_id_fkey", "estudante", "escola", ["escola_id"], ["id"], ondelete="RESTRICT"
    )
    op.drop_column("estudante", "nome_responsavel")
    op.drop_geospatial_column("estudante", "localizacao")


def downgrade() -> None:
    op.add_geospatial_column(
        "estudante",
        sa.Column(
            "localizacao",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
    )
    op.add_column("estudante", sa.Column("nome_responsavel", sa.String(), nullable=True))
    op.drop_constraint("estudante_escola_id_fkey", "estudante", type_="foreignkey")
    op.drop_index(op.f("ix_estudante_escola_id"), table_name="estudante")
    op.create_geospatial_index(
        "idx_estudante_localizacao",
        "estudante",
        ["localizacao"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.drop_column("estudante", "foto_arquivo")
    op.drop_column("estudante", "observacoes_cuidado")
    op.drop_column("estudante", "turno")
    op.drop_column("estudante", "escola_id")
    op.execute("DROP TYPE turno")
