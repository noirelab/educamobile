"""Posições do ônibus, token do rastreador e chegada e partida nas paradas.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_geospatial_table('posicao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('viagem_id', sa.Integer(), nullable=False),
    sa.Column('registrada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recebida_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('velocidade_kmh', sa.Double(), nullable=True),
    sa.Column('precisao_m', sa.Double(), nullable=True),
    sa.Column('fonte', sa.String(), server_default=sa.text("'aparelho'"), nullable=False),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('viagem_id', 'registrada_em')
    )
    op.create_geospatial_index('idx_posicao_localizacao', 'posicao', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index('ix_posicao_viagem_registrada', 'posicao', ['viagem_id', 'registrada_em'], unique=False)
    op.add_column('veiculo', sa.Column('token_rastreador_hash', sa.String(), nullable=True))
    op.create_unique_constraint('veiculo_token_rastreador_hash_key', 'veiculo', ['token_rastreador_hash'])
    op.add_column('viagem_parada', sa.Column('chegada_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('viagem_parada', sa.Column('partida_em', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('viagem_parada', 'partida_em')
    op.drop_column('viagem_parada', 'chegada_em')
    op.drop_constraint('veiculo_token_rastreador_hash_key', 'veiculo', type_='unique')
    op.drop_column('veiculo', 'token_rastreador_hash')
    op.drop_index('ix_posicao_viagem_registrada', table_name='posicao')
    op.drop_geospatial_index('idx_posicao_localizacao', table_name='posicao', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('posicao')
