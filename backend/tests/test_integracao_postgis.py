"""Integridade referencial e consultas espaciais contra o PostGIS real."""

import pytest
from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.geo import Coordenadas, para_ponto
from app.models import (
    SRID,
    Parada,
    RotaParada,
)
from tests.conftest import estudante_de_teste, rota_de_teste

QUADRADO = "MULTIPOLYGON(((-49.3 -25.5,-49.2 -25.5,-49.2 -25.4,-49.3 -25.4,-49.3 -25.5)))"


def _ponto(latitude, longitude):
    return para_ponto(Coordenadas(latitude=latitude, longitude=longitude))


def _falha_integridade(db, acao):
    with pytest.raises(IntegrityError), db.begin_nested():
        acao()
        db.flush()


# Integridade referencial


def test_remover_parada_solta_estudante_mas_nao_rota(db):
    estudante = estudante_de_teste(db)
    livre = Parada(nome="Livre", localizacao=_ponto(-25.4, -49.2))
    usada = Parada(nome="Usada", localizacao=_ponto(-25.5, -49.3))
    rota = rota_de_teste(db, "R1")
    db.add_all([livre, usada])
    db.flush()
    estudante.parada_id = livre.id
    db.add(RotaParada(rota_id=rota.id, parada_id=usada.id, ordem=1))
    db.flush()

    db.delete(livre)
    db.flush()
    db.refresh(estudante)
    assert estudante.parada_id is None
    _falha_integridade(db, lambda: db.delete(usada))


# Consultas espaciais


def test_st_distance_em_metros(db):
    """Um grau de latitude mede cerca de 110,7 km perto de 25 graus sul."""
    origem = func.ST_GeogFromText("SRID=4326;POINT(-49 -25)")
    destino = func.ST_GeogFromText("SRID=4326;POINT(-49 -26)")
    assert db.scalar(select(func.ST_Distance(origem, destino))) == pytest.approx(110_700, rel=0.005)


def test_st_distance_por_paradas_cadastradas(db):
    a = Parada(nome="A", localizacao=_ponto(-25.43, -49.27))
    b = Parada(nome="B", localizacao=_ponto(-25.44, -49.27))
    db.add_all([a, b])
    db.flush()
    pa, pb = aliased(Parada), aliased(Parada)
    consulta = select(
        func.ST_Distance(cast(pa.localizacao, Geography), cast(pb.localizacao, Geography))
    ).where(pa.id == a.id, pb.id == b.id)
    assert db.scalar(consulta) == pytest.approx(1_107, rel=0.005)


def test_st_contains_separa_dentro_fora_e_borda(db):
    area = WKTElement(QUADRADO, srid=SRID)
    casos = {
        (-25.45, -49.25): True,
        (-25.45, -49.35): False,
        (-25.4, -49.25): False,  # ST_Contains não inclui a borda
    }
    for (latitude, longitude), esperado in casos.items():
        assert db.scalar(select(func.ST_Contains(area, _ponto(latitude, longitude)))) is esperado


def test_st_contains_nao_confunde_latitude_com_longitude(db):
    area = WKTElement(QUADRADO, srid=SRID)
    assert db.scalar(select(func.ST_Contains(area, _ponto(-25.45, -49.25)))) is True
    trocado = WKTElement("POINT(-25.45 -49.25)", srid=SRID)
    assert db.scalar(select(func.ST_Contains(area, trocado))) is False


def test_indices_espaciais_existem(db):
    consulta = text("SELECT indexname FROM pg_indexes WHERE indexdef ILIKE '%USING gist%'")
    nomes = set(db.scalars(consulta))
    assert {
        "idx_escola_localizacao",
        "idx_parada_localizacao",
        "idx_rota_trajeto",
    } <= nomes
