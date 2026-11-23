import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import consentimento
from app.config import settings
from app.db import get_db
from app.models import PERFIS_INTERNOS, Perfil, ResponsavelEstudante, Usuario

ALGORITMO = "HS256"
TIPO_ACESSO = "access"
_hasher = PasswordHasher()
_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Comparado quando o e-mail não existe, para o tempo de resposta não revelar quem tem conta.
_HASH_FICTICIO = _hasher.hash("senha-ficticia")


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def senha_confere(senha: str, senha_hash: str | None) -> bool:
    try:
        return _hasher.verify(senha_hash or _HASH_FICTICIO, senha) and senha_hash is not None
    except (Argon2Error, InvalidHashError):
        return False


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(UTC)
    payload = {
        "sub": str(usuario.id),
        # Fracionário de propósito: comparado com `sessoes_validas_desde`, que tem microssegundos.
        "iat": agora.timestamp(),
        "exp": agora + timedelta(minutes=settings.jwt_expire_minutes),
        "jti": uuid.uuid4().hex,
        "typ": TIPO_ACESSO,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)


def novo_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """HMAC com o segredo da API: um vazamento só do banco não permite forjar tokens válidos."""
    return hmac.new(settings.jwt_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def invalidar_tokens_de_acesso(usuario: Usuario) -> None:
    usuario.sessoes_validas_desde = datetime.now(UTC)


def autenticar_token(token: str, db: Session) -> tuple[Usuario, float]:
    """Valida o token de acesso e devolve o usuário e o instante (epoch) em que ele vence."""
    invalido = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITMO],
            options={"require": ["exp", "iat", "sub", "typ"]},
        )
        if payload["typ"] != TIPO_ACESSO:
            raise invalido
        usuario_id = int(payload["sub"])
        emitido_em = float(payload["iat"])
        vence_em = float(payload["exp"])
    except (jwt.PyJWTError, ValueError, TypeError) as erro:
        raise invalido from erro
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise invalido
    if emitido_em < usuario.sessoes_validas_desde.timestamp():
        raise invalido
    return usuario, vence_em


def usuario_atual(
    token: Annotated[str, Depends(_oauth2)], db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    return autenticar_token(token, db)[0]


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]


def exigir_perfil(*perfis: Perfil):
    """Dependência que libera a rota apenas para os perfis informados."""

    def verificar(usuario: UsuarioAtual) -> Usuario:
        if usuario.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Perfil sem permissão")
        return usuario

    return Depends(verificar)


# Equipe da secretaria. Responsável, motorista e monitor nunca entram por aqui: o acesso deles
# passa por vínculo (filho, viagem escalada) e tem rotas próprias.
UsuarioInterno = Annotated[Usuario, exigir_perfil(*PERFIS_INTERNOS)]
Responsavel = Annotated[Usuario, exigir_perfil(Perfil.RESPONSAVEL)]


def garantir_responsavel(
    db: Session, usuario: Usuario, estudante_id: int, exigir_consentimento: bool = True
) -> ResponsavelEstudante:
    """Libera o estudante só para quem tem vínculo com ele (e, por padrão, já consentiu).

    Sem vínculo, a resposta é a mesma de um estudante inexistente: o responsável não descobre
    quais ids existem.
    """
    vinculo = db.scalar(
        select(ResponsavelEstudante).where(
            ResponsavelEstudante.responsavel_id == usuario.id,
            ResponsavelEstudante.estudante_id == estudante_id,
        )
    )
    if vinculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante não encontrado")
    if exigir_consentimento and not consentimento.esta_vigente(vinculo):
        # Nunca consentiu ou o termo mudou desde então: em ambos, precisa aceitar de novo.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Consentimento pendente")
    return vinculo
