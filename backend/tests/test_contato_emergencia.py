"""Contato de emergência opcional do estudante: quem grava, quem lê e o que não se perde."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import Auditoria, Estudante, Perfil, ResponsavelEstudante
from app.security import criar_token
from tests.conftest import estudante_de_teste

CONTATO = {"nome": "Tia Rosa", "telefone": "(41) 99999-1234", "parentesco": "tia"}


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


@pytest.fixture
def familia(db, criar_usuario):
    filho = estudante_de_teste(db, "Bia")
    mae = criar_usuario(Perfil.RESPONSAVEL)
    db.add(
        ResponsavelEstudante(
            responsavel_id=mae.id,
            estudante_id=filho.id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC),
            consentimento_versao=settings.versao_termo_consentimento,
        )
    )
    db.flush()
    return mae, filho


def test_responsavel_cadastra_ve_e_remove_o_contato(client, db, familia):
    mae, filho = familia
    url = f"/responsavel/filhos/{filho.id}/contato-emergencia"
    r = client.put(url, json=CONTATO, headers=_h(mae))
    assert r.status_code == 200, r.text
    assert r.json()["telefone"] == "41999991234"

    detalhe = client.get(f"/responsavel/filhos/{filho.id}", headers=_h(mae)).json()
    assert detalhe["contato_emergencia"] == {
        "nome": "Tia Rosa",
        "telefone": "41999991234",
        "parentesco": "tia",
    }
    registro = db.scalar(select(Auditoria).where(Auditoria.acao == "estudante.contato_emergencia"))
    assert registro is not None
    # O telefone não vai para a auditoria.
    assert "41999991234" not in str(registro.detalhes)

    assert client.delete(url, headers=_h(mae)).status_code == 204
    detalhe = client.get(f"/responsavel/filhos/{filho.id}", headers=_h(mae)).json()
    assert detalhe["contato_emergencia"] is None


def test_sem_vinculo_ou_sem_consentimento_nao_mexe(client, db, familia, criar_usuario):
    mae, filho = familia
    estranho = criar_usuario(Perfil.RESPONSAVEL)
    url = f"/responsavel/filhos/{filho.id}/contato-emergencia"
    assert client.put(url, json=CONTATO, headers=_h(estranho)).status_code == 404
    assert client.delete(url, headers=_h(estranho)).status_code == 404

    vinculo = db.get(ResponsavelEstudante, (mae.id, filho.id))
    vinculo.consentimento_em = None
    db.flush()
    assert client.put(url, json=CONTATO, headers=_h(mae)).status_code == 403
    # Equipe da viagem e outros perfis não usam a rota do responsável.
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR, Perfil.GESTOR):
        assert client.put(url, json=CONTATO, headers=_h(criar_usuario(perfil))).status_code == 403


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": "Rosa", "telefone": "123"},
        {"nome": "Rosa", "telefone": "41 9999-ABCD"},
        {"nome": "Rosa", "telefone": "+55419999912345678"},
        {"nome": "", "telefone": "41999991234"},
        {"telefone": "41999991234"},
        {**CONTATO, "extra": "x"},
    ],
)
def test_contato_invalido_e_recusado(client, familia, corpo):
    mae, filho = familia
    url = f"/responsavel/filhos/{filho.id}/contato-emergencia"
    assert client.put(url, json=corpo, headers=_h(mae)).status_code == 422


def test_gestao_le_e_grava_pelo_cadastro(client, db, cabecalhos, familia):
    _, filho = familia
    h = cabecalhos(Perfil.GESTOR)
    base = {
        "nome": filho.nome,
        "data_nascimento": filho.data_nascimento.isoformat(),
        "escola_id": filho.escola_id,
        "turno": filho.turno.value,
    }
    r = client.put(
        f"/estudantes/{filho.id}",
        json={
            **base,
            "contato_emergencia_nome": "Avó Lúcia",
            "contato_emergencia_telefone": "+55 41 3333-4444",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["contato_emergencia_telefone"] == "+554133334444"
    assert client.get(f"/estudantes/{filho.id}", headers=h).json()["contato_emergencia_nome"] == (
        "Avó Lúcia"
    )


def test_formulario_sem_os_campos_nao_apaga_o_contato_do_responsavel(
    client, db, cabecalhos, familia
):
    mae, filho = familia
    client.put(f"/responsavel/filhos/{filho.id}/contato-emergencia", json=CONTATO, headers=_h(mae))
    corpo = {
        "nome": "Bia S.",
        "data_nascimento": filho.data_nascimento.isoformat(),
        "escola_id": filho.escola_id,
        "turno": filho.turno.value,
    }
    r = client.put(f"/estudantes/{filho.id}", json=corpo, headers=cabecalhos(Perfil.GESTOR))
    assert r.status_code == 200
    assert r.json()["contato_emergencia_nome"] == "Tia Rosa"


def test_gestao_precisa_de_nome_e_telefone_juntos(client, cabecalhos, familia):
    _, filho = familia
    corpo = {
        "nome": filho.nome,
        "data_nascimento": filho.data_nascimento.isoformat(),
        "escola_id": filho.escola_id,
        "turno": filho.turno.value,
        "contato_emergencia_nome": "Avó Lúcia",
    }
    r = client.put(f"/estudantes/{filho.id}", json=corpo, headers=cabecalhos(Perfil.GESTOR))
    assert r.status_code == 422


def test_o_banco_recusa_contato_pela_metade(db, familia):
    _, filho = familia
    with pytest.raises(IntegrityError), db.begin_nested():
        db.get(Estudante, filho.id).contato_emergencia_telefone = "41999991234"
        db.flush()
