"""Gestão de usuários e convites de responsável.

Admin cria e gere qualquer perfil. O gestor cria e gere motorista e monitor, e convida
responsáveis; não toca em admin nem em outro gestor.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import auditoria, sessoes
from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar
from app.models import Convite, Estudante, Perfil, Usuario
from app.schemas.usuarios import (
    ConviteCriar,
    ConviteLer,
    ConviteResumo,
    UsuarioAtualizar,
    UsuarioCriar,
    UsuarioLer,
    UsuariosPagina,
)
from app.security import exigir_perfil, gerar_hash, hash_refresh_token

router = APIRouter(tags=["usuários"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
VALIDADE_CONVITE = timedelta(hours=72)
# Perfis que o gestor pode criar e gerir.
GERIDOS_PELO_GESTOR = frozenset({Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL})


def _pode_gerir(ator: Usuario, perfil: Perfil) -> bool:
    return ator.perfil == Perfil.ADMIN or perfil in GERIDOS_PELO_GESTOR


def _exigir_gestao_de(ator: Usuario, alvo: Usuario) -> None:
    # 404 e não 403: o gestor não descobre quais ids são de administradores.
    if not _pode_gerir(ator, alvo.perfil):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _email_em_uso() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")


@router.get("/usuarios")
def listar(
    db: Db,
    _: Gestao,
    perfil: Perfil | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ativo: bool | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> UsuariosPagina:
    filtros = []
    if perfil is not None:
        filtros.append(Usuario.perfil == perfil)
    if q:
        filtros.append(Usuario.nome.ilike(f"%{_escapar_like(q.strip())}%", escape="\\"))
    if ativo is not None:
        filtros.append(Usuario.ativo == ativo)
    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros))
    itens = db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.nome, Usuario.id)
        .limit(limit)
        .offset(offset)
    )
    return UsuariosPagina(total=total or 0, itens=[UsuarioLer.model_validate(u) for u in itens])


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, request: Request, db: Db, ator: Gestao) -> UsuarioLer:
    if not _pode_gerir(ator, dados.perfil):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o administrador cria esse perfil")
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email.lower(),
        senha_hash=gerar_hash(dados.senha),
        perfil=dados.perfil,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        raise _email_em_uso() from erro
    auditoria.registrar(
        db,
        "usuario.criar",
        request=request,
        usuario=ator,
        recurso="usuario",
        recurso_id=usuario.id,
        perfil=usuario.perfil.value,
    )
    db.commit()
    return UsuarioLer.model_validate(usuario)


@router.get("/usuarios/{usuario_id}")
def obter(usuario_id: IdRota, db: Db, ator: Gestao) -> UsuarioLer:
    alvo = buscar(db, Usuario, usuario_id)
    _exigir_gestao_de(ator, alvo)
    return UsuarioLer.model_validate(alvo)


@router.patch("/usuarios/{usuario_id}")
def atualizar(
    usuario_id: IdRota, dados: UsuarioAtualizar, request: Request, db: Db, ator: Gestao
) -> UsuarioLer:
    alvo = buscar(db, Usuario, usuario_id)
    _exigir_gestao_de(ator, alvo)
    campos = []
    if dados.nome is not None:
        alvo.nome = dados.nome
        campos.append("nome")
    if dados.email is not None and dados.email.lower() != alvo.email:
        alvo.email = dados.email.lower()
        campos.append("email")
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        raise _email_em_uso() from erro
    if "email" in campos:
        # E-mail novo muda quem pode entrar: as sessões antigas deixam de valer.
        sessoes.revogar_todas(db, alvo)
    auditoria.registrar(
        db,
        "usuario.editar",
        request=request,
        usuario=ator,
        recurso="usuario",
        recurso_id=alvo.id,
        campos=campos,
    )
    db.commit()
    return UsuarioLer.model_validate(alvo)


def _alterar_situacao(
    usuario_id: int, ativo: bool, request: Request, db: Db, ator: Usuario
) -> UsuarioLer:
    alvo = buscar(db, Usuario, usuario_id)
    _exigir_gestao_de(ator, alvo)
    if alvo.id == ator.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você não pode desativar a própria conta")
    alvo.ativo = ativo
    if not ativo:
        sessoes.revogar_todas(db, alvo)
    auditoria.registrar(
        db,
        "usuario.reativar" if ativo else "usuario.desativar",
        request=request,
        usuario=ator,
        recurso="usuario",
        recurso_id=alvo.id,
    )
    db.commit()
    return UsuarioLer.model_validate(alvo)


@router.post("/usuarios/{usuario_id}/desativar")
def desativar(usuario_id: IdRota, request: Request, db: Db, ator: Gestao) -> UsuarioLer:
    return _alterar_situacao(usuario_id, False, request, db, ator)


@router.post("/usuarios/{usuario_id}/reativar")
def reativar(usuario_id: IdRota, request: Request, db: Db, ator: Gestao) -> UsuarioLer:
    return _alterar_situacao(usuario_id, True, request, db, ator)


@router.post("/convites", status_code=status.HTTP_201_CREATED)
def criar_convite(dados: ConviteCriar, request: Request, db: Db, ator: Gestao) -> ConviteLer:
    buscar(db, Estudante, dados.estudante_id)
    email = dados.email.lower()
    if db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        # Quem já tem conta é vinculado por POST /estudantes/{id}/responsaveis.
        raise _email_em_uso()
    codigo = secrets.token_urlsafe(24)
    convite = Convite(
        codigo_hash=hash_refresh_token(codigo),
        nome=dados.nome,
        email=email,
        estudante_id=dados.estudante_id,
        parentesco=dados.parentesco,
        principal=dados.principal,
        criado_por_id=ator.id,
        expira_em=datetime.now(UTC) + VALIDADE_CONVITE,
    )
    db.add(convite)
    db.flush()
    auditoria.registrar(
        db,
        "convite.criar",
        request=request,
        usuario=ator,
        recurso="estudante",
        recurso_id=dados.estudante_id,
        convite_id=convite.id,
    )
    db.commit()
    return ConviteLer(
        id=convite.id,
        codigo=codigo,
        email=email,
        estudante_id=convite.estudante_id,
        expira_em=convite.expira_em,
    )


@router.get("/convites")
def listar_convites(
    db: Db, _: Gestao, pendentes: bool = True, limit: Limite = 50, offset: Deslocamento = 0
) -> list[ConviteResumo]:
    consulta = select(Convite).order_by(Convite.id.desc()).limit(limit).offset(offset)
    if pendentes:
        consulta = consulta.where(Convite.usado_em.is_(None), Convite.expira_em > func.now())
    return [ConviteResumo.model_validate(c) for c in db.scalars(consulta)]
