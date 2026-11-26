"""Consentimento do responsável (LGPD, art. 14): vale só para a versão atual do termo.

Quando `VERSAO_TERMO_CONSENTIMENTO` muda, todo consentimento antigo deixa de valer e o
responsável precisa aceitar de novo, sem que ninguém mexa no banco.
"""

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.models import ResponsavelEstudante


def vigente() -> ColumnElement[bool]:
    """Condição SQL: o vínculo tem consentimento registrado para a versão atual do termo."""
    return and_(
        ResponsavelEstudante.consentimento_em.is_not(None),
        ResponsavelEstudante.consentimento_versao == settings.versao_termo_consentimento,
    )


def esta_vigente(vinculo: ResponsavelEstudante) -> bool:
    return (
        vinculo.consentimento_em is not None
        and vinculo.consentimento_versao == settings.versao_termo_consentimento
    )
