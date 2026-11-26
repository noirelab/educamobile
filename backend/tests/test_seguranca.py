"""Sessões, controle de acesso por perfil e vínculo, auditoria e cabeçalhos."""

import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app import auditoria
from app.config import Settings, settings
from app.geo import Coordenadas, para_ponto
from app.main import app, criar_app
from app.models import Auditoria, Parada, Perfil, Sessao, Usuario
from app.security import ALGORITMO, criar_token
from tests.conftest import corpo_de_rota, estudante_de_teste

SENHA = "senha-forte-1"
SEGREDO_FORTE = "Gq7-pX2_vL9wRt4ZkM8nB3cYh6JdF1sA"


def _login(client, usuario, senha=SENHA, **kw):
    return client.post("/auth/login", data={"username": usuario.email, "password": senha}, **kw)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _me(client, token):
    return client.get("/auth/me", headers=_bearer(token))


# Sessões e tokens


def test_login_devolve_refresh_token_e_validade_curta(client, criar_usuario):
    corpo = _login(client, criar_usuario()).json()
    assert corpo["expires_in"] == settings.jwt_expire_minutes * 60
    assert len(corpo["refresh_token"]) >= 40
    payload = jwt.decode(corpo["access_token"], settings.jwt_secret, algorithms=[ALGORITMO])
    assert payload["typ"] == "access" and payload["jti"]


def test_refresh_token_guardado_so_como_hash(client, db, criar_usuario):
    usuario = criar_usuario()
    refresh = _login(client, usuario).json()["refresh_token"]
    hashes = db.scalars(select(Sessao.token_hash).where(Sessao.usuario_id == usuario.id)).all()
    assert hashes and refresh not in hashes


def test_refresh_troca_o_token_a_cada_uso(client, criar_usuario):
    r1 = _login(client, criar_usuario()).json()["refresh_token"]
    resposta = client.post("/auth/refresh", json={"refresh_token": r1})
    assert resposta.status_code == 200
    novo = resposta.json()
    assert novo["refresh_token"] != r1
    assert _me(client, novo["access_token"]).status_code == 200


def test_reuso_de_refresh_token_derruba_todas_as_sessoes(client, criar_usuario):
    r1 = _login(client, criar_usuario()).json()["refresh_token"]
    segundo = client.post("/auth/refresh", json={"refresh_token": r1}).json()

    # Alguém guardou uma cópia de r1 e tenta usá-la.
    assert client.post("/auth/refresh", json={"refresh_token": r1}).status_code == 401

    assert client.post("/auth/refresh", json=segundo).status_code == 401
    assert _me(client, segundo["access_token"]).status_code == 401


def test_refresh_desconhecido_expirado_ou_de_conta_desativada(client, db, criar_usuario):
    assert client.post("/auth/refresh", json={"refresh_token": "x" * 43}).status_code == 401

    usuario = criar_usuario()
    refresh = _login(client, usuario).json()["refresh_token"]
    sessao = db.scalar(select(Sessao).where(Sessao.usuario_id == usuario.id))
    sessao.expira_em = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401

    outro = criar_usuario()
    refresh = _login(client, outro).json()["refresh_token"]
    outro.ativo = False
    db.flush()
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_logout_encerra_so_a_sessao_do_aparelho(client, criar_usuario):
    usuario = criar_usuario()
    celular = _login(client, usuario).json()
    computador = _login(client, usuario).json()

    resposta = client.post("/auth/logout", json={"refresh_token": celular["refresh_token"]})
    assert resposta.status_code == 204
    assert client.post("/auth/refresh", json=celular).status_code == 401
    assert client.post("/auth/refresh", json=computador).status_code == 200
    # Token desconhecido: mesma resposta, para não confirmar quais tokens existem.
    assert client.post("/auth/logout", json={"refresh_token": "y" * 43}).status_code == 204


def test_logout_todos_invalida_acesso_e_refresh(client, criar_usuario):
    usuario = criar_usuario()
    celular = _login(client, usuario).json()
    computador = _login(client, usuario).json()

    h = _bearer(computador["access_token"])
    assert client.post("/auth/logout-todos", headers=h).status_code == 204
    assert _me(client, computador["access_token"]).status_code == 401
    assert client.post("/auth/refresh", json=celular).status_code == 401
    assert _login(client, usuario).status_code == 200


def test_troca_de_senha_derruba_sessoes_antigas(client, criar_usuario):
    usuario = criar_usuario()
    antigo = _login(client, usuario).json()
    h = _bearer(antigo["access_token"])

    errada = {"senha_atual": "nao-e-essa-1", "senha_nova": "outra-senha-forte-2"}
    assert client.put("/auth/senha", json=errada, headers=h).status_code == 403

    certa = {"senha_atual": SENHA, "senha_nova": "outra-senha-forte-2"}
    assert client.put("/auth/senha", json=certa, headers=h).status_code == 204
    assert _me(client, antigo["access_token"]).status_code == 401
    assert client.post("/auth/refresh", json=antigo).status_code == 401
    assert _login(client, usuario).status_code == 401
    assert _login(client, usuario, "outra-senha-forte-2").status_code == 200


def test_troca_de_senha_bloqueia_tentativas_repetidas(client, criar_usuario):
    h = _bearer(_login(client, criar_usuario()).json()["access_token"])
    errada = {"senha_atual": "nao-e-essa-1", "senha_nova": "outra-senha-forte-2"}
    for _ in range(5):
        assert client.put("/auth/senha", json=errada, headers=h).status_code == 403
    certa = {"senha_atual": SENHA, "senha_nova": "outra-senha-forte-2"}
    assert client.put("/auth/senha", json=certa, headers=h).status_code == 429


def test_senha_nova_igual_a_atual_rejeitada(client, criar_usuario):
    h = _bearer(_login(client, criar_usuario()).json()["access_token"])
    igual = {"senha_atual": SENHA, "senha_nova": SENHA}
    assert client.put("/auth/senha", json=igual, headers=h).status_code == 422


def test_token_sem_tipo_ou_de_outro_tipo_rejeitado(client, criar_usuario):
    usuario = criar_usuario()
    agora = datetime.now(UTC)
    base = {"sub": str(usuario.id), "iat": agora.timestamp(), "exp": agora + timedelta(minutes=5)}
    sem_tipo = jwt.encode(base, settings.jwt_secret, algorithm=ALGORITMO)
    outro_tipo = jwt.encode({**base, "typ": "refresh"}, settings.jwt_secret, algorithm=ALGORITMO)
    for token in (sem_tipo, outro_tipo):
        assert _me(client, token).status_code == 401


def test_validade_do_token_nao_passa_de_uma_hora():
    with pytest.raises(ValidationError):
        Settings(database_url="x", jwt_secret=SEGREDO_FORTE, jwt_expire_minutes=600)


# Perfis novos: nada das rotas de cadastro sem liberação explícita

# Rotas que todo usuário logado usa, independentemente do perfil.
_ROTAS_DE_CONTA = {
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/convites/aceitar"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/logout-todos"),
    ("PUT", "/auth/senha"),
    ("GET", "/auth/me"),
    ("GET", "/auth/sessoes"),
    ("DELETE", "/auth/sessoes/{sessao_id}"),
    ("GET", "/health"),
    ("POST", "/dispositivos"),
    ("DELETE", "/dispositivos"),
    ("GET", "/notificacoes"),
    ("POST", "/notificacoes/{notificacao_id}/lida"),
    ("GET", "/fotos/{token}"),
    # Autentica por token de veículo no cabeçalho, não por usuário.
    ("POST", "/rastreador/posicoes"),
}


_ROTAS_DA_EQUIPE = {
    ("GET", "/viagens/{viagem_id}"),
    ("POST", "/viagens/{viagem_id}/iniciar"),
    ("GET", "/viagens/{viagem_id}/lista"),
    ("POST", "/viagens/{viagem_id}/eventos"),
    ("POST", "/viagens/{viagem_id}/concluir"),
    ("GET", "/viagens/{viagem_id}/posicao"),
    ("GET", "/viagens/{viagem_id}/percurso"),
    ("POST", "/viagens/{viagem_id}/posicoes"),
    ("POST", "/viagens/{viagem_id}/emergencia"),
}


def _rotas_da_api():
    # O schema OpenAPI lista todas as operações dos routers incluídos.
    for caminho, operacoes in app.openapi()["paths"].items():
        for metodo in operacoes:
            yield metodo.upper(), caminho


@pytest.mark.parametrize(
    "perfil", [Perfil.RESPONSAVEL, Perfil.MOTORISTA, Perfil.MONITOR, Perfil.ESCOLA]
)
def test_perfis_externos_barrados_em_todas_as_rotas_de_cadastro(
    client, db, cabecalhos, criar_escola, perfil
):
    if perfil == Perfil.ESCOLA:
        equipe = Usuario(
            nome="Secretaria",
            email="secretaria@escola.exemplo.com",
            senha_hash="x",
            perfil=Perfil.ESCOLA,
            escola_id=criar_escola().id,
        )
        db.add(equipe)
        db.flush()
        h = {"Authorization": f"Bearer {criar_token(equipe)}"}
    else:
        h = cabecalhos(perfil)
    liberadas = set(_ROTAS_DE_CONTA)
    if perfil == Perfil.ESCOLA:
        # Viagem de outra escola some (404), como para a equipe do ônibus.
        liberadas |= {("GET", "/escola/chegadas"), ("POST", "/viagens/{viagem_id}/recebimentos")}
    if perfil == Perfil.RESPONSAVEL:
        liberadas |= {
            (m, p)
            for m, p in _rotas_da_api()
            if p.startswith("/responsavel/") or p.startswith("/ausencias")
        }
    if perfil == Perfil.MOTORISTA:
        liberadas |= {(m, p) for m, p in _rotas_da_api() if p.startswith("/motorista/")}
    if perfil in (Perfil.MOTORISTA, Perfil.MONITOR):
        # Quem não está escalado recebe 404, não 403: a viagem some para ele.
        liberadas |= _ROTAS_DA_EQUIPE | {("GET", "/motorista/viagens-hoje")}

    verificadas = 0
    for metodo, caminho in _rotas_da_api():
        if (metodo, caminho) in liberadas:
            continue
        url = re.sub(r"\{[^}]+\}", "1", caminho)
        resposta = client.request(metodo, url, headers=h)
        assert resposta.status_code == 403, (
            f"{perfil}: {metodo} {caminho} -> {resposta.status_code}"
        )
        verificadas += 1
    assert verificadas > 20


def test_rotas_novas_entram_na_varredura():
    caminhos = {p for _, p in _rotas_da_api()}
    assert "/responsavel/filhos" in caminhos
    assert "/estudantes/{estudante_id}/responsaveis" in caminhos


def test_gestor_opera_o_transporte_mas_nao_cria_usuarios(client, db, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    parada = {"nome": "Parada", "localizacao": {"latitude": -25.4, "longitude": -49.2}}
    assert client.post("/paradas", json=parada, headers=h).status_code == 201
    assert client.post("/rotas", json=corpo_de_rota(db, "Linha G"), headers=h).status_code == 201
    assert client.get("/estudantes", headers=h).status_code == 200
    novo = {"nome": "X", "email": "x@exemplo.com", "senha": SENHA, "perfil": "admin"}
    assert client.post("/usuarios", json=novo, headers=h).status_code == 403


# Vínculo responsável–estudante


@pytest.fixture
def familia(db, criar_usuario):
    parada = Parada(
        nome="Parada da Praça", localizacao=para_ponto(Coordenadas(latitude=-25.4, longitude=-49.2))
    )
    db.add(parada)
    db.flush()
    filho = estudante_de_teste(db, "Bia", parada_id=parada.id)
    outro = estudante_de_teste(db, "Caio")
    return {
        "mae": criar_usuario(Perfil.RESPONSAVEL),
        "estranho": criar_usuario(Perfil.RESPONSAVEL),
        "filho": filho,
        "outro": outro,
        "parada": parada,
    }


def _vincular(client, h, estudante, responsavel, **extra):
    corpo = {"responsavel_id": responsavel.id, "parentesco": "mãe", **extra}
    return client.post(f"/estudantes/{estudante.id}/responsaveis", json=corpo, headers=h)


def test_vinculo_exige_usuario_responsavel_e_nao_duplica(
    client, cabecalhos, criar_usuario, familia
):
    h = cabecalhos(Perfil.GESTOR)
    assert (
        _vincular(client, h, familia["filho"], criar_usuario(Perfil.MOTORISTA)).status_code == 422
    )
    assert _vincular(client, h, familia["filho"], familia["mae"]).status_code == 201
    assert _vincular(client, h, familia["filho"], familia["mae"]).status_code == 409
    lista = client.get(f"/estudantes/{familia['filho'].id}/responsaveis", headers=h).json()
    assert [v["responsavel_id"] for v in lista] == [familia["mae"].id]


def test_so_admin_e_gestor_criam_vinculo(client, cabecalhos, familia):
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR):
        assert (
            _vincular(client, cabecalhos(perfil), familia["filho"], familia["mae"]).status_code
            == 403
        )


def test_responsavel_so_ve_o_filho_depois_do_consentimento(client, cabecalhos, familia):
    _vincular(client, cabecalhos(Perfil.GESTOR), familia["filho"], familia["mae"])
    h = _bearer(criar_token(familia["mae"]))
    filho_id = familia["filho"].id

    filhos = client.get("/responsavel/filhos", headers=h).json()
    assert filhos == [
        {
            "estudante_id": filho_id,
            "nome": "Bia",
            "parentesco": "mãe",
            "consentimento_pendente": True,
        }
    ]
    assert client.get(f"/responsavel/filhos/{filho_id}", headers=h).status_code == 403

    url = f"/responsavel/filhos/{filho_id}/consentimento"
    assert client.post(url, json={"versao_termo": "antiga"}, headers=h).status_code == 422
    aceite = client.post(url, json={"versao_termo": settings.versao_termo_consentimento}, headers=h)
    assert aceite.status_code == 200 and aceite.json()["consentimento_em"]

    detalhe = client.get(f"/responsavel/filhos/{filho_id}", headers=h)
    assert detalhe.status_code == 200
    assert detalhe.json() == {
        "estudante_id": filho_id,
        "nome": "Bia",
        "parada": {"id": familia["parada"].id, "nome": "Parada da Praça"},
        "contato_emergencia": None,
    }


def test_responsavel_nao_ve_filho_de_outra_pessoa(client, cabecalhos, familia):
    _vincular(client, cabecalhos(Perfil.GESTOR), familia["filho"], familia["mae"])
    estranho = _bearer(criar_token(familia["estranho"]))
    mae = _bearer(criar_token(familia["mae"]))
    termo = {"versao_termo": settings.versao_termo_consentimento}

    assert client.get("/responsavel/filhos", headers=estranho).json() == []
    for h, estudante in ((estranho, familia["filho"]), (mae, familia["outro"])):
        assert client.get(f"/responsavel/filhos/{estudante.id}", headers=h).status_code == 404
        url = f"/responsavel/filhos/{estudante.id}/consentimento"
        assert client.post(url, json=termo, headers=h).status_code == 404
    # Inexistente responde igual a sem vínculo.
    assert client.get("/responsavel/filhos/999999", headers=mae).status_code == 404


def test_desvincular_corta_o_acesso(client, cabecalhos, familia):
    gestor = cabecalhos(Perfil.GESTOR)
    _vincular(client, gestor, familia["filho"], familia["mae"])
    mae = _bearer(criar_token(familia["mae"]))
    termo = {"versao_termo": settings.versao_termo_consentimento}
    client.post(f"/responsavel/filhos/{familia['filho'].id}/consentimento", json=termo, headers=mae)

    url = f"/estudantes/{familia['filho'].id}/responsaveis/{familia['mae'].id}"
    assert client.delete(url, headers=gestor).status_code == 204
    assert client.get(f"/responsavel/filhos/{familia['filho'].id}", headers=mae).status_code == 404
    assert client.delete(url, headers=gestor).status_code == 404


# Auditoria


def _acoes(db, usuario_id):
    return db.scalars(
        select(Auditoria.acao).where(Auditoria.usuario_id == usuario_id).order_by(Auditoria.id)
    ).all()


def test_login_e_troca_de_senha_ficam_auditados(client, db, criar_usuario):
    usuario = criar_usuario()
    _login(client, usuario, "errada-123456")
    corpo = _login(client, usuario).json()
    troca = {"senha_atual": SENHA, "senha_nova": "outra-senha-forte-2"}
    client.put("/auth/senha", json=troca, headers=_bearer(corpo["access_token"]))
    assert _acoes(db, usuario.id) == ["login.falha", "login.ok", "senha.troca"]


def test_reuso_de_refresh_fica_auditado(client, db, criar_usuario):
    usuario = criar_usuario()
    r1 = _login(client, usuario).json()["refresh_token"]
    client.post("/auth/refresh", json={"refresh_token": r1})
    client.post("/auth/refresh", json={"refresh_token": r1})
    assert "sessao.reuso" in _acoes(db, usuario.id)


def test_vinculo_e_consentimento_ficam_auditados(client, db, cabecalhos, familia):
    _vincular(client, cabecalhos(Perfil.GESTOR), familia["filho"], familia["mae"])
    termo = {"versao_termo": settings.versao_termo_consentimento}
    url = f"/responsavel/filhos/{familia['filho'].id}/consentimento"
    client.post(url, json=termo, headers=_bearer(criar_token(familia["mae"])))
    acoes = db.scalars(
        select(Auditoria.acao).where(Auditoria.recurso_id == str(familia["filho"].id))
    ).all()
    assert {"vinculo.criar", "consentimento.aceitar"} <= set(acoes)


def test_auditoria_descarta_senha_e_token(db, criar_usuario):
    usuario = criar_usuario()
    auditoria.registrar(db, "teste", usuario=usuario, senha="x", refresh_token="y", motivo="ok")
    db.flush()
    registro = db.scalar(select(Auditoria).where(Auditoria.acao == "teste"))
    assert registro.detalhes == {"motivo": "ok"}


# Cabeçalhos e configuração de produção


def test_cabecalhos_de_seguranca(client, cabecalhos):
    for resposta in (client.get("/health"), client.get("/estudantes")):
        assert resposta.headers["x-content-type-options"] == "nosniff"
        assert resposta.headers["x-frame-options"] == "DENY"
        assert resposta.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in resposta.headers["content-security-policy"]
    assert "strict-transport-security" not in client.get("/health").headers


def test_producao_desliga_swagger_e_liga_hsts():
    config = Settings(
        ambiente="producao",
        database_url=settings.database_url,
        jwt_secret=settings.jwt_secret,
        cors_origins=["https://educamobile.exemplo"],
        limite_backend="redis",
    )
    with TestClient(criar_app(config)) as cliente:
        assert cliente.get("/docs").status_code == 404
        assert cliente.get("/openapi.json").status_code == 404
        assert "max-age" in cliente.get("/health").headers["strict-transport-security"]


def test_producao_recusa_cors_sem_https():
    with pytest.raises(ValidationError):
        Settings(
            ambiente="producao",
            database_url="x",
            jwt_secret=SEGREDO_FORTE,
            cors_origins=["http://localhost:5173"],
        )


# Achados da revisão de segurança (pentest de 21/11/2026)


def test_segredo_de_exemplo_ou_fraco_recusado():
    for segredo in ("troque-por-um-segredo-com-pelo-menos-32-caracteres", "ab" * 20):
        with pytest.raises(ValidationError):
            Settings(database_url="x", jwt_secret=segredo)


def test_producao_recusa_senha_de_banco_de_exemplo():
    with pytest.raises(ValidationError):
        Settings(
            ambiente="producao",
            database_url="postgresql+psycopg://u:troque-esta-senha@db/x",
            jwt_secret=SEGREDO_FORTE,
            cors_origins=["https://educamobile.exemplo"],
        )


def test_limite_por_ip_barra_pulverizacao_de_senha(client, criar_usuario):
    alvo = criar_usuario()
    for i in range(30):
        client.post("/auth/login", data={"username": f"conta{i}@exemplo.com", "password": SENHA})
    assert _login(client, alvo).status_code == 429


def test_limite_por_conta_vale_para_qualquer_ip(client, criar_usuario, monkeypatch):
    monkeypatch.setattr(settings, "confiar_proxy", True)
    alvo = criar_usuario()
    for i in range(50):
        _login(client, alvo, "errada-12345", headers={"X-Forwarded-For": f"10.0.{i // 250}.{i}"})
    resposta = _login(client, alvo, headers={"X-Forwarded-For": "10.9.9.9"})
    assert resposta.status_code == 429


def test_x_forwarded_for_inventado_nao_troca_o_ip(client, criar_usuario, monkeypatch):
    monkeypatch.setattr(settings, "confiar_proxy", True)
    alvo = criar_usuario()
    for i in range(10):
        # O cliente inventa o primeiro IP; o proxy acrescenta o verdadeiro no fim.
        _login(client, alvo, "errada-12345", headers={"X-Forwarded-For": f"1.1.1.{i}, 203.0.113.7"})
    resposta = _login(client, alvo, headers={"X-Forwarded-For": "8.8.8.8, 203.0.113.7"})
    assert resposta.status_code == 429


def test_sem_proxy_x_forwarded_for_e_ignorado(client, criar_usuario):
    alvo = criar_usuario()
    for _ in range(10):
        _login(client, alvo, "errada-12345")
    resposta = _login(client, alvo, headers={"X-Forwarded-For": "10.9.9.9"})
    assert resposta.status_code == 429


def test_inundar_chaves_nao_zera_o_bloqueio():
    from app.limite import LimiteEmMemoria

    limite = LimiteEmMemoria(maximo=3, janela_s=900, max_chaves=5)
    for _ in range(3):
        limite.registrar_falha("alvo")
    for i in range(1_000):
        limite.registrar_falha(f"email-inventado-{i}@exemplo.com")
    assert limite.bloqueado("alvo")
    assert len(limite._falhas) <= 5


@pytest.mark.parametrize(
    "corpo",
    [
        '{"refresh_token": Infinity}',
        '{"refresh_token": NaN}',
        '{"refresh_token": "\\ud800"}',
        '{"a":' * 3000 + "1" + "}" * 3000,
        "{",
    ],
)
def test_json_hostil_recebe_422_e_nao_500(client, corpo):
    resposta = client.post(
        "/auth/refresh", content=corpo, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422


def test_422_nao_repete_o_valor_enviado(client, cabecalhos):
    novo = {"nome": "Ana", "email": "ana@exemplo.com", "senha": "segredo1", "perfil": "admin"}
    resposta = client.post("/usuarios", json=novo, headers=cabecalhos(Perfil.ADMIN))
    assert resposta.status_code == 422
    assert "segredo1" not in resposta.text
    assert all(set(item) == {"loc", "msg", "type"} for item in resposta.json()["detail"])


def test_corpo_grande_demais_recebe_413(client):
    grande = '{"refresh_token": "' + "a" * 2_000_000 + '"}'
    resposta = client.post(
        "/auth/refresh", content=grande, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 413

    def em_partes():
        for _ in range(30):
            yield b"a" * 100_000

    resposta = client.post(
        "/auth/refresh", content=em_partes(), headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 413
