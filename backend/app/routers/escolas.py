from fastapi import APIRouter, status
from sqlalchemy import select

from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar, salvar
from app.geo import para_ponto
from app.models import Escola, Perfil
from app.schemas.escolas import EscolaCriar, EscolaLer
from app.security import UsuarioInterno, exigir_perfil

router = APIRouter(prefix="/escolas", tags=["escolas"])
CONFLITO = "Código INEP já cadastrado"


@router.get("")
def listar(
    db: Db,
    _: UsuarioInterno,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[EscolaLer]:
    consulta = select(Escola).order_by(Escola.id).limit(limit).offset(offset)
    return [EscolaLer.model_validate(e) for e in db.scalars(consulta)]


@router.get("/{escola_id}")
def obter(escola_id: IdRota, db: Db, _: UsuarioInterno) -> EscolaLer:
    return EscolaLer.model_validate(buscar(db, Escola, escola_id))


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[exigir_perfil(Perfil.ADMIN)])
def criar(dados: EscolaCriar, db: Db) -> EscolaLer:
    escola = Escola(
        **dados.model_dump(exclude={"localizacao", "confirma_recebimento"}),
        localizacao=para_ponto(dados.localizacao),
        confirma_recebimento=dados.confirma_recebimento is not False,
    )
    db.add(escola)
    salvar(db, CONFLITO)
    return EscolaLer.model_validate(escola)


@router.put("/{escola_id}", dependencies=[exigir_perfil(Perfil.ADMIN)])
def atualizar(escola_id: IdRota, dados: EscolaCriar, db: Db) -> EscolaLer:
    escola = buscar(db, Escola, escola_id)
    # Novo na reformulação: `confirma_recebimento` omitido fica como está, para o formulário que
    # ainda não tem o campo não religar a confirmação de uma escola que a desligou.
    ignorar = {"localizacao"} | (
        {"confirma_recebimento"} if dados.confirma_recebimento is None else set()
    )
    for campo, valor in dados.model_dump(exclude=ignorar).items():
        setattr(escola, campo, valor)
    escola.localizacao = para_ponto(dados.localizacao)
    salvar(db, CONFLITO)
    return EscolaLer.model_validate(escola)


@router.delete(
    "/{escola_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[exigir_perfil(Perfil.ADMIN)],
)
def remover(escola_id: IdRota, db: Db) -> None:
    db.delete(buscar(db, Escola, escola_id))
    salvar(db, "A escola tem registros vinculados")
