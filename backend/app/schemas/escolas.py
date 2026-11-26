from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.cadastros import LocalizacaoLida, Texto
from app.geo import Coordenadas


class EscolaCriar(BaseModel):
    nome: Texto
    codigo_inep: Annotated[str, StringConstraints(pattern=r"^\d{8}$")] | None = None
    endereco: Texto | None = None
    localizacao: Coordenadas
    raio_cerca_m: int = Field(default=150, ge=20, le=2000)
    # Omitido: liga ao criar e fica como está ao editar.
    confirma_recebimento: bool | None = None


class EscolaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    codigo_inep: str | None
    endereco: str | None
    localizacao: LocalizacaoLida
    raio_cerca_m: int
    confirma_recebimento: bool
