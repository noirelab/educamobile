"""Refresh tokens: criação, rotação a cada uso e revogação.

Cada uso troca o token por outro. Se um token já trocado aparecer de novo, alguém guardou uma
cópia: todas as sessões da pessoa são revogadas e os tokens de acesso deixam de valer.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import auditoria
from app.config import settings
from app.models import Dispositivo, Sessao, Usuario
from app.security import hash_refresh_token, invalidar_tokens_de_acesso, novo_refresh_token

MAX_USER_AGENT = 300
# Aparelhos conectados ao mesmo tempo. O mais antigo cai quando passa disso.
MAX_SESSOES_ATIVAS = 10
# Sessões expiradas ou revogadas há mais que isso são apagadas pelo worker.
GUARDA_DE_SESSOES = timedelta(days=30)


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
    _limitar_ativas(db, usuario.id)
    return sessao, token


def _ativas(usuario_id: int, agora: datetime):
    return select(Sessao).where(
        Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None), Sessao.expira_em > agora
    )


def _limitar_ativas(db: Session, usuario_id: int) -> None:
    agora = datetime.now(UTC)
    ativas = db.scalars(_ativas(usuario_id, agora).order_by(Sessao.criada_em, Sessao.id)).all()
    for antiga in ativas[: max(0, len(ativas) - MAX_SESSOES_ATIVAS)]:
        antiga.revogada_em = agora


def listar_ativas(db: Session, usuario: Usuario) -> list[Sessao]:
    return list(
        db.scalars(
            _ativas(usuario.id, datetime.now(UTC)).order_by(
                Sessao.criada_em.desc(), Sessao.id.desc()
            )
        )
    )


def revogar_uma(db: Session, usuario: Usuario, sessao_id: int) -> bool:
    """Revoga um aparelho da própria conta. Sessão de outra pessoa é igual a inexistente."""
    sessao = db.get(Sessao, sessao_id)
    if sessao is None or sessao.usuario_id != usuario.id or sessao.revogada_em is not None:
        return False
    sessao.revogada_em = datetime.now(UTC)
    return True


def limpar_antigas(db: Session, agora: datetime | None = None) -> int:
    """Apaga o que expirou ou foi revogado há mais de 30 dias. Devolve quantas linhas."""
    limite = (agora or datetime.now(UTC)) - GUARDA_DE_SESSOES
    resultado = db.execute(
        delete(Sessao).where((Sessao.expira_em < limite) | (Sessao.revogada_em < limite))
    )
    return resultado.rowcount or 0


def revogar_todas(db: Session, usuario: Usuario, *, apagar_aparelhos: bool = True) -> None:
    """Encerra todas as sessões e apaga os aparelhos de push: sem sessão, sem aviso no celular.
    O app registra o aparelho de novo quando a pessoa entra.

    No reuso de refresh token os aparelhos ficam: senão quem guardou um token antigo poderia
    cortar, quando quisesse, os avisos que o responsável recebe sobre o filho."""
    agora = datetime.now(UTC)
    db.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario.id, Sessao.revogada_em.is_(None))
        .values(revogada_em=agora)
    )
    if apagar_aparelhos:
        db.execute(delete(Dispositivo).where(Dispositivo.usuario_id == usuario.id))
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
            revogar_todas(db, usuario, apagar_aparelhos=False)
            auditoria.registrar(db, "sessao.reuso", request=request, usuario=usuario)
            db.commit()
        raise _nao_autorizado()
    if sessao.expira_em <= datetime.now(UTC) or not usuario.ativo:
        raise _nao_autorizado()
    # A antiga sai antes de a nova entrar: senão o limite de sessões ativas derrubaria outro
    # aparelho a cada renovação.
    sessao.revogada_em = datetime.now(UTC)
    db.flush()
    nova, novo_token = criar(db, usuario, request)
    sessao.substituida_por_id = nova.id
    db.commit()
    return usuario, novo_token


def revogar(db: Session, token: str) -> Usuario | None:
    sessao = _buscar(db, token)
    if sessao is None or sessao.revogada_em is not None:
        return None
    sessao.revogada_em = datetime.now(UTC)
    return db.get(Usuario, sessao.usuario_id)
