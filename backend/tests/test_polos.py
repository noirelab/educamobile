import pytest

from app.models import Perfil

AREA = {
    "type": "MultiPolygon",
    "coordinates": [[[[-49.3, -25.5], [-49.2, -25.5], [-49.2, -25.4], [-49.3, -25.5]]]],
}


def test_crud_com_area(client, cabecalhos):
    h = cabecalhos()
    criado = client.post("/polos", json={"nome": "Polo Norte", "area": AREA}, headers=h)
    assert criado.status_code == 201
    corpo = criado.json()
    assert corpo["area"]["type"] == "MultiPolygon"
    assert corpo["area"]["coordinates"][0][0][0] == [-49.3, -25.5]

    url = f"/polos/{corpo['id']}"
    assert client.get(url, headers=h).json()["nome"] == "Polo Norte"
    assert client.get("/polos", headers=h).json()[0]["id"] == corpo["id"]

    atualizado = client.put(url, json={"nome": "Polo Sul"}, headers=h)
    assert atualizado.json() == {"id": corpo["id"], "nome": "Polo Sul", "area": None}

    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize(
    "area",
    [
        {"type": "Polygon", "coordinates": AREA["coordinates"][0]},
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": [[]]},
        # anel aberto
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1]]]]},
        # poucos pontos
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [0, 0]]]]},
        # fora do intervalo
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [200, 0], [1, 1], [0, 0]]]]},
        # autointerseção
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]]},
    ],
)
def test_area_invalida(client, cabecalhos, area):
    resposta = client.post("/polos", json={"nome": "P", "area": area}, headers=cabecalhos())
    assert resposta.status_code == 422


def test_nome_duplicado(client, db, cabecalhos):
    h = cabecalhos()
    assert client.post("/polos", json={"nome": "A"}, headers=h).status_code == 201
    assert client.post("/polos", json={"nome": "A"}, headers=h).status_code == 409


def test_autenticacao_e_perfis(client, cabecalhos):
    assert client.get("/polos").status_code == 401
    for perfil in (Perfil.DIRETOR, Perfil.COORDENADOR):
        h = cabecalhos(perfil)
        assert client.get("/polos", headers=h).status_code == 200
        assert client.post("/polos", json={"nome": "X"}, headers=h).status_code == 403
