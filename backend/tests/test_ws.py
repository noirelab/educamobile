"""WebSocket: autenticação na primeira mensagem, escopo por canal e repasse pelo Redis."""

import contextlib
import time
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app import db as app_db
from app.config import settings
from app.db import Base
from app.main import app
from app.models import (
    Inscricao,
    Motorista,
    Perfil,
    ResponsavelEstudante,
    Sentido,
    Turno,
    Veiculo,
    Viagem,
)
from app.security import criar_token
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste
from tests.test_rotas import _parada

HOJE = date.today()
AGORA = datetime.now(UTC)


class SessaoReal(Session):
    """Cada flush vira commit: WebSocket e requisições usam outras sessões, como em produção."""

    _confirmando = False

    def flush(self, objects=None):
        super().flush(objects)
        if not self._confirmando and self.in_transaction():
            self._confirmando = True
            try:
                self.commit()
            finally:
                self._confirmando = False


@pytest.fixture
def db():
    sessao = SessaoReal(bind=app_db.engine, expire_on_commit=False)
    yield sessao
    sessao.close()
    # `configuracao` vem semeada pela migração: apagá-la quebraria os testes seguintes.
    tabelas = ", ".join(
        f'"{t.name}"' for t in Base.metadata.sorted_tables if t.name != "configuracao"
    )
    with app_db.engine.begin() as conexao:
        conexao.execute(text(f"TRUNCATE TABLE {tabelas} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as cliente:
        yield cliente


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _t(segundos):
    return (AGORA - timedelta(minutes=8) + timedelta(seconds=segundos)).isoformat()


@pytest.fixture
def mundo(client, db, cabecalhos, criar_usuario):
    escola = escola_de_teste(db, "Escola", 0.03, 0.0, raio_cerca_m=150)
    a, na_escola = _parada(db, 0.01, nome="A"), _parada(db, 0.03, nome="Escola")
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
        f"/rotas/{rota.id}/paradas", json={"parada_ids": [a.id, na_escola.id]}, headers=gestor
    )
    ana = estudante_de_teste(db, "Ana", escola_id=escola.id)
    beto = estudante_de_teste(db, "Beto", escola_id=escola.id)
    for e in (ana, beto):
        db.add(
            Inscricao(
                estudante_id=e.id,
                rota_id=rota.id,
                parada_id=a.id,
                turno=Turno.MANHA,
                sentido=Sentido.IDA,
                dias_semana=list(range(7)),
                vigencia_inicio=HOJE,
            )
        )
    db.flush()
    viagem = client.post("/viagens/gerar", json={"rota_id": rota.id}, headers=gestor).json()[0]
    return {
        "viagem": viagem,
        "gestor": gestor,
        "hm": _h(motorista),
        "motorista": motorista,
        "ana": ana,
        "beto": beto,
        "veiculo": veiculo,
    }


def _iniciar(client, m):
    return client.post(f"/viagens/{m['viagem']['id']}/iniciar", headers=m["hm"])


def _mae(db, criar_usuario, filho):
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
    return mae


@contextlib.contextmanager
def _abrir(client, usuario_ou_token):
    with client.websocket_connect("/ws") as ws:
        token = (
            usuario_ou_token if isinstance(usuario_ou_token, str) else criar_token(usuario_ou_token)
        )
        ws.send_json({"tipo": "auth", "token": token})
        yield ws


def _receber_ate(ws, tipo, tentativas=20):
    for _ in range(tentativas):
        msg = ws.receive_json()
        if msg.get("tipo") == tipo:
            return msg
    raise AssertionError(f"mensagem {tipo} não chegou")


def _posicao(client, m, lat, segundos):
    return client.post(
        f"/viagens/{m['viagem']['id']}/posicoes",
        json={"posicoes": [{"registrada_em": _t(segundos), "latitude": lat, "longitude": 0.0}]},
        headers=m["hm"],
    )


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


# Autenticação


def test_sem_token_valido_a_conexao_fecha(client, mundo):
    for primeira in (
        {"tipo": "auth", "token": "lixo"},
        {"tipo": "inscrever", "canal": "frota"},
        {"x": 1},
    ):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(primeira)
            with pytest.raises(WebSocketDisconnect) as erro:
                ws.receive_json()
            assert erro.value.code == 4401


def test_token_na_url_nao_vale(client, mundo):
    token = criar_token(mundo["motorista"])
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"tipo": "inscrever", "canal": "frota"})
        with pytest.raises(WebSocketDisconnect) as erro:
            ws.receive_json()
        assert erro.value.code == 4401


def test_token_de_refresh_ou_de_usuario_desativado_nao_entra(client, db, mundo, criar_usuario):
    inativo = criar_usuario(Perfil.GESTOR)
    token = criar_token(inativo)
    inativo.ativo = False
    db.flush()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "auth", "token": token})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_token_vencido_fecha_a_conexao(client, db, mundo, monkeypatch, criar_usuario):
    gestor = criar_usuario(Perfil.GESTOR)
    from app.routers import ws as modulo

    real = modulo.autenticar_token
    monkeypatch.setattr(modulo, "autenticar_token", lambda t, d: (real(t, d)[0], time.time() + 0.4))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "auth", "token": criar_token(gestor)})
        assert ws.receive_json()["tipo"] == "autenticado"
        with pytest.raises(WebSocketDisconnect) as erro:
            ws.receive_json()
        assert erro.value.code == 4401


# Escopo dos canais


def test_gestor_assina_a_frota_e_recebe_a_posicao(client, db, mundo, criar_usuario):
    _iniciar(client, mundo)
    gestor = criar_usuario(Perfil.GESTOR)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "auth", "token": criar_token(gestor)})
        assert ws.receive_json()["tipo"] == "autenticado"
        ws.send_json({"tipo": "inscrever", "canal": "frota"})
        assert ws.receive_json() == {"tipo": "inscrito", "canal": "frota"}
        _posicao(client, mundo, 0.004, 10)
        msg = _receber_ate(ws, "posicao")
        assert msg["canal"] == "frota"
        assert msg["viagem_id"] == mundo["viagem"]["id"]
        assert msg["latitude"] == 0.004


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_so_o_gestor_assina_a_frota(client, mundo, criar_usuario, perfil):
    usuario = criar_usuario(perfil)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "auth", "token": criar_token(usuario)})
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": "frota"})
        assert ws.receive_json() == {"tipo": "recusado", "canal": "frota"}


def test_canal_fora_do_escopo_e_recusado(client, db, mundo, criar_usuario):
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    intrusos = [
        criar_usuario(Perfil.MOTORISTA),  # motorista de outra viagem
        criar_usuario(Perfil.MONITOR),  # monitor não escalado
        criar_usuario(Perfil.RESPONSAVEL),  # responsável sem filho na viagem
    ]
    for usuario in intrusos:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"tipo": "auth", "token": criar_token(usuario)})
            ws.receive_json()
            ws.send_json({"tipo": "inscrever", "canal": canal})
            assert ws.receive_json() == {"tipo": "recusado", "canal": canal}


@pytest.mark.parametrize(
    "canal", ["viagem:999999", "viagem:abc", "viagem:", "frotaX", "../x", "viagem:1:2", ""]
)
def test_canais_malformados_ou_inexistentes_sao_recusados(client, mundo, criar_usuario, canal):
    gestor = criar_usuario(Perfil.GESTOR)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "auth", "token": criar_token(gestor)})
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": canal})
        assert ws.receive_json()["tipo"] == "recusado"


def test_equipe_escalada_assina_a_propria_viagem(client, mundo):
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    with _abrir(client, mundo["motorista"]) as ws:
        assert ws.receive_json()["tipo"] == "autenticado"
        ws.send_json({"tipo": "inscrever", "canal": canal})
        assert ws.receive_json()["tipo"] == "inscrito"


def test_mensagem_desconhecida_recebe_erro(client, mundo, criar_usuario):
    with _abrir(client, criar_usuario(Perfil.GESTOR)) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "qualquer"})
        assert ws.receive_json()["tipo"] == "erro"


# Responsável


def test_responsavel_recebe_a_posicao_e_so_o_proprio_filho(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    with _abrir(client, mae) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": canal})
        assert ws.receive_json()["tipo"] == "inscrito"

        _evento(client, mundo, "embarque", mundo["beto"], 5)  # filho de outra família: não chega
        _evento(client, mundo, "embarque", mundo["ana"], 6)
        msg = _receber_ate(ws, "aluno")
        assert msg["estudante_id"] == mundo["ana"].id
        assert msg["status"] == "embarcou"

        _posicao(client, mundo, 0.004, 20)
        pos = _receber_ate(ws, "posicao")
        assert pos["latitude"] == 0.004


def test_responsavel_nao_recebe_alertas_da_viagem(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    intruso = estudante_de_teste(db, "Intruso", escola_id=mundo["ana"].escola_id)
    with _abrir(client, mae) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": canal})
        ws.receive_json()
        client.post(
            f"/viagens/{mundo['viagem']['id']}/eventos",
            json={
                "eventos": [
                    {
                        "id": str(uuid.uuid4()),
                        "tipo": "embarque_fora_da_lista",
                        "estudante_id": intruso.id,
                        "hora_aparelho": _t(5),
                        "justificativa": "Carona autorizada",
                    }
                ]
            },
            headers=mundo["hm"],
        )
        _posicao(client, mundo, 0.004, 20)
        vistos = []
        for _ in range(2):
            vistos.append(ws.receive_json()["tipo"])
            break
        assert vistos == ["posicao"]


def test_responsavel_perde_o_canal_quando_o_filho_desembarca(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    with _abrir(client, mae) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": canal})
        ws.receive_json()
        _evento(client, mundo, "embarque", mundo["ana"], 5)
        _receber_ate(ws, "aluno")
        _evento(client, mundo, "desembarque", mundo["ana"], 30)
        final = _receber_ate(ws, "aluno")
        assert final["status"] == "desembarcou"

        # A partir daqui o ônibus passa a ter outras crianças: nada de posição para essa família.
        _posicao(client, mundo, 0.02, 40)
        encerrado = _receber_ate(ws, "canal_encerrado")
        assert encerrado["canal"] == canal
        _posicao(client, mundo, 0.021, 50)
        ws.send_json({"tipo": "inscrever", "canal": canal})
        assert ws.receive_json() == {"tipo": "recusado", "canal": canal}


def test_responsavel_nao_assina_antes_da_viagem_comecar(client, db, mundo, criar_usuario):
    mae = _mae(db, criar_usuario, mundo["ana"])
    with _abrir(client, mae) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": f"viagem:{mundo['viagem']['id']}"})
        assert ws.receive_json()["tipo"] == "recusado"


def test_repasse_pelo_redis_chega_a_varias_conexoes(client, mundo, criar_usuario):
    _iniciar(client, mundo)
    gestor_a, gestor_b = criar_usuario(Perfil.GESTOR), criar_usuario(Perfil.ADMIN)
    with _abrir(client, gestor_a) as a, _abrir(client, gestor_b) as b:
        for ws in (a, b):
            ws.receive_json()
            ws.send_json({"tipo": "inscrever", "canal": "frota"})
            ws.receive_json()
        _posicao(client, mundo, 0.004, 10)
        assert _receber_ate(a, "posicao")["latitude"] == 0.004
        assert _receber_ate(b, "posicao")["latitude"] == 0.004


def test_cancelar_inscricao_para_de_receber(client, mundo, criar_usuario):
    _iniciar(client, mundo)
    with _abrir(client, criar_usuario(Perfil.GESTOR)) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": "frota"})
        ws.receive_json()
        ws.send_json({"tipo": "cancelar", "canal": "frota"})
        assert ws.receive_json() == {"tipo": "cancelado", "canal": "frota"}
        ws.send_json({"tipo": "qualquer"})
        _posicao(client, mundo, 0.004, 10)
        assert ws.receive_json()["tipo"] == "erro"


def test_mensagem_so_sai_depois_do_commit(client, db, mundo, criar_usuario, monkeypatch):
    """Se a requisição falhar e der rollback, o canal não recebe nada."""
    from app import tempo_real

    publicadas = []
    monkeypatch.setattr(tempo_real, "publicar", lambda canal, msg: publicadas.append(canal))
    db.execute(text("SELECT 1"))  # abre a transação, como qualquer requisição
    tempo_real.enfileirar(db, 1, {"tipo": "posicao"})
    db.rollback()
    db.commit()
    assert publicadas == []
    db.execute(text("SELECT 1"))
    tempo_real.enfileirar(db, 1, {"tipo": "posicao"})
    db.commit()
    assert tempo_real.CANAL_FROTA in publicadas


def test_conta_desativada_depois_de_conectar_perde_a_conexao(client, db, mundo, criar_usuario):
    _iniciar(client, mundo)
    gestor = criar_usuario(Perfil.GESTOR)
    with _abrir(client, gestor) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": "frota"})
        ws.receive_json()
        gestor.ativo = False
        db.flush()
        _posicao(client, mundo, 0.004, 10)
        with pytest.raises(WebSocketDisconnect) as erro:
            ws.receive_json()
        assert erro.value.code == 4401


def test_motorista_trocado_na_escala_deixa_de_receber(client, db, mundo, criar_usuario):
    _iniciar(client, mundo)
    canal = f"viagem:{mundo['viagem']['id']}"
    with _abrir(client, mundo["motorista"]) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "inscrever", "canal": canal})
        assert ws.receive_json()["tipo"] == "inscrito"
        viagem = db.get(Viagem, mundo["viagem"]["id"])
        viagem.motorista_id = None
        db.flush()
        client.post(
            f"/viagens/{mundo['viagem']['id']}/eventos",
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
            headers=mundo["gestor"],
        )
        assert _receber_ate(ws, "canal_encerrado")["canal"] == canal
