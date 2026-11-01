from pydantic import BaseModel, ConfigDict, Field

from app.cadastros import IdBanco, Texto
from app.models import Turno


class TurmaCriar(BaseModel):
    escola_id: IdBanco
    nome: Texto
    serie: Texto
    turno: Turno
    ano_letivo: int = Field(ge=2000, le=2100)


class TurmaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escola_id: int
    nome: str
    serie: str
    turno: Turno
    ano_letivo: int
