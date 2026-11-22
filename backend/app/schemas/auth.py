from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.cadastros import IdBanco, Texto
from app.models import Perfil

Senha = Field(min_length=10, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class RefreshTokenEntrada(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class TrocaSenha(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    senha_nova: str = Senha

    @model_validator(mode="after")
    def senha_diferente(self) -> Self:
        if self.senha_atual == self.senha_nova:
            raise ValueError("A senha nova precisa ser diferente da atual")
        return self


class UsuarioCriar(BaseModel):
    nome: Texto
    email: EmailStr
    senha: str = Senha
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
