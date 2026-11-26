from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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


class UsuarioLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    perfil: Perfil
    ativo: bool
    escola_id: int | None = None


class SessaoLer(BaseModel):
    """Um aparelho conectado. Nunca inclui o token."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    criada_em: datetime
    expira_em: datetime
    ip: str | None
    user_agent: str | None


class RegistroDeAuditoria(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    em: datetime
    usuario_id: int | None
    acao: str
    recurso: str | None
    recurso_id: str | None
    ip: str | None
    detalhes: dict | None
