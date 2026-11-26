"""Novo na reformulação: a escola confirma o recebimento das crianças da ida."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import alertas
from app.config import settings
from app.models import (
    Alerta,
    Escola,
    Notificacao,
    Perfil,
    ResponsavelEstudante,
    Sentido,
    Usuario,
    Viagem,
)
from app.security import criar_token
from tests.conftest import escola_de_teste
from tests.test_alertas import _iniciar, mundo  # noqa: F401  (fixture reaproveitada)


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _criar_equipe(client, db, gestor, escola_id):
    corpo = {
        "nome": "Secretaria",
        "email": f"{uuid.uuid4().hex[:10]}@escola.exemplo.com",
        "senha": "senha-forte-1",
        "perfil": "escola",
        "escola_id": escola_id,
    }
    r = client.post("/usuarios", json=corpo, headers=gestor)
    assert r.status_code == 201, r.text
    assert r.json()["escola_id"] == escola_id
    return db.get(Usuario, r.json()["id"])


def _evento(client, m, tipo):
    corpo = {
        "eventos": [
            {
                "id": str(uuid.uuid4()),
                "tipo": tipo,
                "estudante_id": m["ana"].id,
                "hora_aparelho": datetime.now(UTC).isoformat(),
            }
        ]
    }
    r = client.post(f"/viagens/{m['viagem']['id']}/eventos", json=corpo, headers=m["hm"])
    assert r.is_success, r.text


@pytest.fixture
def escola(client, db, mundo):  # noqa: F811
    _iniciar(client, mundo)
    equipe = _criar_equipe(client, db, mundo["gestor"], mundo["escola"].id)
    return {**mundo, "equipe": equipe, "he": _h(equipe)}


def _vincular_mae(db, criar_usuario, m):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    db.add(
        ResponsavelEstudante(
            responsavel_id=mae.id,
            estudante_id=m["ana"].id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC),
            consentimento_versao=settings.versao_termo_consentimento,
        )
    )
    db.flush()
    return mae


def test_escola_acompanha_e_confirma_e_a_familia_e_avisada(client, db, escola, criar_usuario):
    m = escola
    mae = _vincular_mae(db, criar_usuario, m)
    assert client.get("/escola/chegadas", headers=m["he"]).json()[0]["alunos"] == []

    _evento(client, m, "embarque")
    aluno = client.get("/escola/chegadas", headers=m["he"]).json()[0]["alunos"][0]
    assert aluno["situacao"] == "a_caminho"
    assert set(aluno) == {"estudante_id", "nome", "situacao", "desembarcou_em", "recebido_em"}

    _evento(client, m, "desembarque")
    aluno = client.get("/escola/chegadas", headers=m["he"]).json()[0]["alunos"][0]
    assert aluno["situacao"] == "aguardando" and aluno["desembarcou_em"]

    url = f"/viagens/{m['viagem']['id']}/recebimentos"
    r = client.post(url, json={"estudante_ids": [m["ana"].id]}, headers=m["he"])
    assert r.json() == {"recebidos": 1, "ja_recebidos": 0}
    # Repetir não muda nada nem avisa de novo.
    r = client.post(url, json={"estudante_ids": [m["ana"].id]}, headers=m["he"])
    assert r.json() == {"recebidos": 0, "ja_recebidos": 1}
    aluno = client.get("/escola/chegadas", headers=m["he"]).json()[0]["alunos"][0]
    assert aluno["situacao"] == "recebido"
    avisos = db.scalars(
        select(Notificacao).where(
            Notificacao.usuario_id == mae.id, Notificacao.tipo == "recebido_escola"
        )
    ).all()
    assert len(avisos) == 1 and "Ana" in avisos[0].mensagem


def test_so_confirma_quem_o_motorista_desembarcou(client, escola):
    m = escola
    url = f"/viagens/{m['viagem']['id']}/recebimentos"
    _evento(client, m, "embarque")
    r = client.post(url, json={"estudante_ids": [m["ana"].id]}, headers=m["he"])
    assert r.status_code == 409
    r = client.post(url, json={"estudante_ids": [999_999]}, headers=m["he"])
    assert r.status_code == 422


def test_outra_escola_outro_dia_ou_volta_somem(client, db, escola):
    m = escola
    _evento(client, m, "embarque")
    _evento(client, m, "desembarque")
    url = f"/viagens/{m['viagem']['id']}/recebimentos"
    corpo = {"estudante_ids": [m["ana"].id]}

    outra = escola_de_teste(db, "Outra")
    equipe_outra = _criar_equipe(client, db, m["gestor"], outra.id)
    assert client.post(url, json=corpo, headers=_h(equipe_outra)).status_code == 404
    assert client.get("/escola/chegadas", headers=_h(equipe_outra)).json() == []

    viagem = db.get(Viagem, m["viagem"]["id"])
    viagem.sentido = Sentido.VOLTA
    db.flush()
    assert client.post(url, json=corpo, headers=m["he"]).status_code == 404
    viagem.sentido = Sentido.IDA
    viagem.data = viagem.data - timedelta(days=1)
    db.flush()
    assert client.post(url, json=corpo, headers=m["he"]).status_code == 404


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.GESTOR, Perfil.RESPONSAVEL])
def test_so_a_equipe_da_escola_confirma(client, escola, cabecalhos, perfil):
    m = escola
    url = f"/viagens/{m['viagem']['id']}/recebimentos"
    r = client.post(url, json={"estudante_ids": [m["ana"].id]}, headers=cabecalhos(perfil))
    assert r.status_code == 403
    assert client.get("/escola/chegadas", headers=cabecalhos(perfil)).status_code == 403


def test_sem_confirmacao_no_prazo_vira_alerta_critico_e_resolve_ao_confirmar(client, db, escola):
    m = escola
    _evento(client, m, "embarque")
    _evento(client, m, "desembarque")
    lim = alertas.limites(db)
    # Dentro do prazo, nada.
    assert alertas.nao_recebido_pela_escola(db, datetime.now(UTC), lim) == []

    depois = datetime.now(UTC) + timedelta(minutes=lim["recebimento_escola_min"] + 1)
    [alerta] = alertas.nao_recebido_pela_escola(db, depois, lim)
    assert alerta.tipo == "crianca_nao_recebida_pela_escola"
    assert alerta.severidade.value == "critico"
    assert alerta.dados["estudante_ids"] == [m["ana"].id]
    aviso_escola = db.scalar(
        select(Notificacao).where(
            Notificacao.usuario_id == m["equipe"].id,
            Notificacao.tipo == "confirmar_recebimento",
        )
    )
    assert aviso_escola is not None
    # Não repete o alerta.
    assert alertas.nao_recebido_pela_escola(db, depois, lim) == []

    url = f"/viagens/{m['viagem']['id']}/recebimentos"
    client.post(url, json={"estudante_ids": [m["ana"].id]}, headers=m["he"])
    db.expire_all()
    assert db.get(Alerta, alerta.id).resolvido_em is not None


def test_escola_que_nao_confirma_nao_gera_alerta(client, db, escola):
    m = escola
    db.get(Escola, m["escola"].id).confirma_recebimento = False
    db.flush()
    _evento(client, m, "embarque")
    _evento(client, m, "desembarque")
    lim = alertas.limites(db)
    depois = datetime.now(UTC) + timedelta(hours=1)
    assert alertas.nao_recebido_pela_escola(db, depois, lim) == []


def test_perfil_escola_exige_a_escola_e_so_ele(client, db, cabecalhos, criar_escola):
    gestor = cabecalhos(Perfil.GESTOR)
    base = {"nome": "X", "senha": "senha-forte-1"}
    sem = {**base, "email": "a@exemplo.com", "perfil": "escola"}
    assert client.post("/usuarios", json=sem, headers=gestor).status_code == 422
    motorista = {
        **base,
        "email": "b@exemplo.com",
        "perfil": "motorista",
        "escola_id": criar_escola().id,
    }
    assert client.post("/usuarios", json=motorista, headers=gestor).status_code == 422
    inexistente = {**base, "email": "c@exemplo.com", "perfil": "escola", "escola_id": 999_999}
    assert client.post("/usuarios", json=inexistente, headers=gestor).status_code == 422
