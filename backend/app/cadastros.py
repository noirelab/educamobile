"""Tipos e funções compartilhados pelas rotas de cadastro."""

from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query, status
from geoalchemy2.elements import WKBElement
from pydantic import BeforeValidator, Field, StringConstraints
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.geo import Coordenadas, de_ponto

# Maior valor da coluna integer; acima disso o banco falharia com erro 500.
MAX_ID = 2_147_483_647

Texto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]+$"),
]
IdBanco = Annotated[int, Field(ge=1, le=MAX_ID)]
IdRota = Annotated[int, Path(ge=1, le=MAX_ID)]
IdFiltro = Annotated[int | None, Query(ge=1, le=MAX_ID)]
Limite = Annotated[int, Query(ge=1, le=200)]
Deslocamento = Annotated[int, Query(ge=0, le=MAX_ID)]
Db = Annotated[Session, Depends(get_db)]


def _ler_ponto(valor):
    return de_ponto(valor) if isinstance(valor, WKBElement) else valor


LocalizacaoLida = Annotated[Coordenadas, BeforeValidator(_ler_ponto)]
LocalizacaoLidaOpcional = Annotated[Coordenadas | None, BeforeValidator(_ler_ponto)]


def buscar(db: Session, modelo, id_: int):
    objeto = db.get(modelo, id_)
    if objeto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{modelo.__name__} não encontrado(a)")
    return objeto


def salvar(db: Session, mensagem: str) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, mensagem) from erro
