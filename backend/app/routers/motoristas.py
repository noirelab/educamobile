"""Cadastro dos motoristas e a pergunta "ele pode dirigir hoje?".

A gestão enxerga todos. O motorista enxerga só o próprio cadastro. O número da CNH não sai em
listagens e nunca em rotas do responsável (que não passam por aqui).
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import auditoria, habilitacao
from app.cadastros import Db, Deslocamento, IdRota, Limite
from app.models import Motorista, Perfil, Usuario
from app.schemas.motoristas import (
    DocumentoVencendo,
    Habilitacao,
    MotoristaAtualizar,
    MotoristaCriar,
    MotoristaDetalhe,
    MotoristaResumo,
    MotoristasPagina,
)
from app.security import exigir_perfil

router = APIRouter(tags=["motoristas"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
SoMotorista = Annotated[Usuario, exigir_perfil(Perfil.MOTORISTA)]
CONFLITO = "CNH já cadastrada ou motorista já tem cadastro"


def _habilitacao(usuario: Usuario, motorista: Motorista | None, dia: date) -> Habilitacao:
    s = habilitacao.situacao(usuario, motorista, dia)
    return Habilitacao(data=dia, pode_dirigir=s.pode_dirigir, motivos=s.motivos)


def _detalhe(usuario: Usuario, m: Motorista) -> MotoristaDetalhe:
    return MotoristaDetalhe(
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        cnh=m.cnh,
        categoria_cnh=m.categoria_cnh,
        cnh_valida_ate=m.cnh_valida_ate,
        curso_transporte_escolar_ate=m.curso_transporte_escolar_ate,
        habilitacao=_habilitacao(usuario, m, date.today()),
    )


def _resumo(usuario: Usuario, m: Motorista) -> MotoristaResumo:
    return MotoristaResumo(
        usuario_id=usuario.id,
        nome=usuario.nome,
        cnh_final=f"*******{m.cnh[-4:]}",
        categoria_cnh=m.categoria_cnh,
        cnh_valida_ate=m.cnh_valida_ate,
        curso_transporte_escolar_ate=m.curso_transporte_escolar_ate,
        habilitacao=_habilitacao(usuario, m, date.today()),
    )


def _buscar(db: Db, usuario_id: int) -> tuple[Usuario, Motorista]:
    usuario = db.get(Usuario, usuario_id)
    motorista = db.get(Motorista, usuario_id)
    if usuario is None or motorista is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Motorista não encontrado")
    return usuario, motorista


@router.get("/motoristas")
def listar(
    db: Db,
    _: Gestao,
    pode_dirigir: bool | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> MotoristasPagina:
    linhas = db.execute(
        select(Usuario, Motorista)
        .join(Motorista, Motorista.usuario_id == Usuario.id)
        .order_by(Usuario.nome, Usuario.id)
    ).all()
    itens = [_resumo(u, m) for u, m in linhas]
    if pode_dirigir is not None:
        itens = [i for i in itens if i.habilitacao.pode_dirigir is pode_dirigir]
    return MotoristasPagina(total=len(itens), itens=itens[offset : offset + limit])


@router.get("/motoristas/vencendo")
def vencendo(
    db: Db, _: Gestao, dias: Annotated[int, Query(ge=1, le=365)] = 30
) -> list[DocumentoVencendo]:
    """Documentos que vencem nos próximos `dias`, e os já vencidos, do mais urgente ao menos."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)
    resultado: list[DocumentoVencendo] = []
    linhas = db.execute(
        select(Usuario, Motorista)
        .join(Motorista, Motorista.usuario_id == Usuario.id)
        .where(Usuario.ativo.is_(True))
    ).all()
    for usuario, m in linhas:
        for nome, vence in (
            ("cnh", m.cnh_valida_ate),
            ("curso_transporte_escolar", m.curso_transporte_escolar_ate),
        ):
            if vence <= limite:
                resultado.append(
                    DocumentoVencendo(
                        usuario_id=usuario.id,
                        nome=usuario.nome,
                        documento=nome,
                        vence_em=vence,
                        dias_restantes=(vence - hoje).days,
                    )
                )
    return sorted(resultado, key=lambda d: (d.vence_em, d.usuario_id))


@router.post("/motoristas", status_code=status.HTTP_201_CREATED)
def criar(dados: MotoristaCriar, request: Request, db: Db, ator: Gestao) -> MotoristaDetalhe:
    usuario = db.get(Usuario, dados.usuario_id)
    if usuario is None or usuario.perfil != Perfil.MOTORISTA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "O usuário informado não é um motorista"
        )
    m = Motorista(**dados.model_dump())
    db.add(m)
    auditoria.registrar(
        db,
        "motorista.criar",
        request=request,
        usuario=ator,
        recurso="motorista",
        recurso_id=usuario.id,
    )
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO) from erro
    return _detalhe(usuario, m)


@router.get("/motoristas/{usuario_id}")
def obter(usuario_id: IdRota, db: Db, _: Gestao) -> MotoristaDetalhe:
    return _detalhe(*_buscar(db, usuario_id))


@router.get("/motoristas/{usuario_id}/habilitacao")
def habilitacao_do_motorista(
    usuario_id: IdRota, db: Db, _: Gestao, data: date | None = None
) -> Habilitacao:
    usuario, m = _buscar(db, usuario_id)
    return _habilitacao(usuario, m, data or date.today())


@router.put("/motoristas/{usuario_id}")
def atualizar(
    usuario_id: IdRota, dados: MotoristaAtualizar, request: Request, db: Db, ator: Gestao
) -> MotoristaDetalhe:
    usuario, m = _buscar(db, usuario_id)
    for campo, valor in dados.model_dump().items():
        setattr(m, campo, valor)
    auditoria.registrar(
        db,
        "motorista.editar",
        request=request,
        usuario=ator,
        recurso="motorista",
        recurso_id=usuario_id,
    )
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO) from erro
    return _detalhe(usuario, m)


@router.delete("/motoristas/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(usuario_id: IdRota, request: Request, db: Db, ator: Gestao) -> None:
    _, m = _buscar(db, usuario_id)
    db.delete(m)
    auditoria.registrar(
        db,
        "motorista.remover",
        request=request,
        usuario=ator,
        recurso="motorista",
        recurso_id=usuario_id,
    )
    db.commit()


@router.get("/motorista/eu")
def meu_cadastro(db: Db, usuario: SoMotorista) -> MotoristaDetalhe:
    return _detalhe(*_buscar(db, usuario.id))


@router.get("/motorista/eu/habilitacao")
def minha_habilitacao(db: Db, usuario: SoMotorista, data: date | None = None) -> Habilitacao:
    """Funciona também sem cadastro de documentos: aí a resposta é "não pode" com o motivo."""
    return _habilitacao(usuario, db.get(Motorista, usuario.id), data or date.today())
