from datetime import date, timedelta

import pytest

from app.models import Perfil

DADOS = {
    "nome": "Maria",
    "data_nascimento": "2012-05-10",
    "nome_responsavel": "Joana",
    "localizacao": {"latitude": -25.4, "longitude": -49.2},
}


def test_crud_admin(client, cabecalhos):
    h = cabecalhos()
    criado = client.post("/estudantes", json=DADOS, headers=h)
    assert criado.status_code == 201
    corpo = criado.json()
    assert corpo["localizacao"] == DADOS["localizacao"]
    url = f"/estudantes/{corpo['id']}"
    assert client.get(url, headers=h).json() == corpo

    sem_local = {"nome": "Maria S.", "data_nascimento": "2012-05-10"}
    atualizado = client.put(url, json=sem_local, headers=h).json()
    assert atualizado["nome"] == "Maria S."
    assert atualizado["localizacao"] is None
    assert atualizado["nome_responsavel"] is None

    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize(
    "alteracao",
    [
        {"nome": ""},
        {"data_nascimento": "ontem"},
        {"data_nascimento": (date.today() + timedelta(days=1)).isoformat()},
        {"localizacao": {"latitude": 100, "longitude": 0}},
    ],
)
def test_validacao(client, cabecalhos, alteracao):
    h = cabecalhos()
    assert client.post("/estudantes", json={**DADOS, **alteracao}, headers=h).status_code == 422


def test_parada_inexistente_da_409(client, cabecalhos):
    com_parada = {**DADOS, "parada_id": 999999}
    assert client.post("/estudantes", json=com_parada, headers=cabecalhos()).status_code == 409


def test_gestor_edita_mas_so_admin_remove(client, cabecalhos):
    criado = client.post("/estudantes", json=DADOS, headers=cabecalhos(Perfil.GESTOR))
    assert criado.status_code == 201
    url = f"/estudantes/{criado.json()['id']}"
    h = cabecalhos(Perfil.GESTOR)
    assert client.put(url, json=DADOS, headers=h).status_code == 200
    assert client.delete(url, headers=h).status_code == 403


def test_exige_token(client):
    assert client.get("/estudantes").status_code == 401
