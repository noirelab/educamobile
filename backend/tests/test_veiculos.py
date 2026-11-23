from datetime import date, timedelta

import pytest

from app.models import Perfil, Veiculo

HOJE = date.today()


def _corpo(**extra):
    return {
        "placa": "ABC1D23",
        "capacidade": 40,
        "modelo": "Ônibus escolar",
        "ano": 2020,
        "vistoria_valida_ate": (HOJE + timedelta(days=90)).isoformat(),
        **extra,
    }


@pytest.mark.parametrize(
    ("entrada", "salva"),
    [("abc1d23", "ABC1D23"), ("ABC-1234", "ABC1234"), (" abc 1d23 ", "ABC1D23")],
)
def test_placa_e_normalizada(client, cabecalhos, entrada, salva):
    resposta = client.post(
        "/veiculos", json=_corpo(placa=entrada), headers=cabecalhos(Perfil.GESTOR)
    )
    assert resposta.status_code == 201
    assert resposta.json()["placa"] == salva


@pytest.mark.parametrize(
    "placa", ["", "ABCD123", "AB12345", "ABC12", "123ABCD", "ABC1D234", "A\x00BC1D23"]
)
def test_placa_invalida(client, cabecalhos, placa):
    resposta = client.post("/veiculos", json=_corpo(placa=placa), headers=cabecalhos(Perfil.GESTOR))
    assert resposta.status_code == 422


@pytest.mark.parametrize(
    "alteracao",
    [{"capacidade": 0}, {"capacidade": 101}, {"ano": 1979}, {"ano": 2101}, {"modelo": ""}],
)
def test_validacao_dos_campos(client, cabecalhos, alteracao):
    resposta = client.post("/veiculos", json=_corpo(**alteracao), headers=cabecalhos())
    assert resposta.status_code == 422


def test_placa_repetida_da_409_mesmo_com_formatacao_diferente(client, db, cabecalhos):
    h = cabecalhos()
    db.commit()
    assert client.post("/veiculos", json=_corpo(placa="ABC1234"), headers=h).status_code == 201
    assert client.post("/veiculos", json=_corpo(placa="abc-1234"), headers=h).status_code == 409


def test_crud(client, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    criado = client.post("/veiculos", json=_corpo(), headers=h).json()
    url = f"/veiculos/{criado['id']}"
    assert client.get(url, headers=h).json() == criado
    novo = client.put(url, json=_corpo(capacidade=30, ativo=False), headers=h).json()
    assert novo["capacidade"] == 30
    assert novo["ativo"] is False
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


def test_gestor_ve_quais_estao_com_vistoria_vencida(client, db, cabecalhos):
    em_dia = Veiculo(
        placa="AAA1A11",
        capacidade=40,
        modelo="A",
        ano=2020,
        vistoria_valida_ate=HOJE + timedelta(days=1),
    )
    vence_hoje = Veiculo(
        placa="BBB2B22", capacidade=40, modelo="B", ano=2020, vistoria_valida_ate=HOJE
    )
    vencido = Veiculo(
        placa="CCC3C33",
        capacidade=40,
        modelo="C",
        ano=2020,
        vistoria_valida_ate=HOJE - timedelta(days=1),
    )
    db.add_all([em_dia, vence_hoje, vencido])
    db.flush()
    h = cabecalhos(Perfil.GESTOR)

    todos = client.get("/veiculos", headers=h).json()
    por_placa = {v["placa"]: v["vistoria_vencida"] for v in todos["itens"]}
    assert por_placa == {"AAA1A11": False, "BBB2B22": False, "CCC3C33": True}

    vencidos = client.get("/veiculos?vistoria_vencida=true", headers=h).json()
    assert [v["placa"] for v in vencidos["itens"]] == ["CCC3C33"]
    assert vencidos["total"] == 1
    validos = client.get("/veiculos?vistoria_vencida=false", headers=h).json()
    assert validos["total"] == 2


def test_busca_por_placa_ignora_caixa_e_hifen(client, db, cabecalhos):
    db.add_all(
        [
            Veiculo(placa="ABC1D23", capacidade=40, modelo="A", ano=2020, vistoria_valida_ate=HOJE),
            Veiculo(placa="XYZ9Z99", capacidade=40, modelo="B", ano=2020, vistoria_valida_ate=HOJE),
        ]
    )
    db.flush()
    h = cabecalhos()
    assert client.get("/veiculos?placa=abc-1", headers=h).json()["total"] == 1
    assert client.get("/veiculos?placa=Z9", headers=h).json()["total"] == 1
    assert client.get("/veiculos?placa=QQQ", headers=h).json()["total"] == 0


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_perfis_externos_nao_acessam(client, cabecalhos, perfil):
    h = cabecalhos(perfil)
    assert client.get("/veiculos", headers=h).status_code == 403
    assert client.post("/veiculos", json=_corpo(), headers=h).status_code == 403


def test_exige_token(client):
    assert client.get("/veiculos").status_code == 401
