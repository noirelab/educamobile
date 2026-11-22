"""sessoes, auditoria e vinculo com responsaveis

Revision ID: 1f4edce61005
Revises: c3c6417735ae
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

revision = '1f4edce61005'
down_revision = 'c3c6417735ae'
branch_labels = None
depends_on = None


NOVOS_PERFIS = ("gestor", "motorista", "monitor", "responsavel")


def upgrade() -> None:
    # O autogenerate não detecta valores novos em enum do Postgres.
    for perfil in NOVOS_PERFIS:
        op.execute(f"ALTER TYPE perfil ADD VALUE IF NOT EXISTS '{perfil}'")
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
    op.add_column('usuario', sa.Column('sessoes_validas_desde', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))


def downgrade() -> None:
    # O Postgres não remove valores de enum; os perfis novos ficam no tipo, sem uso.
    op.execute(
        "DELETE FROM usuario WHERE perfil IN ('gestor', 'motorista', 'monitor', 'responsavel')"
    )
    op.drop_column('usuario', 'sessoes_validas_desde')
    op.drop_index(op.f('ix_sessao_usuario_id'), table_name='sessao')
    op.drop_table('sessao')
    op.drop_index(op.f('ix_responsavel_estudante_estudante_id'), table_name='responsavel_estudante')
    op.drop_table('responsavel_estudante')
    op.drop_index(op.f('ix_auditoria_usuario_id'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_em'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_acao'), table_name='auditoria')
    op.drop_table('auditoria')
