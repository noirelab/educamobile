from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar, salvar
from app.geo import para_ponto
from app.models import Estudante, Matricula, Perfil, StatusMatricula, Turma, Usuario
from app.routers.matriculas import carregar_turma, validar_ano_letivo
from app.schemas.estudantes import EstudanteCadastrar, EstudanteCriar, EstudanteLer
from app.security import UsuarioAtual, exigir_perfil, garantir_escola

router = APIRouter(prefix="/estudantes", tags=["estudantes"])
Editor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.DIRETOR)]
CONFLITO = "Parada inexistente"


def _ids_da_escola(escola_id: int | None):
    """Estudantes com matrícula ativa na escola."""
    return (
        select(Matricula.estudante_id)
        .join(Turma, Matricula.turma_id == Turma.id)
        .where(Matricula.status == StatusMatricula.ATIVA, Turma.escola_id == escola_id)
    )


def _buscar_no_escopo(db: Session, usuario: Usuario, estudante_id: int) -> Estudante:
    # O escopo vem antes da existência, para o diretor não descobrir quais ids existem.
    if usuario.perfil == Perfil.DIRETOR and not db.scalar(
        _ids_da_escola(usuario.escola_id).where(Matricula.estudante_id == estudante_id)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fora do escopo da sua escola")
    return buscar(db, Estudante, estudante_id)


def _garantir_parada_permitida(usuario: Usuario, atual: int | None, nova: int | None) -> None:
    if usuario.perfil == Perfil.DIRETOR and nova != atual:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Associar parada cabe à logística")


@router.get("")
def listar(
    db: Db, usuario: UsuarioAtual, limit: Limite = 50, offset: Deslocamento = 0
) -> list[EstudanteLer]:
    consulta = select(Estudante).order_by(Estudante.id).limit(limit).offset(offset)
    if usuario.perfil == Perfil.DIRETOR:
        consulta = consulta.where(Estudante.id.in_(_ids_da_escola(usuario.escola_id)))
    return [EstudanteLer.model_validate(e) for e in db.scalars(consulta)]


@router.get("/{estudante_id}")
def obter(estudante_id: IdRota, db: Db, usuario: UsuarioAtual) -> EstudanteLer:
    return EstudanteLer.model_validate(_buscar_no_escopo(db, usuario, estudante_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: EstudanteCadastrar, db: Db, usuario: Editor) -> EstudanteLer:
    _garantir_parada_permitida(usuario, None, dados.parada_id)
    if usuario.perfil == Perfil.DIRETOR and dados.matricula is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Diretor cadastra o estudante já com matrícula"
        )
    turma = None
    if dados.matricula:
        turma = carregar_turma(db, dados.matricula.turma_id)
        garantir_escola(usuario, turma.escola_id)
        validar_ano_letivo(turma, dados.matricula.data_inicio)
    estudante = Estudante(
        **dados.model_dump(exclude={"localizacao", "matricula"}),
        localizacao=para_ponto(dados.localizacao) if dados.localizacao else None,
    )
    db.add(estudante)
    if turma:
        try:
            db.flush()
        except IntegrityError as erro:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO) from erro
        db.add(
            Matricula(
                estudante_id=estudante.id,
                turma_id=turma.id,
                data_inicio=dados.matricula.data_inicio,
                status=StatusMatricula.ATIVA,
            )
        )
    salvar(db, CONFLITO)
    return EstudanteLer.model_validate(estudante)


@router.put("/{estudante_id}")
def atualizar(estudante_id: IdRota, dados: EstudanteCriar, db: Db, usuario: Editor) -> EstudanteLer:
    estudante = _buscar_no_escopo(db, usuario, estudante_id)
    _garantir_parada_permitida(usuario, estudante.parada_id, dados.parada_id)
    for campo, valor in dados.model_dump(exclude={"localizacao"}).items():
        setattr(estudante, campo, valor)
    estudante.localizacao = para_ponto(dados.localizacao) if dados.localizacao else None
    salvar(db, CONFLITO)
    return EstudanteLer.model_validate(estudante)


@router.delete(
    "/{estudante_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[exigir_perfil(Perfil.ADMIN)],
)
def remover(estudante_id: IdRota, db: Db) -> None:
    db.delete(buscar(db, Estudante, estudante_id))
    salvar(db, "O estudante tem matrículas vinculadas")
