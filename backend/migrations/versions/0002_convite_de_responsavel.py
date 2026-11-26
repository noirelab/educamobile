"""convite de responsavel

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('convite',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo_hash', sa.String(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('estudante_id', sa.Integer(), nullable=False),
    sa.Column('parentesco', sa.String(), nullable=False),
    sa.Column('principal', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('expira_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('usado_em', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['estudante_id'], ['estudante.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo_hash')
    )
    op.create_index(op.f('ix_convite_email'), 'convite', ['email'], unique=False)
    op.create_index(op.f('ix_convite_estudante_id'), 'convite', ['estudante_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_convite_estudante_id'), table_name='convite')
    op.drop_index(op.f('ix_convite_email'), table_name='convite')
    op.drop_table('convite')
