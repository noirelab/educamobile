"""Consulta ao registro de auditoria. Só o administrador lê."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app import auditoria
from app.cadastros import Db, Deslocamento, Limite
from app.models import Auditoria, Perfil, Usuario
from app.schemas.auth import RegistroDeAuditoria
from app.security import exigir_perfil

router = APIRouter(tags=["auditoria"])
SoAdmin = Annotated[Usuario, exigir_perfil(Perfil.ADMIN)]


@router.get("/auditoria")
def consultar(
    request: Request,
    db: Db,
    admin: SoAdmin,
    usuario_id: int | None = None,
    acao: Annotated[str | None, Query(max_length=80)] = None,
    recurso: Annotated[str | None, Query(max_length=80)] = None,
    recurso_id: Annotated[str | None, Query(max_length=80)] = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[RegistroDeAuditoria]:
    consulta = select(Auditoria).order_by(Auditoria.em.desc(), Auditoria.id.desc())
    if usuario_id is not None:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    if acao:
        # "posicao." traz todas as ações que começam assim; sem ponto, é a ação exata.
        if acao.endswith("."):
            consulta = consulta.where(Auditoria.acao.startswith(acao, autoescape=True))
        else:
            consulta = consulta.where(Auditoria.acao == acao)
    if recurso:
        consulta = consulta.where(Auditoria.recurso == recurso)
    if recurso_id:
        consulta = consulta.where(Auditoria.recurso_id == recurso_id)
    if desde:
        consulta = consulta.where(Auditoria.em >= desde)
    if ate:
        consulta = consulta.where(Auditoria.em <= ate)
    registros = db.scalars(consulta.limit(limit).offset(offset)).all()
    # Quem lê o registro também deixa rastro.
    auditoria.registrar(
        db, "auditoria.consultar", request=request, usuario=admin, linhas=len(registros)
    )
    db.commit()
    return [RegistroDeAuditoria.model_validate(r) for r in registros]
