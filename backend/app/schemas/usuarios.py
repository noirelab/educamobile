from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.cadastros import IdBanco, Texto
from app.models import Perfil
from app.schemas.auth import Senha, UsuarioLer

# Responsável nunca é criado direto: entra por convite, com o vínculo já definido.
PERFIS_CRIAVEIS = frozenset({Perfil.ADMIN, Perfil.GESTOR, Perfil.MOTORISTA, Perfil.MONITOR})


class UsuarioCriar(BaseModel):
    nome: Texto
    email: EmailStr
    senha: str = Senha
    perfil: Perfil

    @model_validator(mode="after")
    def perfil_criavel(self) -> Self:
        if self.perfil not in PERFIS_CRIAVEIS:
            raise ValueError("Responsável entra por convite (POST /convites)")
        return self


class UsuarioAtualizar(BaseModel):
    nome: Texto | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def algum_campo(self) -> Self:
        if self.nome is None and self.email is None:
            raise ValueError("Informe nome ou email")
        return self


class UsuariosPagina(BaseModel):
    total: int
    itens: list[UsuarioLer]


class ConviteCriar(BaseModel):
    nome: Texto
    email: EmailStr
    estudante_id: IdBanco
    parentesco: Texto
    principal: bool = False


class ConviteLer(BaseModel):
    """O código só aparece nesta resposta: depois disso o banco guarda apenas o hash."""

    id: int
    codigo: str
    email: EmailStr
    estudante_id: int
    expira_em: datetime


class ConviteAceitar(BaseModel):
    # No corpo e não no caminho da URL: o caminho fica no log do nginx, do uvicorn e do proxy.
    codigo: Annotated[str, Field(max_length=1000)]
    senha: str = Senha


class ConviteResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    estudante_id: int
    expira_em: datetime
    usado_em: datetime | None
