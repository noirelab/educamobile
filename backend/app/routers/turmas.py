from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.cadastros import Db, Deslocamento, IdFiltro, IdRota, Limite, buscar, salvar
from app.models import Matricula, Perfil, Turma, Usuario
from app.schemas.turmas import TurmaCriar, TurmaLer
from app.security import UsuarioAtual, exigir_perfil, garantir_escola

router = APIRouter(prefix="/turmas", tags=["turmas"])
Editor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.DIRETOR)]
CONFLITO = "Turma já existe nesse ano letivo ou escola inexistente"


@router.get("")
def listar(
    db: Db,
    usuario: UsuarioAtual,
    escola_id: IdFiltro = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[TurmaLer]:
    if usuario.perfil == Perfil.DIRETOR:
        if escola_id is not None:
            garantir_escola(usuario, escola_id)
        escola_id = usuario.escola_id
    consulta = select(Turma).order_by(Turma.id).limit(limit).offset(offset)
    if escola_id is not None:
        consulta = consulta.where(Turma.escola_id == escola_id)
    return [TurmaLer.model_validate(t) for t in db.scalars(consulta)]


@router.get("/{turma_id}")
def obter(turma_id: IdRota, db: Db, usuario: UsuarioAtual) -> TurmaLer:
    turma = buscar(db, Turma, turma_id)
    garantir_escola(usuario, turma.escola_id)
    return TurmaLer.model_validate(turma)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: TurmaCriar, db: Db, usuario: Editor) -> TurmaLer:
    garantir_escola(usuario, dados.escola_id)
    turma = Turma(**dados.model_dump())
    db.add(turma)
    salvar(db, CONFLITO)
    return TurmaLer.model_validate(turma)


@router.put("/{turma_id}")
def atualizar(turma_id: IdRota, dados: TurmaCriar, db: Db, usuario: Editor) -> TurmaLer:
    turma = buscar(db, Turma, turma_id)
    garantir_escola(usuario, turma.escola_id)
    garantir_escola(usuario, dados.escola_id)
    # Mudar a escola ou o ano reescreveria o histórico e o escopo das matrículas já feitas.
    muda_vinculo = (dados.escola_id, dados.ano_letivo) != (turma.escola_id, turma.ano_letivo)
    if muda_vinculo and db.scalar(
        select(Matricula.id).where(Matricula.turma_id == turma.id).limit(1)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A turma tem matrículas: escola e ano não podem mudar"
        )
    for campo, valor in dados.model_dump().items():
        setattr(turma, campo, valor)
    salvar(db, CONFLITO)
    return TurmaLer.model_validate(turma)


@router.delete("/{turma_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(turma_id: IdRota, db: Db, usuario: Editor) -> None:
    turma = buscar(db, Turma, turma_id)
    garantir_escola(usuario, turma.escola_id)
    db.delete(turma)
    salvar(db, "A turma tem matrículas vinculadas")
