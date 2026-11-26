"""Validação dos schemas, sem banco nem HTTP."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app import tempo
from app.geo import Coordenadas, de_ponto, para_ponto
from app.schemas.estudantes import EstudanteCriar
from app.schemas.rotas import RotaSequencia


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


@pytest.mark.parametrize("dias", [0, -1])
def test_nascimento_precisa_estar_no_passado(dias):
    with pytest.raises(ValidationError):
        EstudanteCriar(nome="Ana", data_nascimento=tempo.hoje() - timedelta(days=dias))


def test_sequencia_aceita_lista_de_ids():
    assert RotaSequencia(parada_ids=[1, 2]).parada_ids == [1, 2]
