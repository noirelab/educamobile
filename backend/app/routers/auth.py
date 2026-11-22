from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auditoria, sessoes
from app.config import settings
from app.db import get_db
from app.limite import LimiteEmMemoria
from app.models import Perfil, Usuario
from app.schemas.auth import RefreshTokenEntrada, Token, TrocaSenha, UsuarioCriar, UsuarioLer
from app.security import UsuarioAtual, criar_token, exigir_perfil, gerar_hash, senha_confere

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]
MAX_SENHA = 128
MAX_FALHAS_LOGIN = 10
JANELA_LOGIN_S = 900
limite_login = LimiteEmMemoria(maximo=MAX_FALHAS_LOGIN, janela_s=JANELA_LOGIN_S)
# Troca de senha por quem já está logado: a senha atual também não pode ser adivinhada.
limite_troca_senha = LimiteEmMemoria(maximo=5, janela_s=JANELA_LOGIN_S)


def _muitas_tentativas() -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Muitas tentativas. Tente novamente mais tarde",
        headers={"Retry-After": str(JANELA_LOGIN_S)},
    )


def _emitir(db: Session, usuario: Usuario, request: Request) -> Token:
    _, refresh = sessoes.criar(db, usuario, request)
    return Token(
        access_token=criar_token(usuario),
        expires_in=settings.jwt_expire_minutes * 60,
        refresh_token=refresh,
    )


@router.post("/login")
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Db) -> Token:
    email = form.username.lower()
    chave = f"{auditoria.ip_do_cliente(request) or ''}|{email}"
    if limite_login.bloqueado(chave):
        raise _muitas_tentativas()
    # NUL não existe em e-mail e o Postgres o rejeitaria; senha gigante só gastaria CPU no hash.
    entrada_valida = "\x00" not in email and len(form.password) <= MAX_SENHA
    usuario = db.scalar(select(Usuario).where(Usuario.email == email)) if entrada_valida else None
    senha = form.password if entrada_valida else ""
    if not senha_confere(senha, usuario.senha_hash if usuario else None) or (
        usuario and not usuario.ativo
    ):
        limite_login.registrar_falha(chave)
        # Só registra o id quando a conta existe: e-mails digitados errado não ficam guardados.
        auditoria.registrar(db, "login.falha", request=request, usuario=usuario)
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    limite_login.limpar(chave)
    token = _emitir(db, usuario, request)
    auditoria.registrar(db, "login.ok", request=request, usuario=usuario)
    db.commit()
    return token


@router.post("/refresh")
def renovar(dados: RefreshTokenEntrada, request: Request, db: Db) -> Token:
    usuario, refresh = sessoes.rotacionar(db, dados.refresh_token, request)
    return Token(
        access_token=criar_token(usuario),
        expires_in=settings.jwt_expire_minutes * 60,
        refresh_token=refresh,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(dados: RefreshTokenEntrada, request: Request, db: Db) -> None:
    """Encerra a sessão deste aparelho. Responde 204 mesmo para token desconhecido."""
    usuario = sessoes.revogar(db, dados.refresh_token)
    if usuario is not None:
        auditoria.registrar(db, "logout", request=request, usuario=usuario)
        db.commit()


@router.post("/logout-todos", status_code=status.HTTP_204_NO_CONTENT)
def logout_todos(usuario: UsuarioAtual, request: Request, db: Db) -> None:
    """Encerra todas as sessões, por exemplo depois de perder o celular."""
    sessoes.revogar_todas(db, usuario)
    auditoria.registrar(db, "logout.todos", request=request, usuario=usuario)
    db.commit()


@router.put("/senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(dados: TrocaSenha, usuario: UsuarioAtual, request: Request, db: Db) -> None:
    """Troca a senha e encerra todas as sessões, inclusive a atual."""
    chave = str(usuario.id)
    if limite_troca_senha.bloqueado(chave):
        raise _muitas_tentativas()
    if not senha_confere(dados.senha_atual, usuario.senha_hash):
        limite_troca_senha.registrar_falha(chave)
        auditoria.registrar(db, "senha.falha", request=request, usuario=usuario)
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Senha atual incorreta")
    limite_troca_senha.limpar(chave)
    usuario.senha_hash = gerar_hash(dados.senha_nova)
    sessoes.revogar_todas(db, usuario)
    auditoria.registrar(db, "senha.troca", request=request, usuario=usuario)
    db.commit()


@router.get("/me")
def me(usuario: UsuarioAtual) -> UsuarioLer:
    return UsuarioLer.model_validate(usuario)


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioCriar,
    request: Request,
    db: Db,
    admin: Annotated[Usuario, exigir_perfil(Perfil.ADMIN)],
) -> UsuarioLer:
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email.lower(),
        senha_hash=gerar_hash(dados.senha),
        perfil=dados.perfil,
        escola_id=dados.escola_id,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "E-mail já cadastrado ou escola inexistente"
        ) from erro
    auditoria.registrar(
        db,
        "usuario.criar",
        request=request,
        usuario=admin,
        recurso="usuario",
        recurso_id=usuario.id,
        perfil=usuario.perfil.value,
    )
    db.commit()
    return UsuarioLer.model_validate(usuario)
