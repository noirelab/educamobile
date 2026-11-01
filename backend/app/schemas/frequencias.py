import enum
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.cadastros import IdBanco
from app.schemas.matriculas import DataNaoFutura


class Agrupamento(enum.StrEnum):
    ESCOLA = "escola"
    POLO = "polo"
    TURMA = "turma"


class FrequenciaCriar(BaseModel):
    matricula_id: IdBanco
    data: DataNaoFutura
    presente: bool


class RegistroLote(BaseModel):
    matricula_id: IdBanco
    presente: bool


class FrequenciaLote(BaseModel):
    turma_id: IdBanco
    data: DataNaoFutura
    registros: list[RegistroLote] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def sem_repeticao(self) -> Self:
        ids = [r.matricula_id for r in self.registros]
        if len(ids) != len(set(ids)):
            raise ValueError("Matrícula repetida no lote")
        return self


class FrequenciaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    matricula_id: int
    data: date
    presente: bool


class FrequenciaAgregada(BaseModel):
    # Nulos no grupo das escolas sem polo.
    grupo_id: int | None
    grupo_nome: str | None
    total_registros: int
    presencas: int
    faltas: int
    taxa_infrequencia: float
