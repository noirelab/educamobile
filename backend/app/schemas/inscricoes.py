from datetime import date, timedelta
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cadastros import IdBanco
from app.models import Sentido

# Quantos dias à frente o responsável pode avisar uma ausência.
JANELA_AUSENCIA_DIAS = 60


def _dias_validos(dias: list[int]) -> list[int]:
    if any(d < 0 or d > 6 for d in dias):
        raise ValueError("Dias da semana vão de 0 (segunda) a 6 (domingo)")
    if len(dias) != len(set(dias)):
        raise ValueError("Dia da semana repetido")
    return sorted(dias)


DiasDaSemana = Annotated[
    list[int], Field(min_length=1, max_length=7), AfterValidator(_dias_validos)
]


class InscricaoItem(BaseModel):
    estudante_id: IdBanco
    parada_id: IdBanco
    dias_semana: DiasDaSemana = [0, 1, 2, 3, 4]
    vigencia_inicio: date
    vigencia_fim: date | None = None

    @model_validator(mode="after")
    def periodo(self) -> Self:
        if self.vigencia_fim is not None and self.vigencia_fim < self.vigencia_inicio:
            raise ValueError("A vigência não pode terminar antes de começar")
        return self


class InscricoesSubstituir(BaseModel):
    """A lista completa de inscrições ativas da rota. Quem não estiver nela é desativado."""

    inscricoes: Annotated[list[InscricaoItem], Field(max_length=200)]

    @field_validator("inscricoes")
    @classmethod
    def sem_estudante_repetido(cls, itens: list[InscricaoItem]) -> list[InscricaoItem]:
        ids = [i.estudante_id for i in itens]
        if len(ids) != len(set(ids)):
            raise ValueError("Estudante repetido na lista")
        return itens


class InscricaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estudante_id: int
    estudante_nome: str | None = None
    rota_id: int
    parada_id: int
    dias_semana: list[int]
    vigencia_inicio: date
    vigencia_fim: date | None
    ativa: bool


class AusenciaCriar(BaseModel):
    estudante_id: IdBanco
    data: date
    sentido: Sentido | None = None

    @field_validator("data")
    @classmethod
    def dentro_da_janela(cls, valor: date) -> date:
        hoje = date.today()
        if valor < hoje or valor > hoje + timedelta(days=JANELA_AUSENCIA_DIAS):
            raise ValueError(
                f"A data precisa estar entre hoje e {JANELA_AUSENCIA_DIAS} dias à frente"
            )
        return valor


class AusenciaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estudante_id: int
    data: date
    sentido: Sentido | None
