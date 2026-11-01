import pytest

from app.models import Perfil, Turma, Turno

DADOS = {
    "nome": "Escola Central",
    "codigo_inep": "41000001",
    "endereco": "Rua A, 10",
    "localizacao": {"latitude": -25.43, "longitude": -49.27},
}


def test_crud(client, cabecalhos):
    h = cabecalhos()
    criada = client.post("/escolas", json=DADOS, headers=h)
    assert criada.status_code == 201
    corpo = criada.json()
    assert corpo["localizacao"] == DADOS["localizacao"]

    url = f"/escolas/{corpo['id']}"
    assert client.get(url, headers=h).json() == corpo

    novo = {**DADOS, "nome": "Escola Nova", "localizacao": {"latitude": 1, "longitude": 2}}
    atualizada = client.put(url, json=novo, headers=h).json()
    assert atualizada["nome"] == "Escola Nova"
    assert atualizada["localizacao"] == {"latitude": 1.0, "longitude": 2.0}

    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404
    assert client.put(url, json=novo, headers=h).status_code == 404
    assert client.delete(url, headers=h).status_code == 404


def test_paginacao_e_filtro(client, cabecalhos, criar_escola):
    primeira, segunda = criar_escola("A"), criar_escola("B")
    h = cabecalhos()
    pagina = client.get("/escolas?limit=1&offset=1", headers=h).json()
    assert [e["id"] for e in pagina] == [segunda.id]
    assert primeira.id != segunda.id
    assert client.get("/escolas?limit=0", headers=h).status_code == 422
    assert client.get("/escolas?limit=201", headers=h).status_code == 422
    assert client.get("/escolas?offset=-1", headers=h).status_code == 422


@pytest.mark.parametrize(
    "alteracao",
    [
        {"nome": "   "},
        {"nome": "a\x00b"},
        {"codigo_inep": "123"},
        {"localizacao": {"latitude": 91, "longitude": 0}},
        {"localizacao": {"latitude": 0, "longitude": 181}},
        {"localizacao": None},
        {"polo_id": 0},
        {"polo_id": 2_147_483_648},
    ],
)
def test_validacao(client, cabecalhos, alteracao):
    h = cabecalhos()
    assert client.post("/escolas", json={**DADOS, **alteracao}, headers=h).status_code == 422


def test_id_gigante_nao_quebra(client, cabecalhos):
    assert client.get("/escolas/99999999999", headers=cabecalhos()).status_code == 422


def test_conflitos(client, db, cabecalhos, criar_escola):
    h = cabecalhos()
    db.commit()
    assert client.post("/escolas", json=DADOS, headers=h).status_code == 201
    assert client.post("/escolas", json=DADOS, headers=h).status_code == 409
    sem_polo = {**DADOS, "codigo_inep": None, "polo_id": 999999}
    assert client.post("/escolas", json=sem_polo, headers=h).status_code == 409

    escola = criar_escola("Com turma")
    db.add(Turma(escola_id=escola.id, nome="1A", serie="1", turno=Turno.MANHA, ano_letivo=2026))
    db.commit()
    assert client.delete(f"/escolas/{escola.id}", headers=h).status_code == 409


def test_perfis(client, cabecalhos, criar_escola):
    assert client.get("/escolas").status_code == 401
    escola = criar_escola()
    for perfil in (Perfil.DIRETOR, Perfil.COORDENADOR):
        h = cabecalhos(perfil)
        url = f"/escolas/{escola.id}"
        assert client.get(url, headers=h).status_code == 200
        assert client.post("/escolas", json=DADOS, headers=h).status_code == 403
        assert client.put(url, json=DADOS, headers=h).status_code == 403
        assert client.delete(url, headers=h).status_code == 403
