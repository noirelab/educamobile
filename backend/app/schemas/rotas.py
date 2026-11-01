from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from app.cadastros import IdBanco
from app.schemas.paradas import Nome, ParadaLer


def _sem_repetidas(ids: list[int]) -> list[int]:
    if len(ids) != len(set(ids)):
        raise ValueError("A rota não pode repetir paradas")
    return ids


class RotaCriar(BaseModel):
    nome: Nome


class RotaAtualizar(BaseModel):
    nome: Nome


class RotaSequencia(BaseModel):
    parada_ids: Annotated[list[IdBanco], Field(max_length=500), AfterValidator(_sem_repetidas)]


class TrajetoGeoJSON(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]]


class RotaLer(BaseModel):
    id: int
    nome: str
    distancia_m: float | None
    paradas: list[ParadaLer]
    trajeto: TrajetoGeoJSON | None
