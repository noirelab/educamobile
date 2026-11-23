from typing import Annotated

from fastapi import APIRouter, status
from sqlalchemy import select

from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar, salvar
from app.geo import para_ponto
from app.models import Estudante, Perfil, Usuario
from app.schemas.estudantes import EstudanteCriar, EstudanteLer
from app.security import UsuarioInterno, exigir_perfil

router = APIRouter(prefix="/estudantes", tags=["estudantes"])
Editor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
CONFLITO = "Parada inexistente"


@router.get("")
def listar(
    db: Db, _: UsuarioInterno, limit: Limite = 50, offset: Deslocamento = 0
) -> list[EstudanteLer]:
    consulta = select(Estudante).order_by(Estudante.id).limit(limit).offset(offset)
    return [EstudanteLer.model_validate(e) for e in db.scalars(consulta)]


@router.get("/{estudante_id}")
def obter(estudante_id: IdRota, db: Db, _: UsuarioInterno) -> EstudanteLer:
    return EstudanteLer.model_validate(buscar(db, Estudante, estudante_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: EstudanteCriar, db: Db, _: Editor) -> EstudanteLer:
    estudante = Estudante(
        **dados.model_dump(exclude={"localizacao"}),
        localizacao=para_ponto(dados.localizacao) if dados.localizacao else None,
    )
    db.add(estudante)
    salvar(db, CONFLITO)
    return EstudanteLer.model_validate(estudante)


@router.put("/{estudante_id}")
def atualizar(estudante_id: IdRota, dados: EstudanteCriar, db: Db, _: Editor) -> EstudanteLer:
    estudante = buscar(db, Estudante, estudante_id)
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
    salvar(db, "O estudante tem registros vinculados")
