from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cadastros import Deslocamento, IdRota, Limite
from app.db import get_db
from app.geo import de_ponto
from app.models import Parada, Perfil, Rota, RotaParada
from app.schemas.paradas import ParadaLer
from app.schemas.rotas import RotaAtualizar, RotaCriar, RotaLer, RotaSequencia, TrajetoGeoJSON
from app.security import UsuarioAtual, exigir_perfil

router = APIRouter(prefix="/rotas", tags=["rotas"])
Db = Annotated[Session, Depends(get_db)]
PODE_ESCREVER = exigir_perfil(Perfil.ADMIN, Perfil.COORDENADOR)

_RECALCULAR = text(
    """
    UPDATE rota
    SET trajeto = calculo.linha, distancia_m = ST_Length(calculo.linha::geography)
    FROM (
        SELECT CASE WHEN count(*) >= 2
               THEN ST_MakeLine(p.localizacao ORDER BY rp.ordem) END AS linha
        FROM rota_parada rp
        JOIN parada p ON p.id = rp.parada_id
        WHERE rp.rota_id = :id
    ) AS calculo
    WHERE rota.id = :id
    """
)


def recalcular_trajeto(db: Session, rota: Rota) -> None:
    """Recalcula trajeto e distância na transação atual, sem confirmá-la."""
    db.flush()
    db.execute(_RECALCULAR, {"id": rota.id})
    db.refresh(rota)


def _trajeto(rota: Rota) -> TrajetoGeoJSON | None:
    if rota.trajeto is None:
        return None
    return TrajetoGeoJSON(coordinates=list(to_shape(rota.trajeto).coords))


def _ler(db: Session, rotas: list[Rota]) -> list[RotaLer]:
    linhas = db.execute(
        select(RotaParada.rota_id, Parada)
        .join(Parada, Parada.id == RotaParada.parada_id)
        .where(RotaParada.rota_id.in_([r.id for r in rotas]))
        .order_by(RotaParada.rota_id, RotaParada.ordem)
    ).all()
    paradas: dict[int, list[ParadaLer]] = {r.id: [] for r in rotas}
    for rota_id, parada in linhas:
        paradas[rota_id].append(
            ParadaLer(id=parada.id, nome=parada.nome, localizacao=de_ponto(parada.localizacao))
        )
    return [
        RotaLer(
            id=r.id,
            nome=r.nome,
            distancia_m=r.distancia_m,
            paradas=paradas[r.id],
            trajeto=_trajeto(r),
        )
        for r in rotas
    ]


def _buscar(db: Session, rota_id: int, travar: bool = False) -> Rota:
    rota = db.get(Rota, rota_id, with_for_update=travar)
    if rota is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rota não encontrada")
    return rota


def _confirmar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Conflito com outra rota") from erro


@router.get("")
def listar_rotas(
    db: Db,
    _: UsuarioAtual,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[RotaLer]:
    rotas = db.scalars(select(Rota).order_by(Rota.id).limit(limit).offset(offset)).all()
    return _ler(db, list(rotas))


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[PODE_ESCREVER])
def criar_rota(dados: RotaCriar, db: Db) -> RotaLer:
    rota = Rota(nome=dados.nome)
    db.add(rota)
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.get("/{rota_id}")
def obter_rota(rota_id: IdRota, db: Db, _: UsuarioAtual) -> RotaLer:
    return _ler(db, [_buscar(db, rota_id)])[0]


@router.patch("/{rota_id}", dependencies=[PODE_ESCREVER])
def atualizar_rota(rota_id: IdRota, dados: RotaAtualizar, db: Db) -> RotaLer:
    rota = _buscar(db, rota_id)
    rota.nome = dados.nome
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.put("/{rota_id}/paradas", dependencies=[PODE_ESCREVER])
def definir_paradas(rota_id: IdRota, dados: RotaSequencia, db: Db) -> RotaLer:
    rota = _buscar(db, rota_id, travar=True)
    encontradas = set(db.scalars(select(Parada.id).where(Parada.id.in_(dados.parada_ids))))
    faltando = [i for i in dados.parada_ids if i not in encontradas]
    if faltando:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Paradas inexistentes: {faltando}"
        )
    # Esvaziar antes de inserir: a ordem nova pode reutilizar pares já gravados.
    rota.paradas.clear()
    db.flush()
    rota.paradas.extend(
        RotaParada(parada_id=parada_id, ordem=ordem)
        for ordem, parada_id in enumerate(dados.parada_ids)
    )
    recalcular_trajeto(db, rota)
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.delete("/{rota_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[PODE_ESCREVER])
def remover_rota(rota_id: IdRota, db: Db) -> None:
    db.delete(_buscar(db, rota_id))
    db.commit()
