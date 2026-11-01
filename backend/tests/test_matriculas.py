from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Estudante, Matricula, Perfil, StatusMatricula, Turma, Turno


@pytest.fixture
def cenario(db, criar_escola):
    """Duas escolas, com turmas de 2025, um estudante e os dados confirmados.

    Sem o commit, o rollback do 409 também desfaria o que foi criado no teste.
    """
    a, b = criar_escola("Escola A"), criar_escola("Escola B")
    turmas = [
        Turma(escola_id=a.id, nome="A1", serie="1", turno=Turno.MANHA, ano_letivo=2025),
        Turma(escola_id=a.id, nome="A2", serie="2", turno=Turno.TARDE, ano_letivo=2025),
        Turma(escola_id=b.id, nome="B1", serie="1", turno=Turno.MANHA, ano_letivo=2025),
    ]
    estudante = Estudante(nome="Bia", data_nascimento=date(2015, 5, 1))
    db.add_all([*turmas, estudante])
    db.commit()
    return {
        "a": a,
        "b": b,
        "a1": turmas[0],
        "a2": turmas[1],
        "b1": turmas[2],
        "estudante": estudante,
    }


@pytest.fixture
def auth(db, cabecalhos):
    def criar(perfil=Perfil.ADMIN, escola_id=None):
        h = cabecalhos(perfil, escola_id)
        db.commit()
        return h

    return criar


def _matricular(client, h, c, turma="a1", inicio="2025-02-01"):
    return client.post(
        "/matriculas",
        json={
            "estudante_id": c["estudante"].id,
            "turma_id": c[turma].id,
            "data_inicio": inicio,
        },
        headers=h,
    )


def _transferir(client, h, c, destino="b1", data="2025-06-01"):
    return client.post(
        "/matriculas/transferencias",
        json={
            "estudante_id": c["estudante"].id,
            "turma_destino_id": c[destino].id,
            "data": data,
        },
        headers=h,
    )


def test_criar_consultar_e_filtrar(client, cenario, auth):
    h = auth()
    criada = _matricular(client, h, cenario)
    assert criada.status_code == 201
    assert criada.json()["status"] == "ativa"
    mid = criada.json()["id"]
    assert client.get(f"/matriculas/{mid}", headers=h).json()["id"] == mid

    filtros = {
        "estudante_id": (cenario["estudante"].id, 1),
        "turma_id": (cenario["a2"].id, 0),
        "status": ("encerrada", 0),
    }
    for chave, (valor, esperado) in filtros.items():
        resposta = client.get("/matriculas", params={chave: valor}, headers=h)
        assert resposta.status_code == 200
        assert len(resposta.json()) == esperado, chave


def test_segunda_matricula_ativa_conflita(client, cenario, auth):
    h = auth()
    assert _matricular(client, h, cenario).status_code == 201
    assert _matricular(client, h, cenario, "a2").status_code == 409


@pytest.mark.parametrize(
    ("corpo", "esperado"),
    [
        ({"estudante_id": 999999}, 404),
        ({"turma_id": 999999}, 404),
        ({"data_inicio": "2024-12-31"}, 422),
        ({"data_inicio": "nao-e-data"}, 422),
    ],
)
def test_criar_invalida(client, cenario, auth, corpo, esperado):
    base = {
        "estudante_id": cenario["estudante"].id,
        "turma_id": cenario["a1"].id,
        "data_inicio": "2025-02-01",
    }
    resposta = client.post("/matriculas", json=base | corpo, headers=auth())
    assert resposta.status_code == esperado


def test_exige_login_e_bloqueia_coordenador(client, cenario, auth):
    assert client.get("/matriculas").status_code == 401
    h = auth(Perfil.COORDENADOR)
    assert client.get("/matriculas", headers=h).status_code == 403
    assert _matricular(client, h, cenario).status_code == 403
    assert _transferir(client, h, cenario).status_code == 403


def test_diretor_so_na_propria_escola(client, cenario, auth):
    h_a = auth(Perfil.DIRETOR, cenario["a"].id)
    h_b = auth(Perfil.DIRETOR, cenario["b"].id)

    assert _matricular(client, h_b, cenario, "a1").status_code == 403
    mid = _matricular(client, auth(), cenario, "a1").json()["id"]

    assert client.get(f"/matriculas/{mid}", headers=h_b).status_code == 403
    assert client.get("/matriculas", headers=h_b).json() == []
    assert len(client.get("/matriculas", headers=h_a).json()) == 1
    encerrar = client.post(
        f"/matriculas/{mid}/encerrar", json={"data_fim": "2025-03-01"}, headers=h_b
    )
    assert encerrar.status_code == 403


def test_transferencia_encerra_atual_e_cria_nova(client, cenario, auth):
    h = auth()
    origem = _matricular(client, h, cenario).json()
    nova = _transferir(client, h, cenario, "b1", "2025-06-01")
    assert nova.status_code == 201

    historico = client.get(f"/matriculas/historico/{cenario['estudante'].id}", headers=h).json()
    assert [(m["id"], m["status"], m["data_inicio"], m["data_fim"]) for m in historico] == [
        (origem["id"], "transferida", "2025-02-01", "2025-06-01"),
        (nova.json()["id"], "ativa", "2025-06-01", None),
    ]


def test_transferencia_e_atomica(client, db, cenario, auth, monkeypatch):
    h = auth()
    origem_id = _matricular(client, h, cenario).json()["id"]

    def falhar():
        raise IntegrityError("simulada", None, Exception())

    monkeypatch.setattr(db, "commit", falhar)
    assert _transferir(client, h, cenario).status_code == 409
    monkeypatch.undo()

    linhas = db.scalars(
        select(Matricula).where(Matricula.estudante_id == cenario["estudante"].id),
        execution_options={"populate_existing": True},
    ).all()
    assert [(m.id, m.status, m.data_fim) for m in linhas] == [
        (origem_id, StatusMatricula.ATIVA, None)
    ]


def test_transferencia_diretor_depende_da_origem(client, cenario, auth):
    admin = auth()
    _matricular(client, admin, cenario, "a1")
    assert _transferir(client, auth(Perfil.DIRETOR, cenario["b"].id), cenario).status_code == 403
    # Entre escolas, só o administrador; ver test_regressoes.py.
    assert _transferir(client, auth(Perfil.DIRETOR, cenario["a"].id), cenario).status_code == 403


def test_transferencia_rejeitada(client, cenario, auth):
    h = auth()
    assert _transferir(client, h, cenario).status_code == 422  # sem matrícula ativa
    _matricular(client, h, cenario, "a1")
    assert _transferir(client, h, cenario, "a1").status_code == 422  # mesma turma
    assert _transferir(client, h, cenario, data="2025-01-15").status_code == 422  # antes do início
    assert _transferir(client, h, cenario, data="2026-02-01").status_code == 422  # outro ano letivo
    futura = (date.today() + timedelta(days=1)).isoformat()
    assert _transferir(client, h, cenario, data=futura).status_code == 422
    assert (
        client.post(
            "/matriculas/transferencias",
            json={
                "estudante_id": cenario["estudante"].id,
                "turma_destino_id": 999999,
                "data": "2025-06-01",
            },
            headers=h,
        ).status_code
        == 404
    )


def test_encerrar(client, cenario, auth):
    h = auth()
    mid = _matricular(client, h, cenario).json()["id"]
    url = f"/matriculas/{mid}/encerrar"
    assert client.post(url, json={"data_fim": "2025-01-01"}, headers=h).status_code == 422
    resposta = client.post(url, json={"data_fim": "2025-06-30"}, headers=h)
    assert resposta.status_code == 200
    assert (resposta.json()["status"], resposta.json()["data_fim"]) == ("encerrada", "2025-06-30")
    assert client.post(url, json={"data_fim": "2025-07-01"}, headers=h).status_code == 409
    assert client.get("/matriculas/999999", headers=h).status_code == 404
    assert client.get("/matriculas/historico/999999", headers=h).status_code == 404
