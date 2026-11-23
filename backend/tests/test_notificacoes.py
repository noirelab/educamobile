"""Dispositivos, caixa de notificações, textos, envio com nova tentativa e adaptador do FCM."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app import notificacoes
from app.config import settings
from app.models import (
    Dispositivo,
    Inscricao,
    Motorista,
    Notificacao,
    Perfil,
    ResponsavelEstudante,
    Sentido,
    Turno,
    Veiculo,
)
from app.notificacoes import EnviadorFcm, Resultado, enviar_pendentes
from app.security import criar_token
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste
from tests.test_rotas import _parada

HOJE = date.today()
AGORA = datetime.now(UTC)
TOKEN = "t" * 40


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _t(segundos):
    return (AGORA - timedelta(minutes=8) + timedelta(seconds=segundos)).isoformat()


# Dispositivos


def test_registra_e_remove_o_token(client, db, criar_usuario):
    usuario = criar_usuario(Perfil.RESPONSAVEL)
    h = _h(usuario)
    corpo = {"token": TOKEN, "plataforma": "android"}
    assert client.post("/dispositivos", json=corpo, headers=h).status_code == 204
    assert client.post("/dispositivos", json=corpo, headers=h).status_code == 204  # idempotente
    assert len(db.scalars(select(Dispositivo)).all()) == 1
    assert client.request("DELETE", "/dispositivos", json=corpo, headers=h).status_code == 204
    assert db.scalars(select(Dispositivo)).all() == []


def test_aparelho_que_troca_de_dono_deixa_de_receber_do_dono_antigo(client, db, criar_usuario):
    antigo, novo = criar_usuario(Perfil.RESPONSAVEL), criar_usuario(Perfil.RESPONSAVEL)
    corpo = {"token": TOKEN, "plataforma": "ios"}
    client.post("/dispositivos", json=corpo, headers=_h(antigo))
    client.post("/dispositivos", json=corpo, headers=_h(novo))
    assert db.scalar(select(Dispositivo.usuario_id)) == novo.id
    # O dono antigo não consegue apagar o token que já é de outro.
    client.request("DELETE", "/dispositivos", json=corpo, headers=_h(antigo))
    assert len(db.scalars(select(Dispositivo)).all()) == 1


@pytest.mark.parametrize(
    "corpo",
    [
        {"token": "curto", "plataforma": "android"},
        {"token": TOKEN, "plataforma": "windows-phone"},
        {"token": "a b" * 20, "plataforma": "android"},
        {"token": "x" * 501, "plataforma": "android"},
        {"plataforma": "android"},
    ],
)
def test_token_invalido_da_422(client, criar_usuario, corpo):
    assert client.post("/dispositivos", json=corpo, headers=_h(criar_usuario())).status_code == 422


def test_limite_de_dispositivos_por_conta(client, db, criar_usuario):
    h = _h(criar_usuario(Perfil.RESPONSAVEL))
    for i in range(12):
        client.post(
            "/dispositivos",
            json={"token": f"{i:02d}" + "z" * 40, "plataforma": "android"},
            headers=h,
        )
    tokens = db.scalars(select(Dispositivo.token).order_by(Dispositivo.id)).all()
    assert len(tokens) == 10
    assert tokens[-1].startswith("11")
    assert not any(t.startswith("00") for t in tokens)


def test_dispositivos_exigem_login(client):
    assert (
        client.post("/dispositivos", json={"token": TOKEN, "plataforma": "android"}).status_code
        == 401
    )
    assert client.get("/notificacoes").status_code == 401


# Caixa de notificações


def test_cada_um_le_so_as_proprias_e_marca_como_lida(client, db, criar_usuario):
    a, b = criar_usuario(Perfil.RESPONSAVEL), criar_usuario(Perfil.RESPONSAVEL)
    n1 = notificacoes.criar(db, a.id, "x", "Título", "Mensagem de A")
    n2 = notificacoes.criar(db, b.id, "x", "Título", "Mensagem de B")
    db.flush()
    lista = client.get("/notificacoes", headers=_h(a)).json()
    assert [n["mensagem"] for n in lista] == ["Mensagem de A"]
    assert client.post(f"/notificacoes/{n2.id}/lida", headers=_h(a)).status_code == 404
    assert client.post("/notificacoes/999999/lida", headers=_h(a)).status_code == 404
    assert client.post(f"/notificacoes/{n1.id}/lida", headers=_h(a)).status_code == 204
    assert client.get("/notificacoes?nao_lidas=true", headers=_h(a)).json() == []
    assert client.get("/notificacoes", headers=_h(a)).json()[0]["lido_em"] is not None
    assert db.get(Notificacao, n2.id).lido_em is None


# Gatilhos e textos


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
    ana = estudante_de_teste(db, "Ana Souza", escola_id=escola.id)
    beto = estudante_de_teste(db, "Beto Lima", escola_id=escola.id)
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
    maes = {}
    for filho in (ana, beto):
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
        maes[filho.id] = mae
    db.flush()
    viagem = client.post("/viagens/gerar", json={"rota_id": rota.id}, headers=gestor).json()[0]
    return {
        "viagem": viagem,
        "hm": _h(motorista),
        "ana": ana,
        "beto": beto,
        "maes": maes,
        "gestor": gestor,
    }


def _caixa(client, mae):
    return client.get("/notificacoes", headers=_h(mae)).json()


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


def test_ciclo_completo_de_avisos_so_do_proprio_filho(client, db, mundo):
    mae_ana, mae_beto = mundo["maes"][mundo["ana"].id], mundo["maes"][mundo["beto"].id]
    client.post(f"/viagens/{mundo['viagem']['id']}/iniciar", headers=mundo["hm"])
    _evento(client, mundo, "embarque", mundo["ana"], 1)
    _evento(client, mundo, "nao_embarcou", mundo["beto"], 2)
    _evento(client, mundo, "desembarque", mundo["ana"], 30)

    da_ana = _caixa(client, mae_ana)
    assert sorted(n["tipo"] for n in da_ana) == ["desembarcou", "embarcou", "onibus_saiu"]
    chegada = next(n for n in da_ana if n["tipo"] == "desembarcou")
    assert chegada["titulo"] == "Chegou à escola"
    assert chegada["mensagem"] == "Ana chegou à escola."

    do_beto = _caixa(client, mae_beto)
    assert sorted(n["tipo"] for n in do_beto) == ["nao_embarcou", "onibus_saiu"]
    texto = json.dumps(da_ana + do_beto, ensure_ascii=False)
    assert "Souza" not in texto and "Lima" not in texto
    for n in da_ana:
        assert "Beto" not in n["mensagem"]
    for n in do_beto:
        assert "Ana" not in n["mensagem"]


def test_onibus_chegando_avisa_quem_espera_na_parada(client, db, mundo):
    client.post(f"/viagens/{mundo['viagem']['id']}/iniciar", headers=mundo["hm"])
    client.post(
        f"/viagens/{mundo['viagem']['id']}/posicoes",
        json={"posicoes": [{"registrada_em": _t(0), "latitude": 0.0099, "longitude": 0.0}]},
        headers=mundo["hm"],
    )
    for filho in (mundo["ana"], mundo["beto"]):
        tipos = [n["tipo"] for n in _caixa(client, mundo["maes"][filho.id])]
        assert "onibus_chegando" in tipos


def test_quem_ja_embarcou_nao_recebe_onibus_chegando(client, db, mundo):
    client.post(f"/viagens/{mundo['viagem']['id']}/iniciar", headers=mundo["hm"])
    _evento(client, mundo, "embarque", mundo["ana"], 1)
    client.post(
        f"/viagens/{mundo['viagem']['id']}/posicoes",
        json={"posicoes": [{"registrada_em": _t(5), "latitude": 0.0099, "longitude": 0.0}]},
        headers=mundo["hm"],
    )
    tipos = [n["tipo"] for n in _caixa(client, mundo["maes"][mundo["ana"].id])]
    assert "onibus_chegando" not in tipos


def test_responsavel_sem_consentimento_nao_recebe_nada(client, db, mundo):
    vinculo = db.scalar(
        select(ResponsavelEstudante).where(ResponsavelEstudante.estudante_id == mundo["ana"].id)
    )
    vinculo.consentimento_em = None
    db.flush()
    client.post(f"/viagens/{mundo['viagem']['id']}/iniciar", headers=mundo["hm"])
    assert _caixa(client, mundo["maes"][mundo["ana"].id]) == []


# Envio


class Enviador:
    def __init__(self, *resultados):
        self.resultados = list(resultados)
        self.enviadas = []

    def enviar(self, token, titulo, corpo, dados):
        self.enviadas.append((token, titulo, corpo, dados))
        return self.resultados.pop(0) if self.resultados else Resultado.ENVIADO


def _pendente(db, usuario, *tokens):
    for t in tokens:
        db.add(Dispositivo(usuario_id=usuario.id, token=t, plataforma="android"))
    n = notificacoes.criar(db, usuario.id, "teste", "Título", "Corpo")
    db.flush()
    return n


def test_envia_e_marca_como_enviada(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN)
    enviador = Enviador()
    assert enviar_pendentes(db, enviador, AGORA) == 1
    assert n.enviada_em is not None and n.erro is None
    token, titulo, corpo, dados = enviador.enviadas[0]
    assert (token, titulo, corpo) == (TOKEN, "Título", "Corpo")
    assert dados == {"notificacao_id": str(n.id), "tipo": "teste"}
    assert enviar_pendentes(db, enviador, AGORA) == 0


def test_falha_temporaria_tenta_de_novo_com_espera_crescente(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN)
    enviador = Enviador(Resultado.ERRO_TEMPORARIO, Resultado.ERRO_TEMPORARIO, Resultado.ENVIADO)

    enviar_pendentes(db, enviador, AGORA)
    assert (n.tentativas, n.enviada_em) == (1, None)
    primeira_espera = n.proxima_tentativa_em - AGORA
    assert enviar_pendentes(db, enviador, AGORA) == 0  # ainda no período de espera
    assert len(enviador.enviadas) == 1

    depois = n.proxima_tentativa_em + timedelta(seconds=1)
    enviar_pendentes(db, enviador, depois)
    assert n.tentativas == 2
    assert n.proxima_tentativa_em - depois > primeira_espera

    assert enviar_pendentes(db, enviador, n.proxima_tentativa_em + timedelta(seconds=1)) == 1
    assert n.enviada_em is not None


def test_desiste_depois_do_maximo_de_tentativas(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN)
    enviador = Enviador(*[Resultado.ERRO_TEMPORARIO] * 20)
    agora = AGORA
    for _ in range(notificacoes.MAX_TENTATIVAS + 3):
        agora = (n.proxima_tentativa_em or agora) + timedelta(seconds=1)
        enviar_pendentes(db, enviador, agora)
    assert n.tentativas == notificacoes.MAX_TENTATIVAS
    assert len(enviador.enviadas) == notificacoes.MAX_TENTATIVAS
    assert n.enviada_em is None  # continua na caixa de notificações da API


def test_token_recusado_pelo_fcm_e_removido(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN, "u" * 40)
    enviar_pendentes(db, Enviador(Resultado.TOKEN_INVALIDO, Resultado.ENVIADO), AGORA)
    assert [d.token for d in db.scalars(select(Dispositivo))] == ["u" * 40]
    assert n.enviada_em is not None


def test_so_tokens_invalidos_nao_fica_tentando_para_sempre(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN)
    enviar_pendentes(db, Enviador(Resultado.TOKEN_INVALIDO), AGORA)
    assert db.scalars(select(Dispositivo)).all() == []
    assert (n.erro, n.enviada_em is not None) == ("tokens_invalidos", True)


def test_sem_dispositivo_fica_so_na_caixa(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae)
    enviador = Enviador()
    enviar_pendentes(db, enviador, AGORA)
    assert enviador.enviadas == []
    assert (n.erro, n.enviada_em is not None) == ("sem_dispositivo", True)


def test_varios_aparelhos_basta_um_chegar(db, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    n = _pendente(db, mae, TOKEN, "v" * 40)
    enviador = Enviador(Resultado.ERRO_TEMPORARIO, Resultado.ENVIADO)
    assert enviar_pendentes(db, enviador, AGORA) == 1
    assert len(enviador.enviadas) == 2
    assert n.enviada_em is not None


# Adaptador do Firebase


def _fcm(handler):
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return EnviadorFcm("meu-projeto", lambda: "token-oauth", cliente)


def test_fcm_monta_a_requisicao_da_api_v1():
    vistos = []

    def handler(request):
        vistos.append(request)
        return httpx.Response(200, json={"name": "projects/meu-projeto/messages/1"})

    r = _fcm(handler).enviar("tok", "Título", "Corpo", {"a": "1"})
    assert r is Resultado.ENVIADO
    [req] = vistos
    assert str(req.url) == "https://fcm.googleapis.com/v1/projects/meu-projeto/messages:send"
    assert req.headers["authorization"] == "Bearer token-oauth"
    corpo = json.loads(req.content)["message"]
    assert corpo["token"] == "tok"
    assert corpo["notification"] == {"title": "Título", "body": "Corpo"}
    assert corpo["data"] == {"a": "1"}


@pytest.mark.parametrize(
    ("status", "corpo", "esperado"),
    [
        (
            404,
            {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}},
            Resultado.TOKEN_INVALIDO,
        ),
        (404, {"error": {"status": "NOT_FOUND"}}, Resultado.TOKEN_INVALIDO),
        (
            400,
            {
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "message": "The registration token is not valid",
                }
            },
            Resultado.TOKEN_INVALIDO,
        ),
        (
            400,
            {"error": {"status": "INVALID_ARGUMENT", "message": "Invalid JSON payload"}},
            Resultado.ERRO_TEMPORARIO,
        ),
        (401, {"error": {"status": "UNAUTHENTICATED"}}, Resultado.ERRO_TEMPORARIO),
        (429, {"error": {"status": "RESOURCE_EXHAUSTED"}}, Resultado.ERRO_TEMPORARIO),
        (503, {"error": {"status": "UNAVAILABLE"}}, Resultado.ERRO_TEMPORARIO),
    ],
)
def test_fcm_classifica_as_respostas(status, corpo, esperado):
    assert _fcm(lambda r: httpx.Response(status, json=corpo)).enviar("t", "a", "b", {}) is esperado


def test_fcm_sem_rede_e_erro_temporario():
    def cai(request):
        raise httpx.ConnectError("sem rede")

    assert _fcm(cai).enviar("t", "a", "b", {}) is Resultado.ERRO_TEMPORARIO


def test_sem_credenciais_o_enviador_so_registra_em_log(monkeypatch):
    monkeypatch.setattr(settings, "fcm_credenciais", None)
    assert isinstance(notificacoes.obter_enviador(), notificacoes.EnviadorDeRegistro)
