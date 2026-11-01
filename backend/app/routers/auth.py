import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Perfil, Usuario
from app.schemas.auth import Token, UsuarioCriar, UsuarioLer
from app.security import UsuarioAtual, criar_token, exigir_perfil, gerar_hash, senha_confere

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]
MAX_SENHA = 128
MAX_FALHAS_LOGIN = 10
JANELA_LOGIN_S = 900
MAX_CHAVES_LOGIN = 10_000
_falhas_login: dict[tuple[str, str], list[float]] = {}


def _falhas_recentes(chave: tuple[str, str]) -> list[float]:
    # Contagem em memória, por processo: com vários workers, mover para o proxy ou um Redis.
    limite = time.monotonic() - JANELA_LOGIN_S
    if len(_falhas_login) > MAX_CHAVES_LOGIN:
        _falhas_login.clear()
    recentes = [t for t in _falhas_login.get(chave, []) if t > limite]
    if recentes:
        _falhas_login[chave] = recentes
    else:
        _falhas_login.pop(chave, None)
    return recentes


@router.post("/login")
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Db) -> Token:
    email = form.username.lower()
    chave = (request.client.host if request.client else "", email)
    if len(_falhas_recentes(chave)) >= MAX_FALHAS_LOGIN:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitas tentativas. Tente novamente mais tarde",
            headers={"Retry-After": str(JANELA_LOGIN_S)},
        )
    # NUL não existe em e-mail e o Postgres o rejeitaria; senha gigante só gastaria CPU no hash.
    entrada_valida = "\x00" not in email and len(form.password) <= MAX_SENHA
    usuario = db.scalar(select(Usuario).where(Usuario.email == email)) if entrada_valida else None
    senha = form.password if entrada_valida else ""
    if not senha_confere(senha, usuario.senha_hash if usuario else None) or (
        usuario and not usuario.ativo
    ):
        _falhas_login.setdefault(chave, []).append(time.monotonic())
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _falhas_login.pop(chave, None)
    return Token(access_token=criar_token(usuario))


@router.get("/me")
def me(usuario: UsuarioAtual) -> UsuarioLer:
    return UsuarioLer.model_validate(usuario)


@router.post(
    "/usuarios", status_code=status.HTTP_201_CREATED, dependencies=[exigir_perfil(Perfil.ADMIN)]
)
def criar_usuario(dados: UsuarioCriar, db: Db) -> UsuarioLer:
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email.lower(),
        senha_hash=gerar_hash(dados.senha),
        perfil=dados.perfil,
        escola_id=dados.escola_id,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "E-mail já cadastrado ou escola inexistente"
        ) from erro
    return UsuarioLer.model_validate(usuario)
