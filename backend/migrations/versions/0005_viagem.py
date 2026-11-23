"""Viagem do dia, lista, eventos imutáveis, alertas e avisos.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM('agendada', 'em_andamento', 'concluida', 'cancelada', name='status_viagem').create(op.get_bind())
    postgresql.ENUM('aguardando', 'embarcou', 'desembarcou', 'nao_embarcou', 'ausencia_avisada', name='status_aluno').create(op.get_bind())
    postgresql.ENUM('embarque', 'nao_embarcou', 'desembarque', 'embarque_fora_da_lista', 'onibus_vazio', 'correcao', name='tipo_evento').create(op.get_bind())
    postgresql.ENUM('critico', 'aviso', name='severidade').create(op.get_bind())
    op.create_table('viagem',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rota_id', sa.Integer(), nullable=False),
    sa.Column('data', sa.Date(), nullable=False),
    sa.Column('turno', postgresql.ENUM('manha', 'tarde', 'integral', name='turno', create_type=False), nullable=False),
    sa.Column('sentido', postgresql.ENUM('ida', 'volta', name='sentido', create_type=False), nullable=False),
    sa.Column('escola_id', sa.Integer(), nullable=False),
    sa.Column('veiculo_id', sa.Integer(), nullable=True),
    sa.Column('motorista_id', sa.Integer(), nullable=True),
    sa.Column('monitor_id', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('agendada', 'em_andamento', 'concluida', 'cancelada', name='status_viagem', create_type=False), nullable=False),
    sa.Column('iniciada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('concluida_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelada_por_id', sa.Integer(), nullable=True),
    sa.Column('motivo_cancelamento', sa.String(), nullable=True),
    sa.Column('dentro_da_cerca_escola', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.ForeignKeyConstraint(['cancelada_por_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['escola_id'], ['escola.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['monitor_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['motorista_id'], ['motorista.usuario_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['rota_id'], ['rota.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('rota_id', 'data')
    )
    op.create_index(op.f('ix_viagem_data'), 'viagem', ['data'], unique=False)
    op.create_index(op.f('ix_viagem_rota_id'), 'viagem', ['rota_id'], unique=False)
    op.create_table('alerta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('viagem_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.String(), nullable=False),
    sa.Column('severidade', postgresql.ENUM('critico', 'aviso', name='severidade', create_type=False), nullable=False),
    sa.Column('mensagem', sa.String(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolvido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolvido_por_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['resolvido_por_id'], ['usuario.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerta_tipo'), 'alerta', ['tipo'], unique=False)
    op.create_index(op.f('ix_alerta_viagem_id'), 'alerta', ['viagem_id'], unique=False)
    op.create_table('aviso',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('viagem_id', sa.Integer(), nullable=True),
    sa.Column('estudante_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.String(), nullable=False),
    sa.Column('mensagem', sa.String(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lido_em', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['estudante_id'], ['estudante.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_aviso_usuario_id'), 'aviso', ['usuario_id'], unique=False)
    op.create_geospatial_table('evento_viagem',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('viagem_id', sa.Integer(), nullable=False),
    sa.Column('tipo', postgresql.ENUM('embarque', 'nao_embarcou', 'desembarque', 'embarque_fora_da_lista', 'onibus_vazio', 'correcao', name='tipo_evento', create_type=False), nullable=False),
    sa.Column('estudante_id', sa.Integer(), nullable=True),
    sa.Column('parada_id', sa.Integer(), nullable=True),
    sa.Column('hora_aparelho', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recebido_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('justificativa', sa.String(), nullable=True),
    sa.Column('status_corrigido', postgresql.ENUM('aguardando', 'embarcou', 'desembarcou', 'nao_embarcou', 'ausencia_avisada', name='status_aluno', create_type=False), nullable=True),
    sa.Column('anomalia', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['autor_id'], ['usuario.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['estudante_id'], ['estudante.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_evento_viagem_localizacao', 'evento_viagem', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_evento_viagem_viagem_id'), 'evento_viagem', ['viagem_id'], unique=False)
    op.create_geospatial_table('viagem_parada',
    sa.Column('viagem_id', sa.Integer(), nullable=False),
    sa.Column('parada_id', sa.Integer(), nullable=False),
    sa.Column('localizacao', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('horario_previsto', sa.Time(), nullable=True),
    sa.Column('raio_cerca_m', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('viagem_id', 'parada_id')
    )
    op.create_geospatial_index('idx_viagem_parada_localizacao', 'viagem_parada', ['localizacao'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_table('viagem_aluno',
    sa.Column('viagem_id', sa.Integer(), nullable=False),
    sa.Column('estudante_id', sa.Integer(), nullable=False),
    sa.Column('parada_id', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('aguardando', 'embarcou', 'desembarcou', 'nao_embarcou', 'ausencia_avisada', name='status_aluno', create_type=False), nullable=False),
    sa.Column('status_inicial', postgresql.ENUM('aguardando', 'embarcou', 'desembarcou', 'nao_embarcou', 'ausencia_avisada', name='status_aluno', create_type=False), nullable=False),
    sa.Column('fora_da_lista', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('ausencia_avisada_em', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['estudante_id'], ['estudante.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['viagem_id', 'parada_id'], ['viagem_parada.viagem_id', 'viagem_parada.parada_id'], ),
    sa.ForeignKeyConstraint(['viagem_id'], ['viagem.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('viagem_id', 'estudante_id')
    )
    op.create_index(op.f('ix_viagem_aluno_estudante_id'), 'viagem_aluno', ['estudante_id'], unique=False)

    # Evento de viagem não se altera nem se apaga: correção é um novo evento. O trigger vale
    # para qualquer conexão, inclusive uma que ignore a aplicação.
    op.execute(
        """
        CREATE FUNCTION evento_viagem_imutavel() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'evento_viagem é só de inclusão (% recusado)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER evento_viagem_so_inclusao
        BEFORE UPDATE OR DELETE ON evento_viagem
        FOR EACH ROW EXECUTE FUNCTION evento_viagem_imutavel()
        """
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER evento_viagem_so_inclusao ON evento_viagem')
    op.execute('DROP FUNCTION evento_viagem_imutavel()')
    op.drop_index(op.f('ix_viagem_aluno_estudante_id'), table_name='viagem_aluno')
    op.drop_table('viagem_aluno')
    op.drop_geospatial_index('idx_viagem_parada_localizacao', table_name='viagem_parada', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('viagem_parada')
    op.drop_index(op.f('ix_evento_viagem_viagem_id'), table_name='evento_viagem')
    op.drop_geospatial_index('idx_evento_viagem_localizacao', table_name='evento_viagem', postgresql_using='gist', column_name='localizacao')
    op.drop_geospatial_table('evento_viagem')
    op.drop_index(op.f('ix_aviso_usuario_id'), table_name='aviso')
    op.drop_table('aviso')
    op.drop_index(op.f('ix_alerta_viagem_id'), table_name='alerta')
    op.drop_index(op.f('ix_alerta_tipo'), table_name='alerta')
    op.drop_table('alerta')
    op.drop_index(op.f('ix_viagem_rota_id'), table_name='viagem')
    op.drop_index(op.f('ix_viagem_data'), table_name='viagem')
    op.drop_table('viagem')
    for tipo in ('severidade', 'tipo_evento', 'status_aluno', 'status_viagem'):
        op.execute(f'DROP TYPE {tipo}')
