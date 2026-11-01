from pydantic import BaseModel, ConfigDict, Field

from app.cadastros import Texto
from app.geo import Coordenadas

Nome = Texto


class ParadaCriar(BaseModel):
    nome: Nome
    localizacao: Coordenadas


class ParadaAtualizar(BaseModel):
    nome: Nome | None = None
    localizacao: Coordenadas | None = None


class ParadaLer(BaseModel):
    id: int
    nome: str
    localizacao: Coordenadas


class ParadaProxima(ParadaLer):
    distancia_m: float = Field(ge=0)


class EstudanteDaParada(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
