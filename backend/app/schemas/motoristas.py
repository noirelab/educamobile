from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.cadastros import IdBanco

CategoriaCnh = Literal["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"]
Cnh = Annotated[str, StringConstraints(pattern=r"^\d{11}$")]


class MotoristaCriar(BaseModel):
    usuario_id: IdBanco
    cnh: Cnh
    categoria_cnh: CategoriaCnh
    cnh_valida_ate: date
    curso_transporte_escolar_ate: date


class MotoristaAtualizar(BaseModel):
    cnh: Cnh
    categoria_cnh: CategoriaCnh
    cnh_valida_ate: date
    curso_transporte_escolar_ate: date


class Habilitacao(BaseModel):
    """Se o motorista pode dirigir na data, e os motivos quando não pode."""

    data: date
    pode_dirigir: bool
    motivos: list[str]


class MotoristaResumo(BaseModel):
    """Listagem: o número da CNH sai mascarado."""

    usuario_id: int
    nome: str
    cnh_final: str
    categoria_cnh: str
    cnh_valida_ate: date
    curso_transporte_escolar_ate: date
    habilitacao: Habilitacao


class MotoristaDetalhe(BaseModel):
    usuario_id: int
    nome: str
    email: str
    cnh: str
    categoria_cnh: str
    cnh_valida_ate: date
    curso_transporte_escolar_ate: date
    habilitacao: Habilitacao


class MotoristasPagina(BaseModel):
    total: int
    itens: list[MotoristaResumo]


class DocumentoVencendo(BaseModel):
    usuario_id: int
    nome: str
    documento: Literal["cnh", "curso_transporte_escolar"]
    vence_em: date
    dias_restantes: int = Field(description="Negativo quando já venceu")
