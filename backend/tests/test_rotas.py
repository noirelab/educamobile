import pytest

from app.geo import Coordenadas, para_ponto
from app.models import Parada, Perfil

# Em WGS 84, um grau de latitude a partir do equador mede 110574,39 m.
UM_GRAU_LATITUDE_M = 110_574.39


def _parada(db, latitude, longitude=0.0, nome="P"):
    parada = Parada(
        nome=nome, localizacao=para_ponto(Coordenadas(latitude=latitude, longitude=longitude))
    )
    db.add(parada)
    db.flush()
    return parada


def _rota(client, h, nome="Linha 1"):
    resposta = client.post("/rotas", json={"nome": nome}, headers=h)
    assert resposta.status_code == 201
    return resposta.json()


@pytest.mark.parametrize("perfil", [Perfil.ADMIN, Perfil.COORDENADOR])
def test_crud_de_rota(client, cabecalhos, perfil):
    h = cabecalhos(perfil)
    rota = _rota(client, h)
    assert rota["paradas"] == []
    assert rota["trajeto"] is None
    assert rota["distancia_m"] is None
    url = f"/rotas/{rota['id']}"

    assert client.get(url, headers=h).json() == rota
    assert rota in client.get("/rotas", headers=h).json()
    alterada = client.patch(url, json={"nome": "Linha 2"}, headers=h)
    assert alterada.json()["nome"] == "Linha 2"
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


def test_nome_repetido_da_409(client, cabecalhos):
    h = cabecalhos()
    _rota(client, h, "Igual")
    assert client.post("/rotas", json={"nome": "Igual"}, headers=h).status_code == 409


def test_nome_vazio_da_422(client, cabecalhos):
    assert client.post("/rotas", json={"nome": " "}, headers=cabecalhos()).status_code == 422


def test_exige_token(client):
    assert client.get("/rotas").status_code == 401
    assert client.post("/rotas", json={"nome": "R"}).status_code == 401
    assert client.put("/rotas/1/paradas", json={"parada_ids": []}).status_code == 401


def test_diretor_le_mas_nao_escreve(client, cabecalhos):
    rota = _rota(client, cabecalhos())
    url = f"/rotas/{rota['id']}"
    h = cabecalhos(Perfil.DIRETOR)
    assert client.get(url, headers=h).status_code == 200
    assert client.get("/rotas", headers=h).status_code == 200
    assert client.post("/rotas", json={"nome": "R"}, headers=h).status_code == 403
    assert client.patch(url, json={"nome": "R"}, headers=h).status_code == 403
    assert client.put(f"{url}/paradas", json={"parada_ids": []}, headers=h).status_code == 403
    assert client.delete(url, headers=h).status_code == 403


def test_sequencia_define_ordem_trajeto_e_distancia(client, db, cabecalhos):
    h = cabecalhos(Perfil.COORDENADOR)
    a, b, c = _parada(db, 0.0, nome="A"), _parada(db, 1.0, nome="B"), _parada(db, 2.0, nome="C")
    rota = _rota(client, h)
    url = f"/rotas/{rota['id']}/paradas"

    resposta = client.put(url, json={"parada_ids": [b.id, a.id, c.id]}, headers=h)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [p["nome"] for p in corpo["paradas"]] == ["B", "A", "C"]
    assert corpo["trajeto"] == {
        "type": "LineString",
        "coordinates": [[0.0, 1.0], [0.0, 0.0], [0.0, 2.0]],
    }
    # B até A: um grau. A até C: dois graus, com leve variação do elipsoide.
    assert corpo["distancia_m"] == pytest.approx(3 * UM_GRAU_LATITUDE_M, abs=20)

    # A nova ordem reaproveita pares já gravados e não pode bater na restrição única.
    invertida = client.put(url, json={"parada_ids": [c.id, a.id]}, headers=h).json()
    assert [p["nome"] for p in invertida["paradas"]] == ["C", "A"]
    assert invertida["distancia_m"] == pytest.approx(2 * UM_GRAU_LATITUDE_M, abs=20)
    assert client.get(f"/rotas/{rota['id']}", headers=h).json() == invertida


@pytest.mark.parametrize("quantidade", [0, 1])
def test_menos_de_duas_paradas_zera_geometria(client, db, cabecalhos, quantidade):
    h = cabecalhos()
    a, b = _parada(db, 0.0), _parada(db, 1.0)
    rota = _rota(client, h)
    url = f"/rotas/{rota['id']}/paradas"
    assert client.put(url, json={"parada_ids": [a.id, b.id]}, headers=h).json()["trajeto"]

    corpo = client.put(url, json={"parada_ids": [a.id][:quantidade]}, headers=h).json()
    assert len(corpo["paradas"]) == quantidade
    assert corpo["trajeto"] is None
    assert corpo["distancia_m"] is None


def test_paradas_repetidas_e_inexistentes_rejeitadas(client, db, cabecalhos):
    h = cabecalhos()
    a = _parada(db, 0.0)
    b = _parada(db, 1.0)
    rota = _rota(client, h)
    url = f"/rotas/{rota['id']}/paradas"
    assert client.put(url, json={"parada_ids": [a.id, b.id]}, headers=h).status_code == 200

    assert client.put(url, json={"parada_ids": [a.id, a.id]}, headers=h).status_code == 422
    assert client.put(url, json={"parada_ids": [a.id, 999999]}, headers=h).status_code == 422
    # A rejeição não pode apagar a sequência já gravada.
    assert len(client.get(f"/rotas/{rota['id']}", headers=h).json()["paradas"]) == 2


def test_sequencia_de_rota_inexistente_da_404(client, cabecalhos):
    resposta = client.put("/rotas/999999/paradas", json={"parada_ids": []}, headers=cabecalhos())
    assert resposta.status_code == 404


def test_mover_parada_recalcula_rotas_que_a_usam(client, db, cabecalhos):
    h = cabecalhos()
    a, b, c = _parada(db, 0.0), _parada(db, 1.0), _parada(db, 5.0)
    com_b = _rota(client, h, "Com B")
    sem_b = _rota(client, h, "Sem B")
    url_com_b, url_sem_b = f"/rotas/{com_b['id']}", f"/rotas/{sem_b['id']}"
    client.put(f"{url_com_b}/paradas", json={"parada_ids": [a.id, b.id]}, headers=h)
    antes = client.put(f"{url_sem_b}/paradas", json={"parada_ids": [a.id, c.id]}, headers=h).json()

    resposta = client.patch(
        f"/paradas/{b.id}", json={"localizacao": {"latitude": 2.0, "longitude": 0.0}}, headers=h
    )
    assert resposta.status_code == 200

    corpo = client.get(url_com_b, headers=h).json()
    assert corpo["trajeto"]["coordinates"] == [[0.0, 0.0], [0.0, 2.0]]
    assert corpo["distancia_m"] == pytest.approx(2 * UM_GRAU_LATITUDE_M, abs=20)
    assert client.get(url_sem_b, headers=h).json() == antes


def test_renomear_parada_mantem_geometria_da_rota(client, db, cabecalhos):
    h = cabecalhos()
    a, b = _parada(db, 0.0), _parada(db, 1.0)
    rota = _rota(client, h)
    url = f"/rotas/{rota['id']}"
    antes = client.put(f"{url}/paradas", json={"parada_ids": [a.id, b.id]}, headers=h).json()
    client.patch(f"/paradas/{a.id}", json={"nome": "Novo"}, headers=h)
    depois = client.get(url, headers=h).json()
    assert depois["distancia_m"] == antes["distancia_m"]
    assert depois["paradas"][0]["nome"] == "Novo"


def test_remover_rota_libera_paradas(client, db, cabecalhos):
    h = cabecalhos()
    a, b = _parada(db, 0.0), _parada(db, 1.0)
    rota = _rota(client, h)
    client.put(f"/rotas/{rota['id']}/paradas", json={"parada_ids": [a.id, b.id]}, headers=h)
    assert client.delete(f"/paradas/{a.id}", headers=h).status_code == 409
    assert client.delete(f"/rotas/{rota['id']}", headers=h).status_code == 204
    assert client.delete(f"/paradas/{a.id}", headers=h).status_code == 204
