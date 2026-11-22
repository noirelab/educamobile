"""Registro de ações sensíveis. Grava na transação atual; quem chama faz o commit."""

import ipaddress

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Auditoria, Usuario

# Campos que nunca entram em `detalhes`, mesmo que alguém os passe por engano.
_PROIBIDOS = {"senha", "senha_atual", "senha_nova", "password", "token", "refresh_token"}


def ip_do_cliente(request: Request) -> str | None:
    """IP de quem fez a requisição.

    Sem proxy, vale só o endereço da conexão. Atrás de um proxy confiável, vale o último item
    de X-Forwarded-For, que é o que o proxy acrescentou; os anteriores vêm do cliente e podem
    ser inventados. O uvicorn precisa rodar com --no-proxy-headers, senão ele mesmo reescreve
    o endereço da conexão a partir desse cabeçalho.
    """
    if settings.confiar_proxy:
        encaminhado = request.headers.get("x-forwarded-for")
        if encaminhado:
            return encaminhado.split(",")[-1].strip() or None
    return request.client.host if request.client else None


def ip_da_requisicao(request: Request) -> str | None:
    ip = ip_do_cliente(request)
    try:
        return str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:
        # O TestClient e alguns proxies mandam nomes em vez de IPs; a coluna é INET.
        return None


def registrar(
    db: Session,
    acao: str,
    *,
    request: Request | None = None,
    usuario: Usuario | int | None = None,
    recurso: str | None = None,
    recurso_id: int | str | None = None,
    **detalhes,
) -> None:
    usuario_id = usuario.id if isinstance(usuario, Usuario) else usuario
    limpos = {k: v for k, v in detalhes.items() if k not in _PROIBIDOS}
    db.add(
        Auditoria(
            acao=acao,
            usuario_id=usuario_id,
            recurso=recurso,
            recurso_id=str(recurso_id) if recurso_id is not None else None,
            ip=ip_da_requisicao(request) if request else None,
            detalhes=limpos or None,
        )
    )
