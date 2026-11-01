from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.cadastros import IdBanco, Texto
from app.models import Perfil


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioCriar(BaseModel):
    nome: Texto
    email: EmailStr
    senha: str = Field(min_length=10, max_length=128)
    perfil: Perfil
    escola_id: IdBanco | None = None

    @model_validator(mode="after")
    def diretor_tem_escola(self) -> Self:
        if self.perfil == Perfil.DIRETOR and self.escola_id is None:
            raise ValueError("Diretor precisa de escola_id")
        return self


class UsuarioLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    perfil: Perfil
    escola_id: int | None
    ativo: bool
