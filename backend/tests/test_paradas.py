import pytest

from app.geo import Coordenadas, para_ponto
from app.models import (
    Parada,
    Perfil,
    Rota,
    RotaParada,
)
from tests.conftest import estudante_de_teste

ESCRITA = [Perfil.ADMIN, Perfil.GESTOR]
LOCAL = {"latitude": -25.43, "longitude": -49.27}


def _parada(db, nome="P", latitude=0.0, longitude=0.0):
    parada = Parada(
        nome=nome, localizacao=para_ponto(Coordenadas(latitude=latitude, longitude=longitude))
    )
    db.add(parada)
    db.flush()
    return parada


def _estudante(db, nome="Ana", parada_id=None):
    return estudante_de_teste(db, nome, parada_id=parada_id)


@pytest.mark.parametrize("perfil", ESCRITA)
def test_crud_de_parada(client, cabecalhos, perfil):
    h = cabecalhos(perfil)
    criada = client.post("/paradas", json={"nome": " Praça ", "localizacao": LOCAL}, headers=h)
    assert criada.status_code == 201
    corpo = criada.json()
    assert corpo["nome"] == "Praça"
    assert corpo["localizacao"] == LOCAL
    url = f"/paradas/{corpo['id']}"

    assert client.get(url, headers=h).json() == corpo
    assert corpo in client.get("/paradas", headers=h).json()

    novo = {"latitude": -25.5, "longitude": -49.3}
    alterada = client.patch(url, json={"nome": "Centro", "localizacao": novo}, headers=h)
    assert alterada.status_code == 200
    assert alterada.json()["nome"] == "Centro"
    assert alterada.json()["localizacao"] == novo

    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": "P", "localizacao": {"latitude": 91, "longitude": 0}},
        {"nome": "P", "localizacao": {"latitude": 0, "longitude": -181}},
        {"nome": "   ", "localizacao": LOCAL},
        {"nome": "P"},
    ],
)
def test_criar_parada_invalida(client, cabecalhos, corpo):
    assert client.post("/paradas", json=corpo, headers=cabecalhos()).status_code == 422


def test_exige_token(client, db):
    url = f"/paradas/{_parada(db).id}"
    assert client.get("/paradas").status_code == 401
    assert client.get(url).status_code == 401
    assert client.get(f"{url}/estudantes").status_code == 401
    assert client.get("/paradas/proximas?latitude=0&longitude=0").status_code == 401
    assert client.post("/paradas", json={"nome": "P", "localizacao": LOCAL}).status_code == 401


def test_associar_e_desassociar_estudante(client, db, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    parada = _parada(db)
    estudante = _estudante(db)
    url = f"/paradas/{parada.id}/estudantes"

    assert client.put(f"{url}/{estudante.id}", headers=h).status_code == 204
    assert client.get(url, headers=h).json() == [{"id": estudante.id, "nome": "Ana"}]

    outra = _parada(db, "Outra")
    outra_url = f"/paradas/{outra.id}/estudantes/{estudante.id}"
    assert client.delete(outra_url, headers=h).status_code == 404

    assert client.delete(f"{url}/{estudante.id}", headers=h).status_code == 204
    assert client.get(url, headers=h).json() == []


def test_associar_inexistentes_da_404(client, db, cabecalhos):
    h = cabecalhos()
    parada = _parada(db)
    estudante = _estudante(db)
    assert client.put(f"/paradas/{parada.id}/estudantes/999999", headers=h).status_code == 404
    assert client.put(f"/paradas/999999/estudantes/{estudante.id}", headers=h).status_code == 404


def test_estudante_da_parada_nao_expoe_dados_pessoais(client, db, cabecalhos):
    parada = _parada(db)
    _estudante(db, "Ana", parada.id)
    corpo = client.get(f"/paradas/{parada.id}/estudantes", headers=cabecalhos()).json()
    assert set(corpo[0]) == {"id", "nome"}


def test_proximas_ordena_e_mede_em_metros(client, db, cabecalhos):
    # No equador, 0,01 grau de longitude mede cerca de 1113,19 m.
    longe = _parada(db, "Longe", 0.0, 0.02)
    perto = _parada(db, "Perto", 0.0, 0.01)
    fora = _parada(db, "Fora", 0.0, 1.0)
    resposta = client.get(
        "/paradas/proximas",
        params={"latitude": 0, "longitude": 0, "raio_m": 3000},
        headers=cabecalhos(Perfil.GESTOR),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [p["id"] for p in corpo] == [perto.id, longe.id]
    assert fora.id not in [p["id"] for p in corpo]
    assert corpo[0]["distancia_m"] == pytest.approx(1113.19, abs=1)
    assert corpo[1]["distancia_m"] == pytest.approx(2226.39, abs=2)


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": 0, "longitude": 0, "raio_m": 50_001},
        {"latitude": 0, "longitude": 0, "raio_m": 0},
        {"latitude": 91, "longitude": 0},
        {"longitude": 0},
    ],
)
def test_proximas_invalida(client, cabecalhos, params):
    assert client.get("/paradas/proximas", params=params, headers=cabecalhos()).status_code == 422


def test_remover_parada_em_rota_da_409(client, db, cabecalhos):
    parada = _parada(db)
    rota = Rota(nome="R1")
    db.add(rota)
    db.flush()
    db.add(RotaParada(rota_id=rota.id, parada_id=parada.id, ordem=0))
    h = cabecalhos()
    # O rollback do conflito desfaria também os dados de teste ainda não confirmados.
    db.commit()
    assert client.delete(f"/paradas/{parada.id}", headers=h).status_code == 409
    assert client.get(f"/paradas/{parada.id}", headers=h).status_code == 200


def test_remover_parada_libera_estudante(client, db, cabecalhos):
    parada = _parada(db)
    estudante = _estudante(db, parada_id=parada.id)
    assert client.delete(f"/paradas/{parada.id}", headers=cabecalhos()).status_code == 204
    db.refresh(estudante)
    assert estudante.parada_id is None
