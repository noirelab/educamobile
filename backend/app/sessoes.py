"""Refresh tokens: criação, rotação a cada uso e revogação.

Cada uso troca o token por outro. Se um token já trocado aparecer de novo, alguém guardou uma
cópia: todas as sessões da pessoa são revogadas e os tokens de acesso deixam de valer.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import auditoria
from app.config import settings
from app.models import Sessao, Usuario
from app.security import hash_refresh_token, invalidar_tokens_de_acesso, novo_refresh_token

MAX_USER_AGENT = 300


def _nao_autorizado() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Sessão inválida", headers={"WWW-Authenticate": "Bearer"}
    )


def criar(db: Session, usuario: Usuario, request: Request) -> tuple[Sessao, str]:
    token = novo_refresh_token()
    agente = request.headers.get("user-agent")
    sessao = Sessao(
        usuario_id=usuario.id,
        token_hash=hash_refresh_token(token),
        expira_em=datetime.now(UTC) + timedelta(days=settings.refresh_expire_days),
        ip=auditoria.ip_da_requisicao(request),
        user_agent=agente[:MAX_USER_AGENT] if agente else None,
    )
    db.add(sessao)
    db.flush()
    return sessao, token


def revogar_todas(db: Session, usuario: Usuario) -> None:
    agora = datetime.now(UTC)
    db.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario.id, Sessao.revogada_em.is_(None))
        .values(revogada_em=agora)
    )
    invalidar_tokens_de_acesso(usuario)


def _buscar(db: Session, token: str) -> Sessao | None:
    return db.scalar(
        select(Sessao).where(Sessao.token_hash == hash_refresh_token(token)).with_for_update()
    )


def rotacionar(db: Session, token: str, request: Request) -> tuple[Usuario, str]:
    """Troca o refresh token por um novo. Confirma a transação também nos casos de erro."""
    sessao = _buscar(db, token)
    if sessao is None:
        raise _nao_autorizado()
    usuario = db.get(Usuario, sessao.usuario_id)
    if sessao.revogada_em is not None:
        if sessao.substituida_por_id is not None:
            revogar_todas(db, usuario)
            auditoria.registrar(db, "sessao.reuso", request=request, usuario=usuario)
            db.commit()
        raise _nao_autorizado()
    if sessao.expira_em <= datetime.now(UTC) or not usuario.ativo:
        raise _nao_autorizado()
    nova, novo_token = criar(db, usuario, request)
    sessao.revogada_em = datetime.now(UTC)
    sessao.substituida_por_id = nova.id
    db.commit()
    return usuario, novo_token


def revogar(db: Session, token: str) -> Usuario | None:
    sessao = _buscar(db, token)
    if sessao is None or sessao.revogada_em is not None:
        return None
    sessao.revogada_em = datetime.now(UTC)
    return db.get(Usuario, sessao.usuario_id)
