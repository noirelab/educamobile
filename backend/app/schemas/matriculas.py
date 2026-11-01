from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.cadastros import IdBanco
from app.models import StatusMatricula


def _nao_futura(valor: date) -> date:
    if valor > date.today():
        raise ValueError("A data não pode estar no futuro")
    return valor


DataNaoFutura = Annotated[date, AfterValidator(_nao_futura)]


class MatriculaCriar(BaseModel):
    estudante_id: IdBanco
    turma_id: IdBanco
    data_inicio: date


class MatriculaInicial(BaseModel):
    turma_id: IdBanco
    data_inicio: date


class MatriculaEncerrar(BaseModel):
    data_fim: DataNaoFutura


class TransferenciaCriar(BaseModel):
    estudante_id: IdBanco
    turma_destino_id: IdBanco
    data: DataNaoFutura


class MatriculaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estudante_id: int
    turma_id: int
    data_inicio: date
    data_fim: date | None
    status: StatusMatricula
