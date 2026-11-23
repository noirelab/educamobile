from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)

from app.cadastros import IdBanco, Texto
from app.models import Turno

Observacoes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]+$"),
]


class EstudanteCriar(BaseModel):
    nome: Texto
    data_nascimento: date
    escola_id: IdBanco
    turno: Turno
    parada_id: IdBanco | None = None
    observacoes_cuidado: Observacoes | None = None

    @field_validator("data_nascimento")
    @classmethod
    def nascimento_no_passado(cls, valor: date) -> date:
        if valor >= date.today():
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
