"""Inscrição do estudante na rota e aviso de ausência do responsável."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.config import settings
from app.models import Auditoria, Perfil, ResponsavelEstudante, Veiculo
from app.security import criar_token
from tests.conftest import corpo_de_rota, escola_de_teste, estudante_de_teste
from tests.test_rotas import _parada

HOJE = date.today()


@pytest.fixture
def cenario(client, db, cabecalhos):
    """Uma rota de ida da manhã com duas paradas, e a escola dela."""
    gestor = cabecalhos(Perfil.GESTOR)
    escola = escola_de_teste(db, "Escola", 0.0, 0.0, raio_cerca_m=150)
    casa, na_escola = _parada(db, 0.01, nome="Casa"), _parada(db, 0.0001, nome="Escola")
    corpo = corpo_de_rota(db, "Linha 1", escola_id=escola.id, turno="manha", sentido="ida")
    rota = client.post("/rotas", json=corpo, headers=gestor).json()
    client.put(
        f"/rotas/{rota['id']}/paradas", json={"parada_ids": [casa.id, na_escola.id]}, headers=gestor
    )
    return {"gestor": gestor, "escola": escola, "rota": rota, "casa": casa, "na_escola": na_escola}


def _item(estudante, parada, **extra):
    return {
        "estudante_id": estudante.id,
        "parada_id": parada.id,
        "dias_semana": [0, 1, 2, 3, 4],
        "vigencia_inicio": HOJE.isoformat(),
        **extra,
    }


def _inscrever(client, c, *itens):
    return client.put(
        f"/rotas/{c['rota']['id']}/inscricoes",
        json={"inscricoes": list(itens)},
        headers=c["gestor"],
    )


def test_gestor_inscreve_e_lista(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    resposta = _inscrever(client, cenario, _item(ana, cenario["casa"]))
    assert resposta.status_code == 200
    [inscricao] = resposta.json()
    assert inscricao["estudante_nome"] == "Ana"
    assert inscricao["parada_id"] == cenario["casa"].id
    assert inscricao["dias_semana"] == [0, 1, 2, 3, 4]
    assert inscricao["ativa"] is True
    url = f"/rotas/{cenario['rota']['id']}/inscricoes"
    assert client.get(url, headers=cenario["gestor"]).json() == resposta.json()


def test_parada_precisa_fazer_parte_da_rota(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    fora = _parada(db, 0.02, nome="Fora")
    resposta = _inscrever(client, cenario, _item(ana, fora))
    assert resposta.status_code == 422
    assert "não faz parte da rota" in resposta.json()["detail"]


def test_estudante_de_outra_escola_ou_turno_e_recusado(client, db, cenario):
    outra = escola_de_teste(db, "Outra", 1.0, 1.0)
    de_fora = estudante_de_teste(db, "Fora", escola_id=outra.id)
    tarde = estudante_de_teste(db, "Tarde", escola_id=cenario["escola"].id, turno="tarde")
    integral = estudante_de_teste(db, "Integral", escola_id=cenario["escola"].id, turno="integral")
    assert _inscrever(client, cenario, _item(de_fora, cenario["casa"])).status_code == 422
    assert _inscrever(client, cenario, _item(tarde, cenario["casa"])).status_code == 422
    assert _inscrever(client, cenario, _item(integral, cenario["casa"])).status_code == 200


def test_estudante_inexistente_ou_repetido(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    fantasma = {**_item(ana, cenario["casa"]), "estudante_id": 999999}
    assert _inscrever(client, cenario, fantasma).status_code == 422
    assert (
        _inscrever(
            client, cenario, _item(ana, cenario["casa"]), _item(ana, cenario["casa"])
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "alteracao",
    [
        {"dias_semana": []},
        {"dias_semana": [7]},
        {"dias_semana": [-1]},
        {"dias_semana": [1, 1]},
        {"dias_semana": list(range(8))},
        {"vigencia_fim": (HOJE - timedelta(days=1)).isoformat()},
    ],
)
def test_validacao_de_dias_e_vigencia(client, db, cenario, alteracao):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    assert _inscrever(client, cenario, _item(ana, cenario["casa"], **alteracao)).status_code == 422


def test_dias_ficam_ordenados(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    [i] = _inscrever(client, cenario, _item(ana, cenario["casa"], dias_semana=[4, 0, 2])).json()
    assert i["dias_semana"] == [0, 2, 4]


def test_put_substitui_a_lista_e_desativa_quem_saiu(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    beto = estudante_de_teste(db, "Beto", escola_id=cenario["escola"].id)
    _inscrever(client, cenario, _item(ana, cenario["casa"]), _item(beto, cenario["casa"]))

    depois = _inscrever(client, cenario, _item(ana, cenario["na_escola"], dias_semana=[0])).json()
    assert [(i["estudante_nome"], i["parada_id"], i["dias_semana"]) for i in depois] == [
        ("Ana", cenario["na_escola"].id, [0])
    ]
    historico = client.get(
        f"/rotas/{cenario['rota']['id']}/inscricoes?historico=true", headers=cenario["gestor"]
    ).json()
    beto_hist = next(i for i in historico if i["estudante_nome"] == "Beto")
    assert beto_hist["ativa"] is False
    assert beto_hist["vigencia_fim"] == HOJE.isoformat()


def test_um_estudante_nao_tem_duas_inscricoes_ativas_no_mesmo_turno_e_sentido(
    client, db, cabecalhos, cenario
):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    _inscrever(client, cenario, _item(ana, cenario["casa"]))

    gestor = cabecalhos(Perfil.GESTOR)
    corpo = corpo_de_rota(
        db, "Linha 2", escola_id=cenario["escola"].id, turno="manha", sentido="ida"
    )
    outra = client.post("/rotas", json=corpo, headers=gestor).json()
    client.put(
        f"/rotas/{outra['id']}/paradas",
        json={"parada_ids": [cenario["na_escola"].id]},
        headers=gestor,
    )
    db.commit()
    repetida = client.put(
        f"/rotas/{outra['id']}/inscricoes",
        json={"inscricoes": [_item(ana, cenario["na_escola"])]},
        headers=gestor,
    )
    assert repetida.status_code == 409

    # Sentido diferente no mesmo turno é permitido.
    volta = client.post(
        "/rotas",
        json=corpo_de_rota(
            db, "Volta", escola_id=cenario["escola"].id, turno="manha", sentido="volta"
        ),
        headers=gestor,
    ).json()
    client.put(
        f"/rotas/{volta['id']}/paradas",
        json={"parada_ids": [cenario["na_escola"].id]},
        headers=gestor,
    )
    ok = client.put(
        f"/rotas/{volta['id']}/inscricoes",
        json={"inscricoes": [_item(ana, cenario["na_escola"])]},
        headers=gestor,
    )
    assert ok.status_code == 200


def test_veiculo_nao_comporta_mais_que_a_capacidade(client, db, cenario):
    veiculo = Veiculo(placa="AAA1A11", capacidade=1, modelo="V", ano=2020, vistoria_valida_ate=HOJE)
    db.add(veiculo)
    db.flush()
    client.patch(
        f"/rotas/{cenario['rota']['id']}",
        json={"veiculo_id": veiculo.id},
        headers=cenario["gestor"],
    )
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    beto = estudante_de_teste(db, "Beto", escola_id=cenario["escola"].id)
    resposta = _inscrever(
        client, cenario, _item(ana, cenario["casa"]), _item(beto, cenario["casa"])
    )
    assert resposta.status_code == 422
    assert "comporta 1" in resposta.json()["detail"]


def test_rota_com_inscricoes_nao_muda_de_sentido_nem_perde_parada_usada(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    _inscrever(client, cenario, _item(ana, cenario["casa"]))
    url = f"/rotas/{cenario['rota']['id']}"
    h = cenario["gestor"]

    assert client.patch(url, json={"sentido": "volta"}, headers=h).status_code == 409
    assert client.patch(url, json={"nome": "Outro nome"}, headers=h).status_code == 200
    sem_a_casa = client.put(
        f"{url}/paradas", json={"parada_ids": [cenario["na_escola"].id]}, headers=h
    )
    assert sem_a_casa.status_code == 409
    com_as_duas = client.put(
        f"{url}/paradas",
        json={"parada_ids": [cenario["na_escola"].id, cenario["casa"].id]},
        headers=h,
    )
    # A casa continua na rota; só a ponta da escola é que passa a estar errada.
    assert com_as_duas.status_code == 422


def test_so_gestao_mexe_nas_inscricoes(client, db, cenario, cabecalhos):
    url = f"/rotas/{cenario['rota']['id']}/inscricoes"
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL):
        h = cabecalhos(perfil)
        assert client.get(url, headers=h).status_code == 403
        assert client.put(url, json={"inscricoes": []}, headers=h).status_code == 403
    assert client.get("/rotas/999999/inscricoes", headers=cenario["gestor"]).status_code == 404


def test_substituicao_vai_para_a_auditoria(client, db, cenario):
    ana = estudante_de_teste(db, "Ana", escola_id=cenario["escola"].id)
    _inscrever(client, cenario, _item(ana, cenario["casa"]))
    from sqlalchemy import select

    assert db.scalar(select(Auditoria.id).where(Auditoria.acao == "inscricoes.substituir"))


def test_paradas_nao_associam_mais_estudante_direto(client, db, cenario):
    ana = estudante_de_teste(db, "Ana")
    url = f"/paradas/{cenario['casa'].id}/estudantes/{ana.id}"
    assert client.put(url, headers=cenario["gestor"]).status_code in (404, 405)
    assert client.delete(url, headers=cenario["gestor"]).status_code in (404, 405)


# Ausências


@pytest.fixture
def familia(db, criar_usuario):
    filho = estudante_de_teste(db, "Bia")
    outro = estudante_de_teste(db, "Caio")
    mae = criar_usuario(Perfil.RESPONSAVEL)
    vinculo = ResponsavelEstudante(
        responsavel_id=mae.id,
        estudante_id=filho.id,
        parentesco="mãe",
        consentimento_em=datetime.now(UTC),
        consentimento_versao=settings.versao_termo_consentimento,
    )
    db.add(vinculo)
    db.flush()
    return {
        "filho": filho,
        "outro": outro,
        "mae": mae,
        "vinculo": vinculo,
        "h": {"Authorization": f"Bearer {criar_token(mae)}"},
    }


def _ausencia(client, f, **extra):
    corpo = {"estudante_id": f["filho"].id, "data": (HOJE + timedelta(days=1)).isoformat(), **extra}
    return client.post("/ausencias", json=corpo, headers=f["h"])


def test_responsavel_avisa_e_cancela_a_ausencia_do_filho(client, familia):
    criada = _ausencia(client, familia)
    assert criada.status_code == 201
    assert criada.json()["sentido"] is None
    assert [a["id"] for a in client.get("/ausencias", headers=familia["h"]).json()] == [
        criada.json()["id"]
    ]
    assert (
        client.delete(f"/ausencias/{criada.json()['id']}", headers=familia["h"]).status_code == 204
    )
    assert client.get("/ausencias", headers=familia["h"]).json() == []


def test_so_os_proprios_filhos_e_so_com_consentimento(client, familia):
    alheio = {"estudante_id": familia["outro"].id, "data": HOJE.isoformat()}
    assert client.post("/ausencias", json=alheio, headers=familia["h"]).status_code == 404
    familia["vinculo"].consentimento_em = None
    assert _ausencia(client, familia).status_code == 403


def test_nao_cancela_ausencia_de_outra_familia(client, db, familia, criar_usuario):
    criada = _ausencia(client, familia).json()
    intrusa = {"Authorization": f"Bearer {criar_token(criar_usuario(Perfil.RESPONSAVEL))}"}
    assert client.delete(f"/ausencias/{criada['id']}", headers=intrusa).status_code == 404
    assert client.delete("/ausencias/999999", headers=familia["h"]).status_code == 404
    assert client.get("/ausencias", headers=intrusa).json() == []


def test_janela_de_datas(client, familia):
    assert _ausencia(client, familia, data=HOJE.isoformat()).status_code == 201
    ontem = _ausencia(client, familia, data=(HOJE - timedelta(days=1)).isoformat())
    longe = _ausencia(client, familia, data=(HOJE + timedelta(days=61)).isoformat())
    assert ontem.status_code == 422
    assert longe.status_code == 422


def test_ausencia_repetida_da_409_e_ida_com_volta_convivem(client, familia):
    assert _ausencia(client, familia, sentido="ida").status_code == 201
    assert _ausencia(client, familia, sentido="ida").status_code == 409
    assert _ausencia(client, familia, sentido="volta").status_code == 201
    # "Ambos" não pode coexistir com um dos sentidos no mesmo dia.
    assert _ausencia(client, familia).status_code == 409


def test_gestao_nao_usa_as_rotas_de_ausencia(client, cabecalhos, familia):
    h = cabecalhos(Perfil.GESTOR)
    assert client.get("/ausencias", headers=h).status_code == 403
    assert (
        client.post(
            "/ausencias", json={"estudante_id": 1, "data": HOJE.isoformat()}, headers=h
        ).status_code
        == 403
    )
