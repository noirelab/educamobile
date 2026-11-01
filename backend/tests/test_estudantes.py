from datetime import date, timedelta

import pytest

from app.models import Estudante, Matricula, Perfil, StatusMatricula, Turma, Turno

DADOS = {
    "nome": "Maria",
    "data_nascimento": "2012-05-10",
    "nome_responsavel": "Joana",
    "localizacao": {"latitude": -25.4, "longitude": -49.2},
}


@pytest.fixture
def matricular(db):
    def criar(escola_id, status=StatusMatricula.ATIVA, nome="Aluno"):
        turma = Turma(escola_id=escola_id, nome=nome, serie="1", turno=Turno.MANHA, ano_letivo=2026)
        estudante = Estudante(nome=nome, data_nascimento=date(2012, 1, 1))
        db.add_all([turma, estudante])
        db.flush()
        db.add(
            Matricula(
                estudante_id=estudante.id,
                turma_id=turma.id,
                data_inicio=date(2026, 2, 1),
                status=status,
            )
        )
        db.flush()
        return estudante

    return criar


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


def test_conflitos(client, db, cabecalhos, criar_escola, matricular):
    h = cabecalhos()
    estudante = matricular(criar_escola().id)
    db.commit()
    assert client.delete(f"/estudantes/{estudante.id}", headers=h).status_code == 409
    com_parada = {**DADOS, "parada_id": 999999}
    assert client.post("/estudantes", json=com_parada, headers=h).status_code == 409


def test_diretor_escopo(client, cabecalhos, criar_escola, matricular):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    meu = matricular(minha.id, nome="Meu")
    alheio = matricular(outra.id, nome="Alheio")
    transferido = matricular(minha.id, StatusMatricula.TRANSFERIDA, nome="Saiu")
    h = cabecalhos(Perfil.DIRETOR, minha.id)

    assert [e["id"] for e in client.get("/estudantes", headers=h).json()] == [meu.id]
    assert client.get(f"/estudantes/{meu.id}", headers=h).status_code == 200
    assert client.put(f"/estudantes/{meu.id}", json=DADOS, headers=h).status_code == 200

    for estudante in (alheio, transferido):
        url = f"/estudantes/{estudante.id}"
        assert client.get(url, headers=h).status_code == 403
        assert client.put(url, json=DADOS, headers=h).status_code == 403
        assert client.delete(url, headers=h).status_code == 403

    # Mesma resposta para id inexistente, para não revelar quais estudantes existem.
    assert client.get("/estudantes/999999", headers=h).status_code == 403
    # Diretor só cadastra informando a matrícula; ver test_regressoes.py.
    assert client.post("/estudantes", json=DADOS, headers=h).status_code == 422


def test_coordenador_so_le(client, cabecalhos, criar_escola, matricular):
    estudante = matricular(criar_escola().id)
    h = cabecalhos(Perfil.COORDENADOR)
    url = f"/estudantes/{estudante.id}"
    assert client.get("/estudantes", headers=h).json()[0]["id"] == estudante.id
    assert client.get(url, headers=h).status_code == 200
    assert client.post("/estudantes", json=DADOS, headers=h).status_code == 403
    assert client.put(url, json=DADOS, headers=h).status_code == 403
    assert client.delete(url, headers=h).status_code == 403


def test_exige_token(client):
    assert client.get("/estudantes").status_code == 401
