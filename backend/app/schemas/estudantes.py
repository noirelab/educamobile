import re
from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app import tempo
from app.cadastros import IdBanco, Texto
from app.models import Turno

Observacoes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]+$"),
]


def _normalizar_telefone(valor: str) -> str:
    """Aceita espaços, parênteses, hífen e o + do DDI; guarda só os dígitos (com o + se houver).
    10 a 13 dígitos: fixo ou celular com DDD, com ou sem o 55."""
    limpo = re.sub(r"[\s().-]", "", valor)
    if not re.fullmatch(r"\+?[0-9]{10,13}", limpo):
        raise ValueError("Telefone inválido: use DDD e número, só com dígitos")
    return limpo


Telefone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=25),
    AfterValidator(_normalizar_telefone),
]
NomeCurto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=r"^[^\x00]+$"),
]
CAMPOS_CONTATO = (
    "contato_emergencia_nome",
    "contato_emergencia_telefone",
    "contato_emergencia_parentesco",
)


class ContatoEmergencia(BaseModel):
    """Para quem não tem smartphone ou quando o responsável não atende. É opcional."""

    model_config = ConfigDict(extra="forbid")

    nome: NomeCurto
    telefone: Telefone
    parentesco: NomeCurto | None = None


class EstudanteCriar(BaseModel):
    nome: Texto
    data_nascimento: date
    escola_id: IdBanco
    turno: Turno
    parada_id: IdBanco | None = None
    observacoes_cuidado: Observacoes | None = None
    # Omitidos no PUT, ficam como estão: o formulário da gestão não pode apagar o contato que o
    # responsável cadastrou só porque não conhece o campo.
    contato_emergencia_nome: NomeCurto | None = None
    contato_emergencia_telefone: Telefone | None = None
    contato_emergencia_parentesco: NomeCurto | None = None

    @model_validator(mode="after")
    def contato_completo(self) -> "EstudanteCriar":
        if (self.contato_emergencia_nome is None) != (self.contato_emergencia_telefone is None):
            raise ValueError("Contato de emergência precisa de nome e telefone")
        if self.contato_emergencia_parentesco and self.contato_emergencia_nome is None:
            raise ValueError("Parentesco sem contato de emergência")
        return self

    @field_validator("data_nascimento")
    @classmethod
    def nascimento_no_passado(cls, valor: date) -> date:
        if valor >= tempo.hoje():
            raise ValueError("A data de nascimento deve estar no passado")
        return valor


class EstudanteLer(BaseModel):
    """Nenhum campo de endereço ou localização da casa. A foto sai por URL assinada à parte."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    data_nascimento: date
    escola_id: int
    turno: Turno
    parada_id: int | None
    observacoes_cuidado: str | None
    contato_emergencia_nome: str | None = None
    contato_emergencia_telefone: str | None = None
    contato_emergencia_parentesco: str | None = None
    foto_arquivo: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def tem_foto(self) -> bool:
        return self.foto_arquivo is not None


class EstudantesPagina(BaseModel):
    total: int
    itens: list[EstudanteLer]


class FotoUrl(BaseModel):
    url: str
    expira_em: datetime
