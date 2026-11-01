import pytest

from app.models import Perfil


def _dados(escola_id=None, **extra):
    return {"nome": "Paulo", "email": "Paulo@Exemplo.com", "escola_id": escola_id, **extra}


def test_crud_admin(client, cabecalhos, criar_escola):
    h = cabecalhos()
    escola = criar_escola()
    criado = client.post("/professores", json=_dados(escola.id), headers=h)
    assert criado.status_code == 201
    assert criado.json()["email"] == "paulo@exemplo.com"
    url = f"/professores/{criado.json()['id']}"
    assert client.get(url, headers=h).json()["nome"] == "Paulo"
    novo = client.put(url, json=_dados(None, nome="Paulo S."), headers=h).json()
    assert novo["nome"] == "Paulo S."
    assert novo["escola_id"] is None
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize("alteracao", [{"nome": ""}, {"email": "nao-e-email"}, {"escola_id": 0}])
def test_validacao(client, cabecalhos, alteracao):
    assert (
        client.post("/professores", json=_dados(**alteracao), headers=cabecalhos()).status_code
        == 422
    )


def test_conflitos(client, db, cabecalhos):
    h = cabecalhos()
    db.commit()
    assert client.post("/professores", json=_dados(), headers=h).status_code == 201
    outro_caso = _dados(email="PAULO@exemplo.com")
    assert client.post("/professores", json=outro_caso, headers=h).status_code == 409
    sem_escola = _dados(999999, email="b@exemplo.com")
    assert client.post("/professores", json=sem_escola, headers=h).status_code == 409


def test_diretor_so_atua_na_propria_escola(client, cabecalhos, criar_escola):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    admin = cabecalhos()
    h = cabecalhos(Perfil.DIRETOR, minha.id)
    alheio = client.post("/professores", json=_dados(outra.id), headers=admin).json()
    url_alheio = f"/professores/{alheio['id']}"

    novo = _dados(minha.id, email="x@exemplo.com")
    assert client.get(url_alheio, headers=h).status_code == 403
    assert client.put(url_alheio, json=novo, headers=h).status_code == 403
    assert client.delete(url_alheio, headers=h).status_code == 403
    assert client.get(f"/professores?escola_id={outra.id}", headers=h).status_code == 403

    # Professor sem escola e de outra escola não podem ser criados pelo diretor.
    for escola_id in (outra.id, None):
        dados = _dados(escola_id, email="y@exemplo.com")
        assert client.post("/professores", json=dados, headers=h).status_code == 403

    criado = client.post("/professores", json=novo, headers=h)
    assert criado.status_code == 201
    meu = criado.json()
    assert [p["id"] for p in client.get("/professores", headers=h).json()] == [meu["id"]]

    url = f"/professores/{meu['id']}"
    mover = _dados(outra.id, email="x@exemplo.com")
    assert client.put(url, json=mover, headers=h).status_code == 403
    assert client.get(url, headers=h).json()["escola_id"] == minha.id
    assert client.delete(url, headers=h).status_code == 204


def test_coordenador_nao_acessa(client, cabecalhos, criar_escola):
    admin = cabecalhos()
    professor = client.post("/professores", json=_dados(criar_escola().id), headers=admin).json()
    h = cabecalhos(Perfil.COORDENADOR)
    url = f"/professores/{professor['id']}"
    assert client.get("/professores", headers=h).status_code == 403
    assert client.get(url, headers=h).status_code == 403
    assert client.post("/professores", json=_dados(), headers=h).status_code == 403
    assert client.delete(url, headers=h).status_code == 403


def test_exige_token(client):
    assert client.get("/professores").status_code == 401
