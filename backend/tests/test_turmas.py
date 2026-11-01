from datetime import date

import pytest

from app.models import Estudante, Matricula, Perfil


def _dados(escola_id, **extra):
    return {
        "escola_id": escola_id,
        "nome": "6A",
        "serie": "6o ano",
        "turno": "manha",
        "ano_letivo": 2026,
        **extra,
    }


def test_crud_admin(client, cabecalhos, criar_escola):
    h = cabecalhos()
    escola = criar_escola()
    criada = client.post("/turmas", json=_dados(escola.id), headers=h)
    assert criada.status_code == 201
    url = f"/turmas/{criada.json()['id']}"
    assert client.get(url, headers=h).json()["nome"] == "6A"
    assert client.put(url, json=_dados(escola.id, nome="6B"), headers=h).json()["nome"] == "6B"
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize(
    "extra", [{"turno": "madrugada"}, {"ano_letivo": 1500}, {"nome": ""}, {"escola_id": None}]
)
def test_validacao(client, cabecalhos, criar_escola, extra):
    dados = {**_dados(criar_escola().id), **extra}
    assert client.post("/turmas", json=dados, headers=cabecalhos()).status_code == 422


def test_conflitos(client, db, cabecalhos, criar_escola):
    h = cabecalhos()
    escola = criar_escola()
    db.commit()
    assert client.post("/turmas", json=_dados(escola.id), headers=h).status_code == 201
    assert client.post("/turmas", json=_dados(escola.id), headers=h).status_code == 409
    assert client.post("/turmas", json=_dados(999999), headers=h).status_code == 409


def test_remover_com_matricula_conflita(client, db, cabecalhos, criar_escola):
    h = cabecalhos()
    turma = client.post("/turmas", json=_dados(criar_escola().id), headers=h).json()
    estudante = Estudante(nome="E", data_nascimento=date(2012, 1, 1))
    db.add(estudante)
    db.flush()
    db.add(Matricula(estudante_id=estudante.id, turma_id=turma["id"], data_inicio=date(2026, 2, 1)))
    db.commit()
    assert client.delete(f"/turmas/{turma['id']}", headers=h).status_code == 409


def test_diretor_so_atua_na_propria_escola(client, cabecalhos, criar_escola):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    admin = cabecalhos()
    h = cabecalhos(Perfil.DIRETOR, minha.id)

    da_outra = client.post("/turmas", json=_dados(outra.id), headers=admin).json()
    assert client.post("/turmas", json=_dados(outra.id, nome="X"), headers=h).status_code == 403
    assert client.get(f"/turmas/{da_outra['id']}", headers=h).status_code == 403
    alterada = _dados(minha.id, nome="X")
    assert client.put(f"/turmas/{da_outra['id']}", json=alterada, headers=h).status_code == 403
    assert client.delete(f"/turmas/{da_outra['id']}", headers=h).status_code == 403
    assert client.get(f"/turmas?escola_id={outra.id}", headers=h).status_code == 403

    criada = client.post("/turmas", json=_dados(minha.id), headers=h)
    assert criada.status_code == 201
    turma = criada.json()
    assert [t["id"] for t in client.get("/turmas", headers=h).json()] == [turma["id"]]

    # Não pode mover a própria turma para outra escola.
    url = f"/turmas/{turma['id']}"
    assert client.put(url, json=_dados(outra.id), headers=h).status_code == 403
    assert client.get(url, headers=h).json()["escola_id"] == minha.id
    assert client.delete(url, headers=h).status_code == 204


def test_coordenador_so_le(client, cabecalhos, criar_escola):
    escola = criar_escola()
    admin = cabecalhos()
    turma = client.post("/turmas", json=_dados(escola.id), headers=admin).json()
    h = cabecalhos(Perfil.COORDENADOR)
    assert client.get("/turmas", headers=h).status_code == 200
    assert client.get(f"/turmas/{turma['id']}", headers=h).status_code == 200
    assert client.post("/turmas", json=_dados(escola.id, nome="X"), headers=h).status_code == 403
    assert client.delete(f"/turmas/{turma['id']}", headers=h).status_code == 403


def test_exige_token(client):
    assert client.get("/turmas").status_code == 401
    assert client.post("/turmas", json={}).status_code == 401
