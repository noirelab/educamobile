"""Validação dos schemas, sem banco nem HTTP."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.geo import Coordenadas, de_ponto, para_ponto
from app.schemas.estudantes import EstudanteCriar
from app.schemas.frequencias import FrequenciaCriar, FrequenciaLote
from app.schemas.polos import MultiPolygonGeoJSON
from app.schemas.rotas import RotaSequencia

ANEL = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]


@pytest.mark.parametrize(
    ("latitude", "longitude"), [(-90.01, 0), (90.01, 0), (0, -180.01), (0, 180.01)]
)
def test_coordenadas_fora_do_intervalo(latitude, longitude):
    with pytest.raises(ValidationError):
        Coordenadas(latitude=latitude, longitude=longitude)


def test_ponto_preserva_latitude_e_longitude_sem_inverter():
    original = Coordenadas(latitude=-25.43, longitude=-49.27)
    assert de_ponto(para_ponto(original)) == original


def test_ponto_nulo():
    assert de_ponto(None) is None


def test_multipolygon_valido():
    MultiPolygonGeoJSON(type="MultiPolygon", coordinates=[[ANEL]])


@pytest.mark.parametrize(
    "coordenadas",
    [
        [],
        [[]],
        [[[[0.0, 0.0], [0.0, 1.0], [0.0, 0.0]]]],
        [[[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 2.0]]]],
        [[[[0.0, 0.0], [0.0, 91.0], [1.0, 1.0], [0.0, 0.0]]]],
        [[[[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]]],
    ],
    ids=["vazio", "sem-anel", "poucos-pontos", "aberto", "fora-do-intervalo", "autointersecao"],
)
def test_multipolygon_invalido(coordenadas):
    with pytest.raises(ValidationError):
        MultiPolygonGeoJSON(type="MultiPolygon", coordinates=coordenadas)


@pytest.mark.parametrize("dias", [0, -1])
def test_nascimento_precisa_estar_no_passado(dias):
    with pytest.raises(ValidationError):
        EstudanteCriar(nome="Ana", data_nascimento=date.today() - timedelta(days=dias))


def test_frequencia_nao_aceita_data_futura():
    with pytest.raises(ValidationError):
        FrequenciaCriar(matricula_id=1, data=date.today() + timedelta(days=1), presente=True)


@pytest.mark.parametrize("quantidade", [0, 501])
def test_limites_do_lote(quantidade):
    registros = [{"matricula_id": i + 1, "presente": True} for i in range(quantidade)]
    with pytest.raises(ValidationError):
        FrequenciaLote(turma_id=1, data=date.today(), registros=registros)


def test_sequencia_aceita_lista_de_ids():
    assert RotaSequencia(parada_ids=[1, 2]).parada_ids == [1, 2]
