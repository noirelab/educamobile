from typing import Annotated

from fastapi import APIRouter, status
from sqlalchemy import select

from app.cadastros import Db, Deslocamento, IdFiltro, IdRota, Limite, buscar, salvar
from app.models import Perfil, Professor, Usuario
from app.schemas.professores import ProfessorCriar, ProfessorLer
from app.security import exigir_perfil, garantir_escola

router = APIRouter(prefix="/professores", tags=["professores"])
Editor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.DIRETOR)]
CONFLITO = "E-mail já cadastrado ou escola inexistente"


@router.get("")
def listar(
    db: Db,
    usuario: Editor,
    escola_id: IdFiltro = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[ProfessorLer]:
    if usuario.perfil == Perfil.DIRETOR:
        if escola_id is not None:
            garantir_escola(usuario, escola_id)
        escola_id = usuario.escola_id
    consulta = select(Professor).order_by(Professor.id).limit(limit).offset(offset)
    if escola_id is not None:
        consulta = consulta.where(Professor.escola_id == escola_id)
    return [ProfessorLer.model_validate(p) for p in db.scalars(consulta)]


@router.get("/{professor_id}")
def obter(professor_id: IdRota, db: Db, usuario: Editor) -> ProfessorLer:
    professor = buscar(db, Professor, professor_id)
    garantir_escola(usuario, professor.escola_id)
    return ProfessorLer.model_validate(professor)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: ProfessorCriar, db: Db, usuario: Editor) -> ProfessorLer:
    garantir_escola(usuario, dados.escola_id)
    professor = Professor(**dados.model_dump())
    db.add(professor)
    salvar(db, CONFLITO)
    return ProfessorLer.model_validate(professor)


@router.put("/{professor_id}")
def atualizar(professor_id: IdRota, dados: ProfessorCriar, db: Db, usuario: Editor) -> ProfessorLer:
    professor = buscar(db, Professor, professor_id)
    garantir_escola(usuario, professor.escola_id)
    garantir_escola(usuario, dados.escola_id)
    for campo, valor in dados.model_dump().items():
        setattr(professor, campo, valor)
    salvar(db, CONFLITO)
    return ProfessorLer.model_validate(professor)


@router.delete("/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(professor_id: IdRota, db: Db, usuario: Editor) -> None:
    professor = buscar(db, Professor, professor_id)
    garantir_escola(usuario, professor.escola_id)
    db.delete(professor)
    salvar(db, "Professor em uso")
