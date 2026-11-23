from datetime import date, timedelta

import pytest

from app.models import Perfil
from tests.conftest import estudante_de_teste


@pytest.fixture
def dados(criar_escola):
    return {
        "nome": "Maria",
        "data_nascimento": "2012-05-10",
        "escola_id": criar_escola().id,
        "turno": "manha",
        "observacoes_cuidado": "Alergia a amendoim",
    }


def test_crud_admin(client, cabecalhos, dados):
    h = cabecalhos()
    criado = client.post("/estudantes", json=dados, headers=h)
    assert criado.status_code == 201
    corpo = criado.json()
    assert corpo["escola_id"] == dados["escola_id"]
    assert corpo["turno"] == "manha"
    assert corpo["tem_foto"] is False
    url = f"/estudantes/{corpo['id']}"
    assert client.get(url, headers=h).json() == corpo

    enxuto = {k: v for k, v in dados.items() if k != "observacoes_cuidado"}
    atualizado = client.put(url, json={**enxuto, "nome": "Maria S.", "turno": "tarde"}, headers=h)
    assert atualizado.json()["nome"] == "Maria S."
    assert atualizado.json()["turno"] == "tarde"
    assert atualizado.json()["observacoes_cuidado"] is None

    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


def test_nenhuma_resposta_traz_endereco_ou_localizacao_da_casa(client, cabecalhos, dados):
    h = cabecalhos()
    corpo = client.post("/estudantes", json=dados, headers=h).json()
    lista = client.get("/estudantes", headers=h).json()
    for campo in ("localizacao", "endereco", "nome_responsavel", "foto_arquivo"):
        assert campo not in corpo
        assert campo not in lista["itens"][0]


def test_campos_antigos_sao_ignorados_e_nao_gravados(client, cabecalhos, dados):
    h = cabecalhos()
    extras = {
        **dados,
        "localizacao": {"latitude": -25.4, "longitude": -49.2},
        "nome_responsavel": "J",
    }
    corpo = client.post("/estudantes", json=extras, headers=h).json()
    assert "localizacao" not in corpo
    assert "nome_responsavel" not in corpo


@pytest.mark.parametrize(
    "alteracao",
    [
        {"nome": ""},
        {"data_nascimento": "ontem"},
        {"data_nascimento": (date.today() + timedelta(days=1)).isoformat()},
        {"turno": "madrugada"},
        {"escola_id": 0},
        {"observacoes_cuidado": "x" * 1001},
        {"observacoes_cuidado": "a\x00b"},
    ],
)
def test_validacao(client, cabecalhos, dados, alteracao):
    resposta = client.post("/estudantes", json={**dados, **alteracao}, headers=cabecalhos())
    assert resposta.status_code == 422


def test_escola_e_turno_sao_obrigatorios(client, cabecalhos, dados):
    for campo in ("escola_id", "turno"):
        faltando = {k: v for k, v in dados.items() if k != campo}
        assert client.post("/estudantes", json=faltando, headers=cabecalhos()).status_code == 422


def test_escola_ou_parada_inexistente_da_409(client, db, cabecalhos, dados):
    h = cabecalhos()
    db.commit()
    assert (
        client.post("/estudantes", json={**dados, "parada_id": 999999}, headers=h).status_code
        == 409
    )
    assert (
        client.post("/estudantes", json={**dados, "escola_id": 999999}, headers=h).status_code
        == 409
    )


def test_listagem_com_busca_filtros_e_total(client, db, cabecalhos, criar_escola):
    a, b = criar_escola("A"), criar_escola("B")
    estudante_de_teste(db, "Ana Souza", escola_id=a.id)
    estudante_de_teste(db, "Ana Lima", escola_id=b.id, turno="tarde")
    estudante_de_teste(db, "Bruno Souza", escola_id=a.id, turno="tarde")
    h = cabecalhos()

    assert client.get("/estudantes", headers=h).json()["total"] == 3
    ana = client.get("/estudantes?q=ana", headers=h).json()
    assert [e["nome"] for e in ana["itens"]] == ["Ana Lima", "Ana Souza"]
    assert client.get(f"/estudantes?escola_id={a.id}", headers=h).json()["total"] == 2
    assert client.get("/estudantes?turno=tarde", headers=h).json()["total"] == 2
    pagina = client.get("/estudantes?limit=1&offset=1", headers=h).json()
    assert pagina["total"] == 3
    assert [e["nome"] for e in pagina["itens"]] == ["Ana Souza"]
    assert client.get("/estudantes?q=%25", headers=h).json()["total"] == 0


def test_gestor_edita_mas_so_admin_remove(client, cabecalhos, dados):
    h = cabecalhos(Perfil.GESTOR)
    criado = client.post("/estudantes", json=dados, headers=h)
    assert criado.status_code == 201
    url = f"/estudantes/{criado.json()['id']}"
    assert client.put(url, json=dados, headers=h).status_code == 200
    assert client.delete(url, headers=h).status_code == 403


def test_escola_com_estudante_nao_e_removida(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    estudante_de_teste(db, escola_id=escola.id)
    db.commit()
    assert client.delete(f"/escolas/{escola.id}", headers=cabecalhos()).status_code == 409


def test_exige_token(client):
    assert client.get("/estudantes").status_code == 401
