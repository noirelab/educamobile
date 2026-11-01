from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.cadastros import IdBanco, LocalizacaoLida, Texto
from app.geo import Coordenadas


class EscolaCriar(BaseModel):
    nome: Texto
    codigo_inep: Annotated[str, StringConstraints(pattern=r"^\d{8}$")] | None = None
    endereco: Texto | None = None
    polo_id: IdBanco | None = None
    localizacao: Coordenadas


class EscolaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    codigo_inep: str | None
    endereco: str | None
    polo_id: int | None
    localizacao: LocalizacaoLida
