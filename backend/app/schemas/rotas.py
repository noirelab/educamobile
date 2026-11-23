from datetime import time
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.cadastros import IdBanco
from app.models import Sentido, Turno
from app.schemas.paradas import Nome, ParadaLer

RAIO_PADRAO_M = 50


class ParadaNaRota(BaseModel):
    parada_id: IdBanco
    horario_previsto: time | None = None
    raio_cerca_m: int = Field(default=RAIO_PADRAO_M, ge=10, le=1000)


class RotaCriar(BaseModel):
    nome: Nome
    escola_id: IdBanco
    turno: Turno
    sentido: Sentido
    veiculo_id: IdBanco | None = None
    motorista_id: IdBanco | None = None


class RotaAtualizar(BaseModel):
    """Só os campos enviados mudam; veiculo_id e motorista_id aceitam null para limpar."""

    nome: Nome | None = None
    escola_id: IdBanco | None = None
    turno: Turno | None = None
    sentido: Sentido | None = None
    veiculo_id: IdBanco | None = None
    motorista_id: IdBanco | None = None

    @model_validator(mode="after")
    def algum_campo(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo")
        for obrigatorio in ("nome", "escola_id", "turno", "sentido"):
            if obrigatorio in self.model_fields_set and getattr(self, obrigatorio) is None:
                raise ValueError(f"{obrigatorio} não pode ser nulo")
        return self


class RotaSequencia(BaseModel):
    """Paradas em ordem. Envie `parada_ids` (só a ordem) ou `paradas` (com horário e cerca)."""

    parada_ids: Annotated[list[IdBanco], Field(max_length=500)] | None = None
    paradas: Annotated[list[ParadaNaRota], Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def validar(self) -> Self:
        if (self.parada_ids is None) == (self.paradas is None):
            raise ValueError("Envie parada_ids ou paradas, não os dois")
        itens = self.itens()
        ids = [i.parada_id for i in itens]
        if len(ids) != len(set(ids)):
            raise ValueError("A rota não pode repetir paradas")
        horarios = [i.horario_previsto for i in itens if i.horario_previsto is not None]
        if any(a >= b for a, b in zip(horarios, horarios[1:], strict=False)):
            raise ValueError("Os horários precisam crescer ao longo da sequência")
        return self

    def itens(self) -> list[ParadaNaRota]:
        if self.paradas is not None:
            return self.paradas
        return [ParadaNaRota(parada_id=i) for i in self.parada_ids or []]


class TrajetoGeoJSON(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]]


class ItemDoItinerario(BaseModel):
    parada_id: int
    ordem: int
    horario_previsto: time | None
    raio_cerca_m: int


class RotaLer(BaseModel):
    id: int
    nome: str
    escola_id: int
    turno: Turno
    sentido: Sentido
    veiculo_id: int | None
    motorista_id: int | None
    distancia_m: float | None
    paradas: list[ParadaLer]
    itinerario: list[ItemDoItinerario]
    trajeto: TrajetoGeoJSON | None
