from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cadastros import Deslocamento, IdRota, Limite
from app.db import get_db
from app.geo import de_ponto
from app.models import Inscricao, Parada, Perfil, Rota, RotaParada, Sentido
from app.schemas.paradas import ParadaLer
from app.schemas.rotas import (
    ItemDoItinerario,
    RotaAtualizar,
    RotaCriar,
    RotaLer,
    RotaSequencia,
    TrajetoGeoJSON,
)
from app.security import UsuarioInterno, exigir_perfil

router = APIRouter(prefix="/rotas", tags=["rotas"])
Db = Annotated[Session, Depends(get_db)]
PODE_ESCREVER = exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)

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
        select(RotaParada, Parada)
        .join(Parada, Parada.id == RotaParada.parada_id)
        .where(RotaParada.rota_id.in_([r.id for r in rotas]))
        .order_by(RotaParada.rota_id, RotaParada.ordem)
    ).all()
    paradas: dict[int, list[ParadaLer]] = {r.id: [] for r in rotas}
    itinerario: dict[int, list[ItemDoItinerario]] = {r.id: [] for r in rotas}
    for rp, parada in linhas:
        paradas[rp.rota_id].append(
            ParadaLer(id=parada.id, nome=parada.nome, localizacao=de_ponto(parada.localizacao))
        )
        itinerario[rp.rota_id].append(
            ItemDoItinerario(
                parada_id=parada.id,
                ordem=rp.ordem,
                horario_previsto=rp.horario_previsto,
                raio_cerca_m=rp.raio_cerca_m,
            )
        )
    return [
        RotaLer(
            id=r.id,
            nome=r.nome,
            escola_id=r.escola_id,
            turno=r.turno,
            sentido=r.sentido,
            veiculo_id=r.veiculo_id,
            motorista_id=r.motorista_id,
            distancia_m=r.distancia_m,
            paradas=paradas[r.id],
            itinerario=itinerario[r.id],
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
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Nome já usado, ou escola, veículo ou motorista inexistente"
        ) from erro


def _exigir_sem_inscricoes(db: Session, rota: Rota) -> None:
    if db.scalar(
        select(Inscricao.id).where(Inscricao.rota_id == rota.id, Inscricao.ativa.is_(True)).limit(1)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A rota tem inscrições ativas: mude escola, turno ou sentido só depois de encerrá-las",
        )


def _exigir_inscricoes_cobertas(db: Session, rota: Rota, novas: set[int]) -> None:
    usadas = set(
        db.scalars(
            select(Inscricao.parada_id).where(
                Inscricao.rota_id == rota.id, Inscricao.ativa.is_(True)
            )
        )
    )
    if usadas - novas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Paradas com inscrições ativas não podem sair da rota: {sorted(usadas - novas)}",
        )


_PONTA_DA_ESCOLA = text(
    """
    SELECT ST_DWithin(p.localizacao::geography, e.localizacao::geography, e.raio_cerca_m)
    FROM rota_parada rp
    JOIN parada p ON p.id = rp.parada_id
    JOIN escola e ON e.id = :escola
    WHERE rp.rota_id = :rota
    ORDER BY rp.ordem {sentido}
    LIMIT 1
    """
)


def _validar_ponto_da_escola(db: Session, rota: Rota) -> None:
    """Na ida a última parada é a escola; na volta, a primeira. Rota vazia não tem o que validar."""
    ordem = "DESC" if rota.sentido == Sentido.IDA else "ASC"
    sql = text(_PONTA_DA_ESCOLA.text.format(sentido=ordem))
    dentro = db.scalar(sql, {"rota": rota.id, "escola": rota.escola_id})
    if dentro is False:
        onde = "última" if rota.sentido == Sentido.IDA else "primeira"
        # Nada do que foi alterado nesta requisição pode sobrar na sessão.
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"A {onde} parada da rota de {rota.sentido.value} precisa ser a escola "
            "(dentro do raio da cerca da escola)",
        )


@router.get("")
def listar_rotas(
    db: Db,
    _: UsuarioInterno,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> list[RotaLer]:
    rotas = db.scalars(select(Rota).order_by(Rota.id).limit(limit).offset(offset)).all()
    return _ler(db, list(rotas))


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[PODE_ESCREVER])
def criar_rota(dados: RotaCriar, db: Db) -> RotaLer:
    rota = Rota(**dados.model_dump())
    db.add(rota)
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.get("/{rota_id}")
def obter_rota(rota_id: IdRota, db: Db, _: UsuarioInterno) -> RotaLer:
    return _ler(db, [_buscar(db, rota_id)])[0]


@router.patch("/{rota_id}", dependencies=[PODE_ESCREVER])
def atualizar_rota(rota_id: IdRota, dados: RotaAtualizar, db: Db) -> RotaLer:
    rota = _buscar(db, rota_id)
    mudancas = dados.model_dump(exclude_unset=True)
    if {"escola_id", "turno", "sentido"} & mudancas.keys():
        if any(
            rota.__dict__[c] != v
            for c, v in mudancas.items()
            if c in {"escola_id", "turno", "sentido"}
        ):
            _exigir_sem_inscricoes(db, rota)
    for campo, valor in mudancas.items():
        setattr(rota, campo, valor)
    if {"escola_id", "sentido"} & mudancas.keys():
        db.flush()
        _validar_ponto_da_escola(db, rota)
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.put("/{rota_id}/paradas", dependencies=[PODE_ESCREVER])
def definir_paradas(rota_id: IdRota, dados: RotaSequencia, db: Db) -> RotaLer:
    rota = _buscar(db, rota_id, travar=True)
    itens = dados.itens()
    ids = [i.parada_id for i in itens]
    encontradas = set(db.scalars(select(Parada.id).where(Parada.id.in_(ids))))
    faltando = [i for i in ids if i not in encontradas]
    if faltando:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Paradas inexistentes: {faltando}"
        )
    # Esvaziar antes de inserir: a ordem nova pode reutilizar pares já gravados.
    _exigir_inscricoes_cobertas(db, rota, set(ids))
    rota.paradas.clear()
    db.flush()
    rota.paradas.extend(
        RotaParada(
            parada_id=item.parada_id,
            ordem=ordem,
            horario_previsto=item.horario_previsto,
            raio_cerca_m=item.raio_cerca_m,
        )
        for ordem, item in enumerate(itens)
    )
    db.flush()
    _validar_ponto_da_escola(db, rota)
    recalcular_trajeto(db, rota)
    _confirmar(db)
    return _ler(db, [rota])[0]


@router.delete("/{rota_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[PODE_ESCREVER])
def remover_rota(rota_id: IdRota, db: Db) -> None:
    db.delete(_buscar(db, rota_id))
    db.commit()
