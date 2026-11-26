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


def _corpo(filho, **extra):
    return {
        "nome": filho.nome,
        "data_nascimento": filho.data_nascimento.isoformat(),
        "escola_id": filho.escola_id,
        "turno": filho.turno.value,
        **extra,
    }


def _gestao_grava(client, h, filho, nome="Tia Rosa", telefone="(41) 99999-1234", parentesco="tia"):
    corpo = _corpo(
        filho,
        contato_emergencia_nome=nome,
        contato_emergencia_telefone=telefone,
        contato_emergencia_parentesco=parentesco,
    )
    return client.put(f"/estudantes/{filho.id}", json=corpo, headers=h)


def test_responsavel_so_le_o_contato_que_a_gestao_gravou(client, db, cabecalhos, familia):
    mae, filho = familia
    assert (
        client.get(f"/responsavel/filhos/{filho.id}", headers=_h(mae)).json()["contato_emergencia"]
        is None
    )
    assert _gestao_grava(client, cabecalhos(Perfil.GESTOR), filho).status_code == 200
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


def test_responsavel_nao_troca_o_contato(client, familia, criar_usuario):
    """A troca é pedida à gestão: nenhum responsável grava direto, nem o que tem vínculo."""
    mae, filho = familia
    url = f"/responsavel/filhos/{filho.id}/contato-emergencia"
    for metodo in ("PUT", "POST", "PATCH", "DELETE"):
        assert client.request(metodo, url, json=CONTATO, headers=_h(mae)).status_code in (404, 405)
    assert (
        client.put(f"/estudantes/{filho.id}", json=_corpo(filho), headers=_h(mae)).status_code
        == 403
    )


def test_equipe_da_viagem_nao_le_nem_grava(client, familia, criar_usuario):
    _, filho = familia
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR):
        h = _h(criar_usuario(perfil))
        assert client.get(f"/estudantes/{filho.id}", headers=h).status_code == 403
        assert _gestao_grava(client, h, filho).status_code == 403


@pytest.mark.parametrize(
    "contato",
    [
        {"contato_emergencia_nome": "Rosa", "contato_emergencia_telefone": "123"},
        {"contato_emergencia_nome": "Rosa", "contato_emergencia_telefone": "41 9999-ABCD"},
        {"contato_emergencia_nome": "Rosa", "contato_emergencia_telefone": "+55419999912345678"},
        {"contato_emergencia_nome": "", "contato_emergencia_telefone": "41999991234"},
        {"contato_emergencia_telefone": "41999991234"},
        {"contato_emergencia_parentesco": "tia"},
    ],
)
def test_contato_invalido_e_recusado(client, cabecalhos, familia, contato):
    _, filho = familia
    r = client.put(
        f"/estudantes/{filho.id}", json=_corpo(filho, **contato), headers=cabecalhos(Perfil.GESTOR)
    )
    assert r.status_code == 422


def test_gestao_remove_o_contato_mandando_vazio(client, cabecalhos, familia):
    _, filho = familia
    h = cabecalhos(Perfil.GESTOR)
    _gestao_grava(client, h, filho)
    vazio = _corpo(
        filho,
        contato_emergencia_nome=None,
        contato_emergencia_telefone=None,
        contato_emergencia_parentesco=None,
    )
    r = client.put(f"/estudantes/{filho.id}", json=vazio, headers=h)
    assert r.status_code == 200
    assert r.json()["contato_emergencia_nome"] is None


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
    _, filho = familia
    _gestao_grava(client, cabecalhos(Perfil.GESTOR), filho)
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
