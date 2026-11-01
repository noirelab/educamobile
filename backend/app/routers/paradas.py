from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography
from sqlalchemy import cast, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cadastros import Deslocamento, IdRota
from app.db import get_db
from app.geo import de_ponto, para_ponto
from app.models import (
    SRID,
    Estudante,
    Matricula,
    Parada,
    Perfil,
    Rota,
    RotaParada,
    StatusMatricula,
    Turma,
)
from app.routers.rotas import recalcular_trajeto
from app.schemas.paradas import (
    EstudanteDaParada,
    ParadaAtualizar,
    ParadaCriar,
    ParadaLer,
    ParadaProxima,
)
from app.security import UsuarioAtual, exigir_perfil

router = APIRouter(prefix="/paradas", tags=["paradas"])
Db = Annotated[Session, Depends(get_db)]
PODE_ESCREVER = exigir_perfil(Perfil.ADMIN, Perfil.COORDENADOR)
RAIO_MAXIMO_M = 50_000


def _ler(parada: Parada) -> ParadaLer:
    return ParadaLer(id=parada.id, nome=parada.nome, localizacao=de_ponto(parada.localizacao))


def _buscar(db: Session, parada_id: int) -> Parada:
    parada = db.get(Parada, parada_id)
    if parada is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parada não encontrada")
    return parada


def _buscar_estudante(db: Session, estudante_id: int) -> Estudante:
    estudante = db.get(Estudante, estudante_id)
    if estudante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante não encontrado")
    return estudante


@router.get("")
def listar_paradas(
    db: Db,
    _: UsuarioAtual,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Deslocamento = 0,
) -> list[ParadaLer]:
    paradas = db.scalars(select(Parada).order_by(Parada.id).limit(limit).offset(offset))
    return [_ler(p) for p in paradas]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[PODE_ESCREVER])
def criar_parada(dados: ParadaCriar, db: Db) -> ParadaLer:
    parada = Parada(nome=dados.nome, localizacao=para_ponto(dados.localizacao))
    db.add(parada)
    db.commit()
    return _ler(parada)


# Declarada antes de /{parada_id} para "proximas" não ser lido como id.
@router.get("/proximas")
def paradas_proximas(
    db: Db,
    _: UsuarioAtual,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    raio_m: Annotated[float, Query(gt=0, le=RAIO_MAXIMO_M)] = 1_000,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ParadaProxima]:
    alvo = cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), SRID), Geography)
    local = cast(Parada.localizacao, Geography)
    distancia = func.ST_Distance(local, alvo)
    linhas = db.execute(
        select(Parada, distancia.label("distancia_m"))
        .where(func.ST_DWithin(local, alvo, raio_m))
        .order_by(distancia, Parada.id)
        .limit(limit)
    ).all()
    return [
        ParadaProxima(**_ler(parada).model_dump(), distancia_m=distancia_m)
        for parada, distancia_m in linhas
    ]


@router.get("/{parada_id}")
def obter_parada(parada_id: IdRota, db: Db, _: UsuarioAtual) -> ParadaLer:
    return _ler(_buscar(db, parada_id))


@router.patch("/{parada_id}", dependencies=[PODE_ESCREVER])
def atualizar_parada(parada_id: IdRota, dados: ParadaAtualizar, db: Db) -> ParadaLer:
    parada = _buscar(db, parada_id)
    if dados.nome is not None:
        parada.nome = dados.nome
    if dados.localizacao is not None:
        parada.localizacao = para_ponto(dados.localizacao)
        db.flush()
        rotas = db.scalars(
            select(Rota)
            .join(RotaParada, RotaParada.rota_id == Rota.id)
            .where(RotaParada.parada_id == parada_id)
            .order_by(Rota.id)
            .with_for_update(of=Rota)
        ).all()
        for rota in rotas:
            recalcular_trajeto(db, rota)
    db.commit()
    return _ler(parada)


@router.delete("/{parada_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[PODE_ESCREVER])
def remover_parada(parada_id: IdRota, db: Db) -> None:
    db.delete(_buscar(db, parada_id))
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Parada usada em rota") from erro


@router.get("/{parada_id}/estudantes")
def listar_estudantes(parada_id: IdRota, db: Db, usuario: UsuarioAtual) -> list[EstudanteDaParada]:
    _buscar(db, parada_id)
    consulta = select(Estudante).where(Estudante.parada_id == parada_id).order_by(Estudante.id)
    if usuario.perfil == Perfil.DIRETOR:
        consulta = consulta.where(
            exists().where(
                Matricula.estudante_id == Estudante.id,
                Matricula.status == StatusMatricula.ATIVA,
                Matricula.turma_id == Turma.id,
                Turma.escola_id == usuario.escola_id,
            )
        )
    return [EstudanteDaParada.model_validate(e) for e in db.scalars(consulta)]


@router.put(
    "/{parada_id}/estudantes/{estudante_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[PODE_ESCREVER],
)
def associar_estudante(parada_id: IdRota, estudante_id: IdRota, db: Db) -> None:
    _buscar(db, parada_id)
    _buscar_estudante(db, estudante_id).parada_id = parada_id
    db.commit()


@router.delete(
    "/{parada_id}/estudantes/{estudante_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[PODE_ESCREVER],
)
def desassociar_estudante(parada_id: IdRota, estudante_id: IdRota, db: Db) -> None:
    estudante = _buscar_estudante(db, estudante_id)
    if estudante.parada_id != parada_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante não associado a esta parada")
    estudante.parada_id = None
    db.commit()
