"""Limites: implementação em Redis compartilhada entre processos e limite geral da API."""

import os
import subprocess
import sys
import time
import uuid

import pytest
import redis

from app import limite as modulo
from app import tempo_real
from app.config import Settings, settings
from app.limite import LimiteEmMemoria, LimiteRedis, criar_limite
from app.models import Perfil
from app.security import criar_token

SEGREDO = "um-segredo-bem-comprido-e-variado-para-os-testes-0123456789"


@pytest.fixture
def prefixo():
    return f"teste-{uuid.uuid4().hex[:8]}"


def test_bloqueia_ao_atingir_o_maximo_e_limpa(prefixo):
    lim = LimiteRedis(3, 60, prefixo)
    for _ in range(2):
        lim.registrar_falha("a")
    assert not lim.bloqueado("a")
    lim.registrar_falha("a")
    assert lim.bloqueado("a")
    assert not lim.bloqueado("outra")
    lim.limpar("a")
    assert not lim.bloqueado("a")


def test_a_janela_desliza(prefixo):
    lim = LimiteRedis(2, 1, prefixo)
    lim.registrar_falha("a")
    lim.registrar_falha("a")
    assert lim.bloqueado("a")
    time.sleep(1.2)
    assert not lim.bloqueado("a")


def test_a_chave_expira_sozinha_no_redis(prefixo):
    lim = LimiteRedis(5, 30, prefixo)
    lim.registrar_falha("a")
    ttl = tempo_real.cliente().ttl(f"limite:{prefixo}:a")
    assert 0 < ttl <= 31


def test_so_guarda_as_ultimas_tentativas(prefixo):
    lim = LimiteRedis(3, 60, prefixo)
    for _ in range(50):
        lim.registrar_falha("a")
    assert tempo_real.cliente().zcard(f"limite:{prefixo}:a") == 3


def test_dois_processos_simulados_dividem_o_mesmo_limite(prefixo):
    """Dois objetos independentes (como dois workers da API) enxergam a mesma contagem."""
    a, b = LimiteRedis(4, 60, prefixo), LimiteRedis(4, 60, prefixo)
    a.registrar_falha("ip")
    a.registrar_falha("ip")
    b.registrar_falha("ip")
    assert not a.bloqueado("ip")
    b.registrar_falha("ip")
    assert a.bloqueado("ip") and b.bloqueado("ip")


def test_dois_processos_de_verdade_dividem_o_mesmo_limite(prefixo):
    codigo = (
        "from app.limite import LimiteRedis\n"
        f"l = LimiteRedis(4, 60, {prefixo!r})\n"
        "[l.registrar_falha('ip') for _ in range(2)]\n"
    )
    env = {**os.environ, "JWT_SECRET": SEGREDO}
    for _ in range(2):
        subprocess.run([sys.executable, "-c", codigo], check=True, env=env, cwd=os.getcwd())
    # Nenhum dos dois processos chegou ao máximo sozinho; juntos, sim.
    assert LimiteRedis(4, 60, prefixo).bloqueado("ip")


def test_a_implementacao_vem_da_configuracao(monkeypatch):
    monkeypatch.setattr(settings, "limite_backend", "memoria")
    assert isinstance(criar_limite("x", 1, 1), LimiteEmMemoria)
    monkeypatch.setattr(settings, "limite_backend", "redis")
    assert isinstance(criar_limite("x", 1, 1), LimiteRedis)


def test_producao_exige_limite_no_redis():
    base = {
        "database_url": "postgresql+psycopg://u:p@h/d",
        "jwt_secret": SEGREDO,
        "ambiente": "producao",
        "cors_origins": ["https://app.exemplo.com"],
    }
    with pytest.raises(ValueError, match="LIMITE_BACKEND"):
        Settings(**base, limite_backend="memoria", _env_file=None)
    assert Settings(**base, limite_backend="redis", _env_file=None).limite_backend == "redis"


# Limite geral


def _gestor_h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def test_escritas_acima_do_limite_recebem_429(client, criar_usuario, monkeypatch):
    monkeypatch.setattr(modulo, "limite_escrita", LimiteEmMemoria(3, 60))
    h = _gestor_h(criar_usuario(Perfil.GESTOR))
    outro = _gestor_h(criar_usuario(Perfil.GESTOR))
    veiculo = {
        "placa": "AAA1A11",
        "capacidade": 40,
        "modelo": "V",
        "ano": 2020,
        "vistoria_valida_ate": "2030-01-01",
    }
    codigos = [
        client.post("/veiculos", json={**veiculo, "placa": f"AAA1A{i}1"}, headers=h).status_code
        for i in range(5)
    ]
    assert codigos == [201, 201, 201, 429, 429]
    limitado = client.post("/veiculos", json=veiculo, headers=h)
    assert limitado.headers["Retry-After"] == "60"
    # Leituras não contam e outra pessoa tem a própria cota.
    assert client.get("/veiculos", headers=h).status_code == 200
    assert (
        client.post("/veiculos", json={**veiculo, "placa": "BBB2B22"}, headers=outro).status_code
        == 201
    )


def test_sem_token_o_limite_vale_por_ip(client, monkeypatch):
    monkeypatch.setattr(modulo, "limite_escrita", LimiteEmMemoria(2, 60))
    codigos = [
        client.post(
            "/auth/login", data={"username": "x@y.com", "password": "senha-qualquer"}
        ).status_code
        for _ in range(4)
    ]
    assert codigos[:2] == [401, 401]
    assert codigos[2:] == [429, 429]


def test_posicoes_tem_limite_proprio(client, criar_usuario, monkeypatch):
    monkeypatch.setattr(modulo, "limite_posicoes", LimiteEmMemoria(2, 60))
    h = _gestor_h(criar_usuario(Perfil.MOTORISTA))
    corpo = {
        "posicoes": [{"registrada_em": "2026-11-23T07:00:00-03:00", "latitude": 0, "longitude": 0}]
    }
    codigos = [
        client.post("/viagens/1/posicoes", json=corpo, headers=h).status_code for _ in range(4)
    ]
    assert codigos[:2] == [404, 404]  # passou pelo limite e parou na viagem inexistente
    assert codigos[2:] == [429, 429]
    # O limite de posições não consome a cota de escrita geral e vice-versa.
    assert client.get("/auth/me", headers=h).status_code == 200


def test_redis_fora_do_ar_nao_derruba_a_api(client, criar_usuario, monkeypatch):
    def quebrado():
        raise redis.ConnectionError("fora do ar")

    monkeypatch.setattr(modulo, "limite_escrita", LimiteRedis(1, 60, "x"))
    monkeypatch.setattr(tempo_real, "cliente", quebrado)
    h = _gestor_h(criar_usuario(Perfil.GESTOR))
    veiculo = {
        "placa": "AAA1A11",
        "capacidade": 40,
        "modelo": "V",
        "ano": 2020,
        "vistoria_valida_ate": "2030-01-01",
    }
    assert client.post("/veiculos", json=veiculo, headers=h).status_code == 201


def test_variar_o_cabecalho_de_autorizacao_nao_escapa_do_limite_por_ip(client, monkeypatch):
    monkeypatch.setattr(modulo, "limite_ip", LimiteEmMemoria(3, 60))
    codigos = [
        client.post(
            "/auth/logout",
            json={"refresh_token": "x" * 30},
            headers={"Authorization": f"Bearer {i}"},
        ).status_code
        for i in range(6)
    ]
    assert codigos[:3] == [204, 204, 204]
    assert codigos[3:] == [429, 429, 429]


def test_limite_no_redis_fora_do_ar_nao_derruba_o_login(monkeypatch, prefixo):
    def quebrado():
        raise redis.ConnectionError("fora do ar")

    lim = LimiteRedis(1, 60, prefixo)
    monkeypatch.setattr(tempo_real, "cliente", quebrado)
    lim.registrar_falha("a")
    lim.registrar_falha("a")
    assert lim.bloqueado("a") is False
    lim.limpar("a")
