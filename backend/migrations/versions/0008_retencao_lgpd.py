"""Prazos de guarda (LGPD) e exclusão de eventos pela rotina de retenção.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PRAZOS = [
    ("retencao_posicoes_dias", 90, "LGPD: dias de guarda das posições brutas do ônibus"),
    ("retencao_dados_dias", 365, "LGPD: dias de guarda de viagens, eventos, alertas e avisos (a confirmar com a secretaria)"),
    ("retencao_auditoria_dias", 730, "LGPD: dias de guarda do registro de auditoria"),
]


def upgrade() -> None:
    # A imutabilidade continua valendo para qualquer conexão. A única exceção é a rotina de
    # retenção, que declara `SET LOCAL app.retencao = 'on'` na própria transação.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evento_viagem_imutavel() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('app.retencao', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'evento_viagem é só de inclusão (% recusado)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    tabela = sa.table(
        "configuracao",
        sa.column("chave", sa.String),
        sa.column("valor", sa.Double),
        sa.column("descricao", sa.String),
    )
    op.bulk_insert(tabela, [{"chave": c, "valor": v, "descricao": d} for c, v, d in PRAZOS])


def downgrade() -> None:
    op.execute("DELETE FROM configuracao WHERE chave LIKE 'retencao_%'")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evento_viagem_imutavel() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'evento_viagem é só de inclusão (% recusado)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
