from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.cadastros import LocalizacaoLida, Texto
from app.geo import Coordenadas


class EscolaCriar(BaseModel):
    nome: Texto
    codigo_inep: Annotated[str, StringConstraints(pattern=r"^\d{8}$")] | None = None
    endereco: Texto | None = None
    localizacao: Coordenadas


class EscolaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    codigo_inep: str | None
    endereco: str | None
    localizacao: LocalizacaoLida
