from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auditoria, sessoes
from app.config import settings
from app.db import get_db
from app.limite import LimiteEmMemoria
from app.models import Convite, Perfil, ResponsavelEstudante, Usuario
from app.schemas.auth import RefreshTokenEntrada, Token, TrocaSenha, UsuarioLer
from app.schemas.usuarios import ConviteAceitar
from app.security import UsuarioAtual, criar_token, gerar_hash, hash_refresh_token, senha_confere

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]
MAX_SENHA = 128
MAX_FALHAS_LOGIN = 10
# Um IP tentando muitas contas (pulverização de senha) e uma conta atacada de muitos IPs.
MAX_FALHAS_POR_IP = 30
MAX_FALHAS_POR_CONTA = 50
JANELA_LOGIN_S = 900
limite_login = LimiteEmMemoria(maximo=MAX_FALHAS_LOGIN, janela_s=JANELA_LOGIN_S)
limite_login_ip = LimiteEmMemoria(maximo=MAX_FALHAS_POR_IP, janela_s=JANELA_LOGIN_S)
limite_login_conta = LimiteEmMemoria(maximo=MAX_FALHAS_POR_CONTA, janela_s=JANELA_LOGIN_S)
# Troca de senha por quem já está logado: a senha atual também não pode ser adivinhada.
limite_troca_senha = LimiteEmMemoria(maximo=5, janela_s=JANELA_LOGIN_S)
# Aceite de convite: o código é aleatório, mas o limite barra quem tenta adivinhar.
limite_convite = LimiteEmMemoria(maximo=10, janela_s=JANELA_LOGIN_S)


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
    email = form.username.strip().lower()
    ip = auditoria.ip_do_cliente(request) or ""
    chave = f"{ip}|{email}"
    if (
        limite_login.bloqueado(chave)
        or limite_login_ip.bloqueado(ip)
        or limite_login_conta.bloqueado(email)
    ):
        raise _muitas_tentativas()
    # NUL não existe em e-mail e o Postgres o rejeitaria; senha gigante só gastaria CPU no hash.
    entrada_valida = "\x00" not in email and len(form.password) <= MAX_SENHA
    usuario = db.scalar(select(Usuario).where(Usuario.email == email)) if entrada_valida else None
    senha = form.password if entrada_valida else ""
    if not senha_confere(senha, usuario.senha_hash if usuario else None) or (
        usuario and not usuario.ativo
    ):
        limite_login.registrar_falha(chave)
        limite_login_ip.registrar_falha(ip)
        limite_login_conta.registrar_falha(email)
        # Só registra o id quando a conta existe: e-mails digitados errado não ficam guardados.
        auditoria.registrar(db, "login.falha", request=request, usuario=usuario)
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # O contador por IP não é zerado: senão um atacante com uma conta válida intercalaria
    # logins próprios para continuar testando senhas de outras pessoas.
    limite_login.limpar(chave)
    limite_login_conta.limpar(email)
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


@router.post("/convites/{codigo}/aceitar", status_code=status.HTTP_201_CREATED)
def aceitar_convite(codigo: str, dados: ConviteAceitar, request: Request, db: Db) -> Token:
    """O responsável define a senha e entra. O convite já traz o vínculo com o estudante."""
    ip = auditoria.ip_do_cliente(request) or ""
    if limite_convite.bloqueado(ip):
        raise _muitas_tentativas()
    invalido = HTTPException(status.HTTP_404_NOT_FOUND, "Convite inválido ou expirado")
    if len(codigo) > 100 or "\x00" in codigo:
        limite_convite.registrar_falha(ip)
        raise invalido
    # O UPDATE condicional é o que garante o uso único, mesmo com duas requisições em paralelo.
    convite = db.scalar(
        update(Convite)
        .where(
            Convite.codigo_hash == hash_refresh_token(codigo),
            Convite.usado_em.is_(None),
            Convite.expira_em > func.now(),
        )
        .values(usado_em=func.now())
        .returning(Convite)
    )
    if convite is None:
        limite_convite.registrar_falha(ip)
        raise invalido
    usuario = Usuario(
        nome=convite.nome,
        email=convite.email,
        senha_hash=gerar_hash(dados.senha),
        perfil=Perfil.RESPONSAVEL,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError as erro:
        # Alguém criou uma conta com este e-mail depois do convite.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado") from erro
    db.add(
        ResponsavelEstudante(
            responsavel_id=usuario.id,
            estudante_id=convite.estudante_id,
            parentesco=convite.parentesco,
            principal=convite.principal,
            criado_por_id=convite.criado_por_id,
        )
    )
    token = _emitir(db, usuario, request)
    auditoria.registrar(
        db,
        "convite.aceitar",
        request=request,
        usuario=usuario,
        recurso="estudante",
        recurso_id=convite.estudante_id,
        convite_id=convite.id,
    )
    db.commit()
    return token
