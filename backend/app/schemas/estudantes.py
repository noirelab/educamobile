from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.cadastros import IdBanco, LocalizacaoLidaOpcional, Texto
from app.geo import Coordenadas
from app.schemas.matriculas import MatriculaInicial


class EstudanteCriar(BaseModel):
    nome: Texto
    data_nascimento: date
    nome_responsavel: Texto | None = None
    localizacao: Coordenadas | None = None
    parada_id: IdBanco | None = None

    @field_validator("data_nascimento")
    @classmethod
    def nascimento_no_passado(cls, valor: date) -> date:
        if valor >= date.today():
            raise ValueError("A data de nascimento deve estar no passado")
        return valor


class EstudanteCadastrar(EstudanteCriar):
    """Na criação, a matrícula é opcional para o administrador e obrigatória para o diretor."""

    matricula: MatriculaInicial | None = None


class EstudanteLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    data_nascimento: date
    nome_responsavel: str | None
    localizacao: LocalizacaoLidaOpcional
    parada_id: int | None
