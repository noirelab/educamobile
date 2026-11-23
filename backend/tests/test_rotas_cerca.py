"""Rota com escola, turno, sentido, horários e cerca da escola."""

import pytest

from app.models import Motorista, Perfil, Veiculo
from tests.conftest import corpo_de_rota, escola_de_teste
from tests.test_rotas import _parada

# 0,001 grau de latitude mede cerca de 110 m.
RAIO = 150


def _rota(client, db, h, sentido="ida", **extra):
    escola = escola_de_teste(db, "Escola", 0.0, 0.0, raio_cerca_m=RAIO)
    corpo = corpo_de_rota(db, "R", escola_id=escola.id, sentido=sentido, **extra)
    resposta = client.post("/rotas", json=corpo, headers=h)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_rota_nasce_com_escola_turno_e_sentido(client, db, cabecalhos):
    corpo = corpo_de_rota(db, "Linha Norte", turno="tarde", sentido="volta")
    rota = client.post("/rotas", json=corpo, headers=cabecalhos(Perfil.GESTOR)).json()
    assert (rota["escola_id"], rota["turno"], rota["sentido"]) == (
        corpo["escola_id"],
        "tarde",
        "volta",
    )
    assert rota["veiculo_id"] is None
    assert rota["motorista_id"] is None


@pytest.mark.parametrize("campo", ["escola_id", "turno", "sentido"])
def test_escola_turno_e_sentido_sao_obrigatorios(client, db, cabecalhos, campo):
    corpo = corpo_de_rota(db)
    del corpo[campo]
    assert client.post("/rotas", json=corpo, headers=cabecalhos()).status_code == 422


def test_valores_invalidos(client, db, cabecalhos):
    h = cabecalhos()
    assert (
        client.post("/rotas", json={**corpo_de_rota(db), "sentido": "lado"}, headers=h).status_code
        == 422
    )
    assert (
        client.post("/rotas", json={**corpo_de_rota(db), "turno": "noite"}, headers=h).status_code
        == 422
    )


def test_escola_veiculo_ou_motorista_inexistente_da_409(client, db, cabecalhos):
    h = cabecalhos()
    db.commit()
    assert (
        client.post(
            "/rotas", json={**corpo_de_rota(db), "escola_id": 999999}, headers=h
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/rotas", json={**corpo_de_rota(db, "R2"), "veiculo_id": 999999}, headers=h
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/rotas", json={**corpo_de_rota(db, "R3"), "motorista_id": 999999}, headers=h
        ).status_code
        == 409
    )


def test_veiculo_e_motorista_padrao_podem_ser_trocados_e_limpos(
    client, db, cabecalhos, criar_usuario
):
    from datetime import date

    h = cabecalhos(Perfil.GESTOR)
    veiculo = Veiculo(
        placa="AAA1A11", capacidade=40, modelo="A", ano=2020, vistoria_valida_ate=date.today()
    )
    usuario = criar_usuario(Perfil.MOTORISTA)
    db.add_all(
        [
            veiculo,
            Motorista(
                usuario_id=usuario.id,
                cnh="11111111111",
                categoria_cnh="D",
                cnh_valida_ate=date.today(),
                curso_transporte_escolar_ate=date.today(),
            ),
        ]
    )
    db.flush()
    rota = _rota(client, db, h)
    url = f"/rotas/{rota['id']}"

    atualizada = client.patch(
        url, json={"veiculo_id": veiculo.id, "motorista_id": usuario.id}, headers=h
    ).json()
    assert (atualizada["veiculo_id"], atualizada["motorista_id"]) == (veiculo.id, usuario.id)
    limpa = client.patch(url, json={"veiculo_id": None}, headers=h).json()
    assert limpa["veiculo_id"] is None
    assert limpa["motorista_id"] == usuario.id


def test_patch_vazio_ou_com_nulo_invalido(client, db, cabecalhos):
    h = cabecalhos()
    url = f"/rotas/{_rota(client, db, h)['id']}"
    assert client.patch(url, json={}, headers=h).status_code == 422
    assert client.patch(url, json={"turno": None}, headers=h).status_code == 422


# A última parada da ida (ou a primeira da volta) é a escola.


def test_ida_termina_na_escola(client, db, cabecalhos):
    h = cabecalhos()
    casa, perto, longe = _parada(db, 0.01), _parada(db, 0.001), _parada(db, 0.5)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"

    assert client.put(url, json={"parada_ids": [casa.id, perto.id]}, headers=h).status_code == 200
    recusada = client.put(url, json={"parada_ids": [perto.id, longe.id]}, headers=h)
    assert recusada.status_code == 422
    assert "última parada da rota de ida" in recusada.json()["detail"]
    # A rejeição não pode apagar o que já estava gravado.
    assert len(client.get(url.removesuffix("/paradas"), headers=h).json()["paradas"]) == 2


def test_volta_comeca_na_escola(client, db, cabecalhos):
    h = cabecalhos()
    escola_aqui, casa = _parada(db, 0.0005), _parada(db, 0.5)
    url = f"/rotas/{_rota(client, db, h, sentido='volta')['id']}/paradas"

    assert (
        client.put(url, json={"parada_ids": [escola_aqui.id, casa.id]}, headers=h).status_code
        == 200
    )
    recusada = client.put(url, json={"parada_ids": [casa.id, escola_aqui.id]}, headers=h)
    assert recusada.status_code == 422
    assert "primeira parada da rota de volta" in recusada.json()["detail"]


def test_cerca_da_escola_vale_na_borda(client, db, cabecalhos):
    h = cabecalhos()
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    # Raio de 150 m: 0,001 grau (110 m) cabe; 0,0015 grau (166 m) não.
    assert (
        client.put(url, json={"parada_ids": [_parada(db, 0.001).id]}, headers=h).status_code == 200
    )
    assert (
        client.put(url, json={"parada_ids": [_parada(db, 0.0015).id]}, headers=h).status_code == 422
    )


def test_mudar_sentido_revalida_a_ponta(client, db, cabecalhos):
    h = cabecalhos()
    rota = _rota(client, db, h)
    url = f"/rotas/{rota['id']}"
    perto, longe = _parada(db, 0.0005), _parada(db, 0.5)
    client.put(f"{url}/paradas", json={"parada_ids": [longe.id, perto.id]}, headers=h)
    resposta = client.patch(url, json={"sentido": "volta"}, headers=h)
    assert resposta.status_code == 422
    assert client.get(url, headers=h).json()["sentido"] == "ida"


# Horários e cerca de cada parada


def test_horarios_e_raio_ficam_no_itinerario(client, db, cabecalhos):
    h = cabecalhos()
    a, b = _parada(db, 0.01), _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    corpo = {
        "paradas": [
            {"parada_id": a.id, "horario_previsto": "06:30:00", "raio_cerca_m": 80},
            {"parada_id": b.id, "horario_previsto": "07:05:00"},
        ]
    }
    rota = client.put(url, json=corpo, headers=h).json()
    assert rota["itinerario"] == [
        {"parada_id": a.id, "ordem": 0, "horario_previsto": "06:30:00", "raio_cerca_m": 80},
        {"parada_id": b.id, "ordem": 1, "horario_previsto": "07:05:00", "raio_cerca_m": 50},
    ]
    assert [p["id"] for p in rota["paradas"]] == [a.id, b.id]


def test_parada_ids_continua_funcionando_sem_horarios(client, db, cabecalhos):
    h = cabecalhos()
    a, b = _parada(db, 0.01), _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    rota = client.put(url, json={"parada_ids": [a.id, b.id]}, headers=h).json()
    assert [i["horario_previsto"] for i in rota["itinerario"]] == [None, None]


@pytest.mark.parametrize(
    "horarios",
    [["07:00:00", "06:00:00"], ["07:00:00", "07:00:00"]],
)
def test_horarios_precisam_crescer(client, db, cabecalhos, horarios):
    h = cabecalhos()
    a, b = _parada(db, 0.01), _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    corpo = {
        "paradas": [
            {"parada_id": a.id, "horario_previsto": horarios[0]},
            {"parada_id": b.id, "horario_previsto": horarios[1]},
        ]
    }
    assert client.put(url, json=corpo, headers=h).status_code == 422


def test_horario_ausente_no_meio_nao_quebra_a_ordem(client, db, cabecalhos):
    h = cabecalhos()
    a, b, c = _parada(db, 0.02), _parada(db, 0.01), _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    corpo = {
        "paradas": [
            {"parada_id": a.id, "horario_previsto": "06:00:00"},
            {"parada_id": b.id},
            {"parada_id": c.id, "horario_previsto": "07:00:00"},
        ]
    }
    assert client.put(url, json=corpo, headers=h).status_code == 200


def test_envie_parada_ids_ou_paradas_nunca_os_dois(client, db, cabecalhos):
    h = cabecalhos()
    a = _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    assert client.put(url, json={}, headers=h).status_code == 422
    ambos = {"parada_ids": [a.id], "paradas": [{"parada_id": a.id}]}
    assert client.put(url, json=ambos, headers=h).status_code == 422


@pytest.mark.parametrize("raio", [0, 9, 1001])
def test_raio_da_cerca_da_parada_tem_limites(client, db, cabecalhos, raio):
    h = cabecalhos()
    a = _parada(db, 0.0005)
    url = f"/rotas/{_rota(client, db, h)['id']}/paradas"
    corpo = {"paradas": [{"parada_id": a.id, "raio_cerca_m": raio}]}
    assert client.put(url, json=corpo, headers=h).status_code == 422


def test_raio_da_cerca_da_escola(client, cabecalhos):
    h = cabecalhos()
    base = {"nome": "E", "localizacao": {"latitude": -25.4, "longitude": -49.2}}
    criada = client.post("/escolas", json=base, headers=h).json()
    assert criada["raio_cerca_m"] == 150
    ok = client.post("/escolas", json={**base, "nome": "F", "raio_cerca_m": 300}, headers=h)
    assert ok.json()["raio_cerca_m"] == 300
    for raio in (19, 2001):
        assert (
            client.post("/escolas", json={**base, "raio_cerca_m": raio}, headers=h).status_code
            == 422
        )
