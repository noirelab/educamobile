"""Posições do ônibus, cercas, previsão, acompanhamento do responsável e painel da frota."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app import tempo_real
from app.config import settings
from app.models import (
    Auditoria,
    Inscricao,
    Motorista,
    Perfil,
    Posicao,
    ResponsavelEstudante,
    Sentido,
    Turno,
    Veiculo,
    Viagem,
    ViagemParada,
)
from app.security import criar_token
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste
from tests.test_rotas import _parada

HOJE = date.today()
AGORA = datetime.now(UTC)
# 0,001 grau de latitude mede cerca de 110 m. O trajeto segue o meridiano: lat 0.00 a 0.03.
LAT_ESCOLA = 0.03


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _t(segundos):
    """Instante no passado recente; `segundos` crescentes andam para frente no tempo."""
    return (AGORA - timedelta(minutes=8) + timedelta(seconds=segundos)).isoformat()


def _pos(lat, segundos, **extra):
    return {"registrada_em": _t(segundos), "latitude": lat, "longitude": 0.0, **extra}


@pytest.fixture
def mundo(client, db, cabecalhos, criar_usuario):
    """Ida pelo meridiano: parada A em 0.01, B em 0.02, escola em 0.03. Viagem já iniciada."""
    escola = escola_de_teste(db, "Escola", LAT_ESCOLA, 0.0, raio_cerca_m=150)
    a, b = _parada(db, 0.01, nome="A"), _parada(db, 0.02, nome="B")
    na_escola = _parada(db, LAT_ESCOLA, nome="Escola")
    motorista = criar_usuario(Perfil.MOTORISTA)
    db.add(
        Motorista(
            usuario_id=motorista.id,
            cnh="11111111111",
            categoria_cnh="D",
            cnh_valida_ate=HOJE + timedelta(days=100),
            curso_transporte_escolar_ate=HOJE + timedelta(days=100),
        )
    )
    veiculo = Veiculo(
        placa="AAA1A11",
        capacidade=40,
        modelo="V",
        ano=2020,
        vistoria_valida_ate=HOJE + timedelta(days=100),
    )
    db.add(veiculo)
    db.flush()
    rota = rota_de_teste(
        db,
        "Linha",
        escola_id=escola.id,
        turno=Turno.MANHA,
        sentido=Sentido.IDA,
        veiculo_id=veiculo.id,
        motorista_id=motorista.id,
    )
    gestor = cabecalhos(Perfil.GESTOR)
    client.put(
        f"/rotas/{rota.id}/paradas", json={"parada_ids": [a.id, b.id, na_escola.id]}, headers=gestor
    )
    ana = estudante_de_teste(db, "Ana", escola_id=escola.id)
    beto = estudante_de_teste(db, "Beto", escola_id=escola.id)
    for e, p in ((ana, a), (beto, b)):
        db.add(
            Inscricao(
                estudante_id=e.id,
                rota_id=rota.id,
                parada_id=p.id,
                turno=Turno.MANHA,
                sentido=Sentido.IDA,
                dias_semana=list(range(7)),
                vigencia_inicio=HOJE,
            )
        )
    db.flush()
    viagem = client.post("/viagens/gerar", json={"rota_id": rota.id}, headers=gestor).json()[0]
    client.post(f"/viagens/{viagem['id']}/iniciar", headers=_h(motorista))
    return {
        "viagem": viagem,
        "gestor": gestor,
        "motorista": motorista,
        "hm": _h(motorista),
        "ana": ana,
        "beto": beto,
        "a": a,
        "b": b,
        "escola": escola,
        "veiculo": veiculo,
        "rota": rota,
    }


def _enviar(client, m, *posicoes, quem="hm"):
    return client.post(
        f"/viagens/{m['viagem']['id']}/posicoes", json={"posicoes": list(posicoes)}, headers=m[quem]
    )


# Recebimento


def test_lote_gravado_e_ultima_posicao_no_redis(client, db, mundo):
    r = _enviar(client, mundo, _pos(0.0, 0), _pos(0.001, 10), _pos(0.002, 20, velocidade_kmh=36))
    assert [x["resultado"] for x in r.json()] == ["aceita"] * 3
    assert db.scalar(select(text("count(*)")).select_from(Posicao)) == 3
    ultima = tempo_real.ler_posicao(mundo["viagem"]["id"])
    assert ultima["latitude"] == 0.002
    assert ultima["velocidade_kmh"] == 36


def test_reenviar_o_lote_nao_duplica(client, db, mundo):
    lote = [_pos(0.0, 0), _pos(0.001, 10)]
    _enviar(client, mundo, *lote)
    r = _enviar(client, mundo, *lote)
    assert [x["resultado"] for x in r.json()] == ["duplicada", "duplicada"]
    assert db.scalar(select(text("count(*)")).select_from(Posicao)) == 2


def test_lote_atrasado_nao_regride_a_ultima_posicao(client, mundo):
    _enviar(client, mundo, _pos(0.005, 100))
    _enviar(client, mundo, _pos(0.001, 10), _pos(0.002, 20))
    assert tempo_real.ler_posicao(mundo["viagem"]["id"])["latitude"] == 0.005


@pytest.mark.parametrize(
    ("posicao", "motivo"),
    [
        (
            {
                "registrada_em": (AGORA + timedelta(hours=1)).isoformat(),
                "latitude": 0,
                "longitude": 0,
            },
            "Data no futuro",
        ),
        (_pos(0.0, 0, velocidade_kmh=250), "Velocidade informada impossível"),
    ],
)
def test_recusa_futuro_e_velocidade_impossivel(client, mundo, posicao, motivo):
    r = _enviar(client, mundo, posicao)
    assert r.json()[0]["resultado"] == "rejeitada"
    assert r.json()[0]["motivo"] == motivo


def test_recusa_salto_de_velocidade_absurdo(client, db, mundo):
    # 0,01 grau (1,1 km) em 5 s são 800 km/h.
    r = _enviar(client, mundo, _pos(0.0, 0), _pos(0.01, 5), _pos(0.001, 10))
    assert [x["resultado"] for x in r.json()] == ["aceita", "rejeitada", "aceita"]
    assert r.json()[1]["motivo"] == "Salto de velocidade impossível"
    assert db.scalar(select(text("count(*)")).select_from(Posicao)) == 2


def test_salto_vale_contra_a_posicao_ja_gravada(client, mundo):
    _enviar(client, mundo, _pos(0.0, 0))
    r = _enviar(client, mundo, _pos(0.05, 5))
    assert r.json()[0]["resultado"] == "rejeitada"


def test_recusa_posicao_anterior_ao_inicio_da_viagem(client, mundo):
    antiga = {
        "registrada_em": (AGORA - timedelta(hours=5)).isoformat(),
        "latitude": 0,
        "longitude": 0,
    }
    assert _enviar(client, mundo, antiga).json()[0]["motivo"] == "Anterior ao início da viagem"


@pytest.mark.parametrize(
    "ruim",
    [
        {"latitude": 91, "longitude": 0},
        {"latitude": 0, "longitude": -181},
        {"latitude": "x", "longitude": 0},
        {"latitude": 0, "longitude": 0, "velocidade_kmh": -1},
        {"latitude": 0, "longitude": 0, "registrada_em": "2026-11-23T07:00:00"},
    ],
)
def test_coordenadas_e_campos_invalidos_dao_422(client, mundo, ruim):
    corpo = {"registrada_em": _t(0), **ruim}
    assert _enviar(client, mundo, corpo).status_code == 422


def test_lote_vazio_ou_grande_demais(client, mundo):
    url = f"/viagens/{mundo['viagem']['id']}/posicoes"
    assert client.post(url, json={"posicoes": []}, headers=mundo["hm"]).status_code == 422
    muitas = [_pos(0.0, i) for i in range(501)]
    assert client.post(url, json={"posicoes": muitas}, headers=mundo["hm"]).status_code == 422


def test_so_o_motorista_escalado_e_so_com_a_viagem_em_andamento(
    client, db, mundo, criar_usuario, cabecalhos
):
    url = f"/viagens/{mundo['viagem']['id']}/posicoes"
    corpo = {"posicoes": [_pos(0.0, 0)]}
    assert (
        client.post(url, json=corpo, headers=_h(criar_usuario(Perfil.MOTORISTA))).status_code == 404
    )
    for perfil in (Perfil.MONITOR, Perfil.RESPONSAVEL, Perfil.GESTOR):
        assert client.post(url, json=corpo, headers=cabecalhos(perfil)).status_code == 403
    assert client.post(url, json=corpo).status_code == 401
    db.get(Viagem, mundo["viagem"]["id"]).status = "concluida"
    db.flush()
    assert client.post(url, json=corpo, headers=mundo["hm"]).status_code == 409


# Rastreador veicular


def test_rastreador_autentica_pelo_veiculo(client, db, mundo):
    token = client.post(
        f"/veiculos/{mundo['veiculo'].id}/token-rastreador", headers=mundo["gestor"]
    ).json()["token"]
    r = client.post(
        "/rastreador/posicoes",
        json={"posicoes": [_pos(0.0, 0)]},
        headers={"X-Token-Rastreador": token},
    )
    assert r.status_code == 200
    assert r.json()[0]["resultado"] == "aceita"
    assert db.scalar(select(Posicao.fonte)) == "rastreador"
    assert token not in str(db.scalar(select(Veiculo.token_rastreador_hash)))


def test_rastreador_com_token_errado_revogado_ou_sem_viagem(client, db, mundo):
    corpo = {"posicoes": [_pos(0.0, 0)]}
    assert (
        client.post(
            "/rastreador/posicoes", json=corpo, headers={"X-Token-Rastreador": "x" * 40}
        ).status_code
        == 401
    )
    assert client.post("/rastreador/posicoes", json=corpo).status_code == 422
    url = f"/veiculos/{mundo['veiculo'].id}/token-rastreador"
    antigo = client.post(url, headers=mundo["gestor"]).json()["token"]
    novo = client.post(url, headers=mundo["gestor"]).json()["token"]
    assert (
        client.post(
            "/rastreador/posicoes", json=corpo, headers={"X-Token-Rastreador": antigo}
        ).status_code
        == 401
    )
    assert client.delete(url, headers=mundo["gestor"]).status_code == 204
    assert (
        client.post(
            "/rastreador/posicoes", json=corpo, headers={"X-Token-Rastreador": novo}
        ).status_code
        == 401
    )


def test_token_do_rastreador_so_a_gestao_gera(client, mundo, cabecalhos):
    url = f"/veiculos/{mundo['veiculo'].id}/token-rastreador"
    assert client.post(url, headers=cabecalhos(Perfil.MOTORISTA)).status_code == 403
    assert (
        client.post("/veiculos/999999/token-rastreador", headers=mundo["gestor"]).status_code == 404
    )


def test_rastreador_sem_viagem_em_andamento_da_409(client, db, mundo):
    token = client.post(
        f"/veiculos/{mundo['veiculo'].id}/token-rastreador", headers=mundo["gestor"]
    ).json()["token"]
    db.get(Viagem, mundo["viagem"]["id"]).status = "concluida"
    db.flush()
    r = client.post(
        "/rastreador/posicoes",
        json={"posicoes": [_pos(0.0, 0)]},
        headers={"X-Token-Rastreador": token},
    )
    assert r.status_code == 409


# Leitura


def test_posicao_e_percurso(client, mundo):
    _enviar(client, mundo, _pos(0.0, 0), _pos(0.001, 10), _pos(0.002, 20))
    url = f"/viagens/{mundo['viagem']['id']}"
    estado = client.get(f"{url}/posicao", headers=mundo["gestor"]).json()
    assert estado["posicao"]["latitude"] == 0.002
    assert estado["proxima_parada"]["nome"] == "A"
    caminho = client.get(f"{url}/percurso", headers=mundo["hm"]).json()
    assert [p["latitude"] for p in caminho] == [0.0, 0.001, 0.002]
    desde = client.get(f"{url}/percurso", params={"desde": _t(10)}, headers=mundo["gestor"]).json()
    assert [p["latitude"] for p in desde] == [0.002]


def test_sem_posicao_ainda(client, mundo):
    estado = client.get(f"/viagens/{mundo['viagem']['id']}/posicao", headers=mundo["gestor"]).json()
    assert estado["posicao"] is None


def test_leitura_cai_para_o_banco_se_o_redis_falhar(client, db, mundo, monkeypatch):
    import redis

    _enviar(client, mundo, _pos(0.003, 0))

    def quebrado(_):
        raise redis.ConnectionError("fora do ar")

    monkeypatch.setattr(tempo_real, "ler_posicao", quebrado)
    estado = client.get(f"/viagens/{mundo['viagem']['id']}/posicao", headers=mundo["gestor"]).json()
    assert estado["posicao"]["latitude"] == pytest.approx(0.003)


def test_leitura_so_para_a_equipe_escalada(client, mundo, criar_usuario):
    url = f"/viagens/{mundo['viagem']['id']}/posicao"
    assert client.get(url, headers=_h(criar_usuario(Perfil.MOTORISTA))).status_code == 404
    assert client.get(url, headers=_h(criar_usuario(Perfil.RESPONSAVEL))).status_code == 403


# Cercas virtuais, previsão e desvio


def test_chegada_e_partida_nas_paradas(client, db, mundo):
    _enviar(client, mundo, _pos(0.0, 0), _pos(0.0095, 60), _pos(0.0101, 70), _pos(0.012, 90))
    a = db.get(ViagemParada, (mundo["viagem"]["id"], mundo["a"].id))
    b = db.get(ViagemParada, (mundo["viagem"]["id"], mundo["b"].id))
    assert a.chegada_em is not None
    assert a.partida_em is not None and a.partida_em > a.chegada_em
    assert b.chegada_em is None


def test_fora_do_raio_nao_chega(client, db, mundo):
    _enviar(client, mundo, _pos(0.0, 0), _pos(0.0075, 60))
    assert db.get(ViagemParada, (mundo["viagem"]["id"], mundo["a"].id)).chegada_em is None


def test_cercas_em_lote_fora_de_ordem(client, db, mundo):
    _enviar(client, mundo, _pos(0.012, 90), _pos(0.0, 0), _pos(0.0101, 70))
    a = db.get(ViagemParada, (mundo["viagem"]["id"], mundo["a"].id))
    assert a.chegada_em is not None and a.partida_em is not None


def test_modo_da_lista_muda_para_desembarque_ao_chegar_na_escola(client, mundo):
    url = f"/viagens/{mundo['viagem']['id']}/lista"
    assert client.get(url, headers=mundo["hm"]).json()["modo"] == "embarque"
    _enviar(client, mundo, _pos(0.02, 0), _pos(LAT_ESCOLA - 0.0005, 60))
    assert client.get(url, headers=mundo["hm"]).json()["modo"] == "desembarque"


def test_previsao_de_chegada_pela_distancia_restante_e_velocidade(client, mundo):
    # Anda 0,001 grau (cerca de 111 m) a cada 10 s: perto de 40 km/h.
    pontos = [_pos(0.001 * i, 10 * i) for i in range(6)]
    _enviar(client, mundo, *pontos)
    estado = client.get(f"/viagens/{mundo['viagem']['id']}/posicao", headers=mundo["gestor"]).json()
    prev = estado["proxima_parada"]["previsao"]
    assert prev["parada_id"] == mundo["a"].id
    # Faltam 5 centésimos de grau até A (em 0.01): cerca de 555 m.
    assert prev["distancia_restante_m"] == pytest.approx(0.005 * 111_320, rel=0.03)
    assert prev["eta_segundos"] == pytest.approx(
        prev["distancia_restante_m"] / (111.32 / 10), rel=0.1
    )


def test_onibus_parado_nao_gera_previsao_absurda(client, mundo):
    _enviar(client, mundo, *[_pos(0.0, 10 * i) for i in range(5)])
    prev = client.get(f"/viagens/{mundo['viagem']['id']}/posicao", headers=mundo["gestor"]).json()[
        "proxima_parada"
    ]["previsao"]
    assert prev["eta_segundos"] is None
    assert prev["distancia_restante_m"] > 0


def test_desvio_em_relacao_ao_trajeto_previsto(client, mundo):
    _enviar(client, mundo, {"registrada_em": _t(0), "latitude": 0.015, "longitude": 0.001})
    desvio = tempo_real.ler_posicao(mundo["viagem"]["id"])["desvio_m"]
    assert desvio == pytest.approx(0.001 * 111_320, rel=0.02)
    _enviar(client, mundo, _pos(0.016, 20))
    assert tempo_real.ler_posicao(mundo["viagem"]["id"])["desvio_m"] == pytest.approx(0, abs=1)


def test_saida_da_escola_com_crianca_a_bordo_gera_alerta_pela_posicao(client, db, mundo):
    """O alerta sai do recebimento da posição, sem o motorista tentar concluir a viagem."""
    cid = mundo["viagem"]["id"]
    client.post(
        f"/viagens/{cid}/eventos",
        json={
            "eventos": [
                {
                    "id": str(uuid.uuid4()),
                    "tipo": "embarque",
                    "estudante_id": mundo["ana"].id,
                    "hora_aparelho": _t(5),
                }
            ]
        },
        headers=mundo["hm"],
    )
    _enviar(client, mundo, _pos(LAT_ESCOLA - 0.0005, 60), _pos(LAT_ESCOLA - 0.003, 120))
    alertas = client.get("/alertas", headers=mundo["gestor"]).json()
    assert [(a["tipo"], a["severidade"]) for a in alertas] == [
        ("crianca_a_bordo_fora_da_escola", "critico")
    ]


# Acompanhamento do responsável


def _mae(db, criar_usuario, estudante, consentido=True):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    db.add(
        ResponsavelEstudante(
            responsavel_id=mae.id,
            estudante_id=estudante.id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC) if consentido else None,
            consentimento_versao=settings.versao_termo_consentimento if consentido else None,
        )
    )
    db.flush()
    return mae


def _evento(client, m, tipo, estudante, segundos):
    return client.post(
        f"/viagens/{m['viagem']['id']}/eventos",
        json={
            "eventos": [
                {
                    "id": str(uuid.uuid4()),
                    "tipo": tipo,
                    "estudante_id": estudante.id,
                    "hora_aparelho": _t(segundos),
                }
            ]
        },
        headers=m["hm"],
    )


def test_responsavel_ve_o_onibus_enquanto_o_filho_esta_na_viagem(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _enviar(client, mundo, *[_pos(0.001 * i, 10 * i) for i in range(5)])
    hoje = client.get(f"/responsavel/filhos/{mundo['ana'].id}/hoje", headers=_h(mae)).json()

    [viagem] = hoje["viagens"]
    assert viagem["situacao_do_filho"] == "aguardando"
    assert viagem["parada_nome"] == "A"
    assert viagem["onibus"] == {"placa": "AAA1A11", "motorista_nome": mundo["motorista"].nome}
    assert viagem["posicao"]["latitude"] == pytest.approx(0.004)
    assert viagem["previsao"]["parada_id"] == mundo["a"].id
    assert viagem["previsao"]["distancia_restante_m"] > 0


def test_responsavel_nunca_recebe_dados_de_outros_alunos(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _enviar(client, mundo, _pos(0.0, 0))
    texto = client.get(f"/responsavel/filhos/{mundo['ana'].id}/hoje", headers=_h(mae)).text
    for proibido in (
        "Beto",
        str(mundo["beto"].id) + '"',
        "alunos",
        "observacoes",
        "data_nascimento",
    ):
        assert proibido not in texto


def test_sem_posicao_antes_do_inicio_e_depois_do_desembarque(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["beto"])
    h = _h(mae)
    url = f"/responsavel/filhos/{mundo['beto'].id}/hoje"
    _enviar(client, mundo, _pos(0.0, 0))
    assert client.get(url, headers=h).json()["viagens"][0]["posicao"] is not None

    _evento(client, mundo, "embarque", mundo["beto"], 10)
    assert client.get(url, headers=h).json()["viagens"][0]["posicao"] is not None
    _evento(client, mundo, "desembarque", mundo["beto"], 40)
    depois = client.get(url, headers=h).json()["viagens"][0]
    assert depois["situacao_do_filho"] == "desembarcou"
    assert depois["posicao"] is None
    assert depois["previsao"] is None


def test_antes_do_inicio_da_viagem_nao_ha_posicao(client, db, mundo, criar_usuario, cabecalhos):
    mae = _mae(db, criar_usuario, mundo["ana"])
    amanha = (HOJE + timedelta(days=1)).isoformat()
    # Viagem agendada de hoje para outra rota: a do filho ainda não começou.
    db.get(Viagem, mundo["viagem"]["id"]).status = "agendada"
    db.flush()
    tempo_real.guardar_posicao(
        mundo["viagem"]["id"],
        {
            "viagem_id": 1,
            "latitude": 0,
            "longitude": 0,
            "registrada_em": _t(0),
            "ts": 1,
            "velocidade_kmh": None,
            "desvio_m": None,
        },
    )
    [viagem] = client.get(f"/responsavel/filhos/{mundo['ana'].id}/hoje", headers=_h(mae)).json()[
        "viagens"
    ]
    assert viagem["status_viagem"] == "agendada"
    assert viagem["posicao"] is None
    assert amanha


@pytest.mark.parametrize("situacao", ["nao_embarcou", "ausencia_avisada"])
def test_filho_que_nao_esta_no_onibus_nao_da_acesso_a_posicao(
    client, db, mundo, criar_usuario, situacao
):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _enviar(client, mundo, _pos(0.0, 0))
    if situacao == "nao_embarcou":
        _evento(client, mundo, "nao_embarcou", mundo["ana"], 5)
    else:
        from app.models import StatusAluno, ViagemAluno

        db.get(
            ViagemAluno, (mundo["viagem"]["id"], mundo["ana"].id)
        ).status = StatusAluno.AUSENCIA_AVISADA
        db.flush()
    [viagem] = client.get(f"/responsavel/filhos/{mundo['ana'].id}/hoje", headers=_h(mae)).json()[
        "viagens"
    ]
    assert viagem["posicao"] is None


def test_exige_vinculo_e_consentimento(client, db, mundo, criar_usuario):
    sem_vinculo = _h(criar_usuario(Perfil.RESPONSAVEL))
    url = f"/responsavel/filhos/{mundo['ana'].id}/hoje"
    assert client.get(url, headers=sem_vinculo).status_code == 404
    pendente = _mae(db, criar_usuario, mundo["ana"], consentido=False)
    assert client.get(url, headers=_h(pendente)).status_code == 403
    outra_mae = _mae(db, criar_usuario, mundo["beto"])
    assert client.get(url, headers=_h(outra_mae)).status_code == 404


def test_cada_consulta_a_posicao_vai_para_a_auditoria(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _enviar(client, mundo, _pos(0.0, 0))
    url = f"/responsavel/filhos/{mundo['ana'].id}/hoje"
    for _ in range(2):
        client.get(url, headers=_h(mae))
    _evento(client, mundo, "nao_embarcou", mundo["ana"], 5)
    client.get(url, headers=_h(mae))
    registros = db.scalars(select(Auditoria).where(Auditoria.acao == "posicao.consultar")).all()
    assert [r.detalhes["liberada"] for r in registros] == [True, True, False]
    assert all(r.usuario_id == mae.id for r in registros)


def test_so_responsavel_usa_o_acompanhamento(client, mundo, cabecalhos):
    url = f"/responsavel/filhos/{mundo['ana'].id}/hoje"
    for perfil in (Perfil.GESTOR, Perfil.MOTORISTA, Perfil.MONITOR):
        assert client.get(url, headers=cabecalhos(perfil)).status_code == 403


# Painel da frota


def test_painel_da_frota(client, db, mundo):
    _enviar(client, mundo, _pos(0.002, 0))
    _evento(client, mundo, "embarque", mundo["ana"], 5)
    [item] = client.get("/painel/frota", headers=mundo["gestor"]).json()
    assert item["viagem_id"] == mundo["viagem"]["id"]
    assert item["status"] == "em_andamento"
    assert item["placa"] == "AAA1A11"
    assert item["motorista_nome"] == mundo["motorista"].nome
    assert item["posicao"]["latitude"] == 0.002
    assert item["alunos_a_bordo"] == 1
    assert item["alertas_abertos"] == 0


def test_painel_le_a_posicao_do_redis_e_nao_do_banco(client, db, mundo, monkeypatch):
    _enviar(client, mundo, _pos(0.002, 0))
    db.execute(text("DELETE FROM posicao"))
    [item] = client.get("/painel/frota", headers=mundo["gestor"]).json()
    assert item["posicao"]["latitude"] == 0.002


def test_painel_com_filtros(client, mundo):
    h = mundo["gestor"]
    escola = mundo["escola"].id
    assert len(client.get(f"/painel/frota?escola_id={escola}", headers=h).json()) == 1
    assert client.get("/painel/frota?escola_id=999999", headers=h).json() == []
    assert client.get("/painel/frota?turno=tarde", headers=h).json() == []
    assert client.get("/painel/frota?situacao=concluida", headers=h).json() == []
    assert len(client.get("/painel/frota?situacao=em_andamento&turno=manha", headers=h).json()) == 1


def test_painel_mostra_atraso_da_proxima_parada(client, db, mundo):
    """A parada A estava prevista para uma hora atrás e o ônibus ainda não chegou."""
    from zoneinfo import ZoneInfo

    local = datetime.now(ZoneInfo(settings.fuso_horario)) - timedelta(minutes=45)
    db.get(ViagemParada, (mundo["viagem"]["id"], mundo["a"].id)).horario_previsto = local.time()
    db.flush()
    [item] = client.get("/painel/frota", headers=mundo["gestor"]).json()
    assert item["atraso_min"] in (44, 45, 46)


def test_painel_so_para_a_gestao(client, mundo, cabecalhos):
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL):
        assert client.get("/painel/frota", headers=cabecalhos(perfil)).status_code == 403
    assert client.get("/painel/frota").status_code == 401


def test_posicao_com_precisao_ruim_nao_vira_referencia(client, db, mundo):
    ruim = {"registrada_em": _t(0), "latitude": 40.0, "longitude": 40.0, "precisao_m": 5000}
    r = _enviar(client, mundo, ruim, _pos(0.0, 20))
    assert [x["resultado"] for x in r.json()] == ["rejeitada", "aceita"]
    assert r.json()[0]["motivo"] == "Precisão do GPS ruim"
