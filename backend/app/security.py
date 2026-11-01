from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Perfil, Usuario

ALGORITMO = "HS256"
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
        "iat": agora,
        "exp": agora + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)


def usuario_atual(
    token: Annotated[str, Depends(_oauth2)], db: Annotated[Session, Depends(get_db)]
) -> Usuario:
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
            options={"require": ["exp", "sub"]},
        )
        usuario_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError) as erro:
        raise invalido from erro
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise invalido
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]


def exigir_perfil(*perfis: Perfil):
    """Dependência que libera a rota apenas para os perfis informados."""

    def verificar(usuario: UsuarioAtual) -> Usuario:
        if usuario.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Perfil sem permissão")
        return usuario

    return Depends(verificar)


def garantir_escola(usuario: Usuario, escola_id: int | None) -> None:
    """Diretor só atua na própria escola; os demais perfis liberados pela rota passam direto."""
    if usuario.perfil == Perfil.DIRETOR and usuario.escola_id != escola_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fora do escopo da sua escola")
