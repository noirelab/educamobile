from fastapi import APIRouter, status
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sqlalchemy import func, select

from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar, salvar
from app.models import SRID, Escola, Perfil, Polo
from app.schemas.escolas import EscolaLer
from app.schemas.polos import PoloCriar, PoloLer
from app.security import UsuarioAtual, exigir_perfil

router = APIRouter(prefix="/polos", tags=["polos"])
CONFLITO = "Já existe um polo com esse nome"


def _area(dados: PoloCriar):
    return from_shape(shape(dados.area.model_dump()), srid=SRID) if dados.area else None


@router.get("")
def listar(db: Db, _: UsuarioAtual, limit: Limite = 50, offset: Deslocamento = 0) -> list[PoloLer]:
    consulta = select(Polo).order_by(Polo.id).limit(limit).offset(offset)
    return [PoloLer.model_validate(p) for p in db.scalars(consulta)]


@router.get("/{polo_id}")
def obter(polo_id: IdRota, db: Db, _: UsuarioAtual) -> PoloLer:
    return PoloLer.model_validate(buscar(db, Polo, polo_id))


@router.get("/{polo_id}/escolas-na-area")
def escolas_na_area(polo_id: IdRota, db: Db, _: UsuarioAtual) -> list[EscolaLer]:
    """Escolas dentro da área do polo, pela localização, mesmo sem vínculo por polo_id."""
    polo = buscar(db, Polo, polo_id)
    consulta = (
        select(Escola).where(func.ST_Contains(polo.area, Escola.localizacao)).order_by(Escola.nome)
    )
    return [EscolaLer.model_validate(e) for e in db.scalars(consulta)]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[exigir_perfil(Perfil.ADMIN)])
def criar(dados: PoloCriar, db: Db) -> PoloLer:
    polo = Polo(nome=dados.nome, area=_area(dados))
    db.add(polo)
    salvar(db, CONFLITO)
    return PoloLer.model_validate(polo)


@router.put("/{polo_id}", dependencies=[exigir_perfil(Perfil.ADMIN)])
def atualizar(polo_id: IdRota, dados: PoloCriar, db: Db) -> PoloLer:
    polo = buscar(db, Polo, polo_id)
    polo.nome = dados.nome
    polo.area = _area(dados)
    salvar(db, CONFLITO)
    return PoloLer.model_validate(polo)


@router.delete(
    "/{polo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[exigir_perfil(Perfil.ADMIN)],
)
def remover(polo_id: IdRota, db: Db) -> None:
    db.delete(buscar(db, Polo, polo_id))
    salvar(db, "Polo em uso")
