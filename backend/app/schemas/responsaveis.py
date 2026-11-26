from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.cadastros import IdBanco, Texto
from app.schemas.estudantes import ContatoEmergencia


class VinculoCriar(BaseModel):
    responsavel_id: IdBanco
    parentesco: Texto
    principal: bool = False


class VinculoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    responsavel_id: int
    estudante_id: int
    parentesco: str
    principal: bool
    consentimento_em: datetime | None
    consentimento_versao: str | None


class Consentimento(BaseModel):
    versao_termo: str = Field(min_length=1, max_length=40)


class FilhoResumo(BaseModel):
    """O que o responsável vê antes de consentir: só o necessário para reconhecer o filho."""

    estudante_id: int
    nome: str
    parentesco: str
    consentimento_pendente: bool


class ParadaDoFilho(BaseModel):
    id: int
    nome: str


class FilhoDetalhe(BaseModel):
    """Dados mínimos para o acompanhamento. Endereço e localização da casa não saem daqui."""

    estudante_id: int
    nome: str
    parada: ParadaDoFilho | None
    contato_emergencia: ContatoEmergencia | None = None
