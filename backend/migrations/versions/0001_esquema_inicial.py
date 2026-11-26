"""Esquema inicial do transporte escolar seguro.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_geospatial_table('escola',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('codigo_inep', sa.String(), nullable=True),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('endereco', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo_inep')
    )
    op.create_geospatial_index('idx_escola_localizacao', 'escola', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_geospatial_table('parada',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_parada_localizacao', 'parada', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_geospatial_table('rota',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('trajeto', Geometry(geometry_type='LINESTRING', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
    sa.Column('distancia_m', sa.Double(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nome')
    )
    op.create_geospatial_index('idx_rota_trajeto', 'rota', ['trajeto'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('senha_hash', sa.String(), nullable=False),
    sa.Column('perfil', sa.Enum('admin', 'gestor', 'motorista', 'monitor', 'responsavel', name='perfil'), nullable=False),
    sa.Column('ativo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('sessoes_validas_desde', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('auditoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('acao', sa.String(), nullable=False),
    sa.Column('recurso', sa.String(), nullable=True),
    sa.Column('recurso_id', sa.String(), nullable=True),
    sa.Column('ip', postgresql.INET(), nullable=True),
    sa.Column('detalhes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auditoria_acao'), 'auditoria', ['acao'], unique=False)
    op.create_index(op.f('ix_auditoria_em'), 'auditoria', ['em'], unique=False)
    op.create_index(op.f('ix_auditoria_usuario_id'), 'auditoria', ['usuario_id'], unique=False)
    op.create_geospatial_table('estudante',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('data_nascimento', sa.Date(), nullable=False),
    sa.Column('nome_responsavel', sa.String(), nullable=True),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
    sa.Column('parada_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parada_id'], ['parada.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_estudante_localizacao', 'estudante', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_estudante_parada_id'), 'estudante', ['parada_id'], unique=False)
    op.create_table('rota_parada',
    sa.Column('rota_id', sa.Integer(), nullable=False),
    sa.Column('parada_id', sa.Integer(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['parada_id'], ['parada.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['rota_id'], ['rota.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('rota_id', 'parada_id'),
    sa.UniqueConstraint('rota_id', 'ordem')
    )
    op.create_table('sessao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('criada_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expira_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revogada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('substituida_por_id', sa.Integer(), nullable=True),
    sa.Column('ip', postgresql.INET(), nullable=True),
    sa.Column('user_agent', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['substituida_por_id'], ['sessao.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_sessao_usuario_id'), 'sessao', ['usuario_id'], unique=False)
    op.create_table('responsavel_estudante',
    sa.Column('responsavel_id', sa.Integer(), nullable=False),
    sa.Column('estudante_id', sa.Integer(), nullable=False),
    sa.Column('parentesco', sa.String(), nullable=False),
    sa.Column('principal', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('consentimento_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consentimento_versao', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['estudante_id'], ['estudante.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['responsavel_id'], ['usuario.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('responsavel_id', 'estudante_id')
    )
    op.create_index(op.f('ix_responsavel_estudante_estudante_id'), 'responsavel_estudante', ['estudante_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_responsavel_estudante_estudante_id'), table_name='responsavel_estudante')
    op.drop_table('responsavel_estudante')
    op.drop_index(op.f('ix_sessao_usuario_id'), table_name='sessao')
    op.drop_table('sessao')
    op.drop_table('rota_parada')
    op.drop_index(op.f('ix_estudante_parada_id'), table_name='estudante')
    op.drop_geospatial_index('idx_estudante_localizacao', table_name='estudante', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('estudante')
    op.drop_index(op.f('ix_auditoria_usuario_id'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_em'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_acao'), table_name='auditoria')
    op.drop_table('auditoria')
    op.drop_table('usuario')
    op.drop_geospatial_index('idx_rota_trajeto', table_name='rota', postgresql_using='gist', column_name='trajeto')
    op.drop_geospatial_table('rota')
    op.drop_geospatial_index('idx_parada_localizacao', table_name='parada', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('parada')
    op.drop_geospatial_index('idx_escola_localizacao', table_name='escola', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('escola')
    op.execute("DROP TYPE perfil")
