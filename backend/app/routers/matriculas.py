from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cadastros import Deslocamento, IdFiltro, IdRota
from app.db import get_db
from app.models import (
    Estudante,
    Frequencia,
    Matricula,
    Perfil,
    StatusMatricula,
    Turma,
    Usuario,
)
from app.schemas.matriculas import (
    MatriculaCriar,
    MatriculaEncerrar,
    MatriculaLer,
    TransferenciaCriar,
)
from app.security import exigir_perfil, garantir_escola

router = APIRouter(prefix="/matriculas", tags=["matrículas"])
Db = Annotated[Session, Depends(get_db)]
Gestor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.DIRETOR)]
Limite = Annotated[int, Query(ge=1, le=500)]


def nao_encontrado(recurso: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{recurso} não encontrado(a)")


def invalido(mensagem: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem)


def no_escopo(consulta: Select, usuario: Usuario) -> Select:
    """Restringe à escola do diretor. A consulta precisa já ter feito join com Turma."""
    if usuario.perfil == Perfil.DIRETOR:
        return consulta.where(Turma.escola_id == usuario.escola_id)
    return consulta


def carregar_matricula(
    db: Session, matricula_id: int, usuario: Usuario, travar: bool = False
) -> Matricula:
    matricula = db.get(Matricula, matricula_id, with_for_update=travar or None)
    if matricula is None:
        raise nao_encontrado("Matrícula")
    garantir_escola(usuario, db.get(Turma, matricula.turma_id).escola_id)
    return matricula


def carregar_turma(db: Session, turma_id: int) -> Turma:
    turma = db.get(Turma, turma_id)
    if turma is None:
        raise nao_encontrado("Turma")
    return turma


def validar_ano_letivo(turma: Turma, data_inicio) -> None:
    if data_inicio.year != turma.ano_letivo:
        raise invalido("A data precisa estar no ano letivo da turma")


def _garantir_estudante_conhecido(db: Session, usuario: Usuario, estudante_id: int) -> None:
    """Diretor só matricula quem já passou pela escola: matricular daria acesso aos dados.

    Estudante novo entra por POST /estudantes com matrícula. A resposta é a mesma para id
    inexistente, para não revelar quais estudantes existem.
    """
    if usuario.perfil == Perfil.DIRETOR:
        passou_pela_escola = db.scalar(
            select(Matricula.id)
            .join(Turma)
            .where(Matricula.estudante_id == estudante_id, Turma.escola_id == usuario.escola_id)
            .limit(1)
        )
        if passou_pela_escola is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Fora do escopo da sua escola")
    elif db.get(Estudante, estudante_id) is None:
        raise nao_encontrado("Estudante")


def _recusar_frequencias_a_partir_de(db: Session, matricula: Matricula, data) -> None:
    conflito = db.scalar(
        select(Frequencia.data)
        .where(Frequencia.matricula_id == matricula.id, Frequencia.data >= data)
        .limit(1)
    )
    if conflito is not None:
        raise invalido(f"A matrícula já tem frequência lançada em {conflito}; ajuste a data")


def _confirmar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Estudante já tem matrícula ativa") from erro


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: MatriculaCriar, db: Db, usuario: Gestor) -> MatriculaLer:
    turma = carregar_turma(db, dados.turma_id)
    garantir_escola(usuario, turma.escola_id)
    _garantir_estudante_conhecido(db, usuario, dados.estudante_id)
    validar_ano_letivo(turma, dados.data_inicio)
    sobreposta = db.scalar(
        select(Matricula.id)
        .where(
            Matricula.estudante_id == dados.estudante_id, Matricula.data_fim >= dados.data_inicio
        )
        .limit(1)
    )
    if sobreposta is not None:
        raise invalido("O início precisa ser posterior ao fim da matrícula anterior")
    matricula = Matricula(**dados.model_dump(), status=StatusMatricula.ATIVA)
    db.add(matricula)
    _confirmar(db)
    return MatriculaLer.model_validate(matricula)


@router.get("")
def listar(
    db: Db,
    usuario: Gestor,
    estudante_id: IdFiltro = None,
    turma_id: IdFiltro = None,
    situacao: Annotated[StatusMatricula | None, Query(alias="status")] = None,
    limite: Limite = 100,
    deslocamento: Deslocamento = 0,
) -> list[MatriculaLer]:
    consulta = no_escopo(select(Matricula).join(Turma), usuario)
    if estudante_id is not None:
        consulta = consulta.where(Matricula.estudante_id == estudante_id)
    if turma_id is not None:
        consulta = consulta.where(Matricula.turma_id == turma_id)
    if situacao is not None:
        consulta = consulta.where(Matricula.status == situacao)
    consulta = consulta.order_by(Matricula.id).limit(limite).offset(deslocamento)
    return [MatriculaLer.model_validate(m) for m in db.scalars(consulta)]


@router.get("/historico/{estudante_id}")
def historico(estudante_id: IdRota, db: Db, usuario: Gestor) -> list[MatriculaLer]:
    """Vínculos do estudante, do mais antigo ao mais recente. Diretor vê os da própria escola."""
    if usuario.perfil != Perfil.DIRETOR and db.get(Estudante, estudante_id) is None:
        raise nao_encontrado("Estudante")
    consulta = (
        no_escopo(select(Matricula).join(Turma), usuario)
        .where(Matricula.estudante_id == estudante_id)
        .order_by(Matricula.data_inicio, Matricula.id)
    )
    return [MatriculaLer.model_validate(m) for m in db.scalars(consulta)]


@router.post("/transferencias", status_code=status.HTTP_201_CREATED)
def transferir(dados: TransferenciaCriar, db: Db, usuario: Gestor) -> MatriculaLer:
    atual = db.scalar(
        select(Matricula)
        .where(
            Matricula.estudante_id == dados.estudante_id,
            Matricula.status == StatusMatricula.ATIVA,
        )
        .with_for_update()
    )
    if atual is None:
        if usuario.perfil == Perfil.DIRETOR:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Fora do escopo da sua escola")
        raise invalido("Estudante sem matrícula ativa")
    garantir_escola(usuario, db.get(Turma, atual.turma_id).escola_id)
    destino = carregar_turma(db, dados.turma_destino_id)
    # Transferência entre escolas é do administrador: o diretor não acessa a escola de destino.
    garantir_escola(usuario, destino.escola_id)
    if destino.id == atual.turma_id:
        raise invalido("A turma de destino é a turma atual")
    if dados.data < atual.data_inicio:
        raise invalido("A transferência não pode ser anterior ao início da matrícula atual")
    validar_ano_letivo(destino, dados.data)
    _recusar_frequencias_a_partir_de(db, atual, dados.data)

    atual.status = StatusMatricula.TRANSFERIDA
    atual.data_fim = dados.data
    # O índice único parcial exige liberar o vínculo ativo antes de inserir o novo.
    db.flush()
    nova = Matricula(
        estudante_id=dados.estudante_id,
        turma_id=destino.id,
        data_inicio=dados.data,
        status=StatusMatricula.ATIVA,
    )
    db.add(nova)
    _confirmar(db)
    return MatriculaLer.model_validate(nova)


@router.get("/{matricula_id}")
def consultar(matricula_id: IdRota, db: Db, usuario: Gestor) -> MatriculaLer:
    return MatriculaLer.model_validate(carregar_matricula(db, matricula_id, usuario))


@router.post("/{matricula_id}/encerrar")
def encerrar(
    matricula_id: IdRota, dados: MatriculaEncerrar, db: Db, usuario: Gestor
) -> MatriculaLer:
    matricula = carregar_matricula(db, matricula_id, usuario, travar=True)
    if matricula.status != StatusMatricula.ATIVA:
        raise HTTPException(status.HTTP_409_CONFLICT, "A matrícula não está ativa")
    if dados.data_fim < matricula.data_inicio:
        raise invalido("O encerramento não pode ser anterior ao início da matrícula")
    _recusar_frequencias_a_partir_de(db, matricula, dados.data_fim + timedelta(days=1))
    matricula.status = StatusMatricula.ENCERRADA
    matricula.data_fim = dados.data_fim
    db.commit()
    return MatriculaLer.model_validate(matricula)
