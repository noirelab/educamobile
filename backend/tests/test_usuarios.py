"""Gestão de usuários e convite de responsável."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Auditoria, Convite, Estudante, Perfil, ResponsavelEstudante, Usuario

SENHA = "senha-forte-1"


def _criar(client, h, perfil="motorista", email="m@exemplo.com", nome="Maria"):
    return client.post(
        "/usuarios",
        json={"nome": nome, "email": email, "senha": SENHA, "perfil": perfil},
        headers=h,
    )


def test_gestor_cria_motorista_e_monitor_mas_nao_admin_nem_gestor(client, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    assert _criar(client, h, "motorista", "a@exemplo.com").status_code == 201
    assert _criar(client, h, "monitor", "b@exemplo.com").status_code == 201
    assert _criar(client, h, "admin", "c@exemplo.com").status_code == 403
    assert _criar(client, h, "gestor", "d@exemplo.com").status_code == 403


def test_admin_cria_admin_e_gestor(client, cabecalhos):
    h = cabecalhos(Perfil.ADMIN)
    assert _criar(client, h, "admin", "a@exemplo.com").status_code == 201
    assert _criar(client, h, "gestor", "b@exemplo.com").status_code == 201


def test_responsavel_nao_nasce_por_cadastro_direto(client, cabecalhos):
    assert _criar(client, cabecalhos(Perfil.ADMIN), "responsavel").status_code == 422


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_perfis_externos_nao_geram_usuarios(client, cabecalhos, perfil):
    h = cabecalhos(perfil)
    assert client.get("/usuarios", headers=h).status_code == 403
    assert _criar(client, h).status_code == 403
    assert client.post("/convites", json={}, headers=h).status_code == 403


def test_listagem_filtra_busca_e_traz_total(client, cabecalhos):
    h = cabecalhos(Perfil.ADMIN)
    _criar(client, h, "motorista", "j@exemplo.com", "João Silva")
    _criar(client, h, "motorista", "p@exemplo.com", "Pedro Souza")
    _criar(client, h, "monitor", "s@exemplo.com", "Sônia Silva")

    todos = client.get("/usuarios", headers=h).json()
    assert todos["total"] == 4  # os três mais o administrador do cabeçalho
    motoristas = client.get("/usuarios?perfil=motorista", headers=h).json()
    assert [u["nome"] for u in motoristas["itens"]] == ["João Silva", "Pedro Souza"]
    silva = client.get("/usuarios?q=silva", headers=h).json()
    assert silva["total"] == 2
    pagina = client.get("/usuarios?perfil=motorista&limit=1&offset=1", headers=h).json()
    assert pagina["total"] == 2
    assert [u["nome"] for u in pagina["itens"]] == ["Pedro Souza"]
    # Curingas do LIKE são tratados como texto.
    assert client.get("/usuarios?q=%25", headers=h).json()["total"] == 0
    assert "senha_hash" not in str(todos)


def test_gestor_nao_ve_nem_edita_admin_e_gestor(client, db, cabecalhos, criar_usuario):
    h = cabecalhos(Perfil.GESTOR)
    admin = criar_usuario(Perfil.ADMIN)
    colega = criar_usuario(Perfil.GESTOR)
    for alvo in (admin, colega):
        url = f"/usuarios/{alvo.id}"
        assert client.get(url, headers=h).status_code == 404
        assert client.patch(url, json={"nome": "X"}, headers=h).status_code == 404
        assert client.post(f"{url}/desativar", headers=h).status_code == 404
    assert client.get("/usuarios/999999", headers=h).status_code == 404


def test_editar_usuario_e_email_repetido(client, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    a = _criar(client, h, "motorista", "a@exemplo.com").json()
    _criar(client, h, "motorista", "b@exemplo.com")
    url = f"/usuarios/{a['id']}"
    ok = client.patch(url, json={"nome": "Novo Nome", "email": "NOVO@exemplo.com"}, headers=h)
    assert ok.status_code == 200
    assert ok.json()["nome"] == "Novo Nome"
    assert ok.json()["email"] == "novo@exemplo.com"
    assert client.patch(url, json={"email": "b@exemplo.com"}, headers=h).status_code == 409
    assert client.patch(url, json={}, headers=h).status_code == 422
    assert client.patch(url, json={"perfil": "admin"}, headers=h).status_code == 422


def test_desativar_derruba_sessoes_e_reativar_devolve_o_acesso(client, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    motorista = _criar(client, h).json()
    login = client.post("/auth/login", data={"username": "m@exemplo.com", "password": SENHA})
    acesso = {"Authorization": f"Bearer {login.json()['access_token']}"}
    refresh = login.json()["refresh_token"]
    assert client.get("/auth/me", headers=acesso).status_code == 200

    url = f"/usuarios/{motorista['id']}"
    assert client.post(f"{url}/desativar", headers=h).json()["ativo"] is False
    assert client.get("/auth/me", headers=acesso).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    entrada = client.post("/auth/login", data={"username": "m@exemplo.com", "password": SENHA})
    assert entrada.status_code == 401

    assert client.post(f"{url}/reativar", headers=h).json()["ativo"] is True
    entrada = client.post("/auth/login", data={"username": "m@exemplo.com", "password": SENHA})
    assert entrada.status_code == 200


def test_nao_desativa_a_propria_conta(client, db, criar_usuario):
    from app.security import criar_token

    admin = criar_usuario(Perfil.ADMIN)
    h = {"Authorization": f"Bearer {criar_token(admin)}"}
    assert client.post(f"/usuarios/{admin.id}/desativar", headers=h).status_code == 409


def test_acoes_ficam_na_auditoria(client, db, cabecalhos):
    h = cabecalhos(Perfil.GESTOR)
    usuario = _criar(client, h).json()
    client.patch(f"/usuarios/{usuario['id']}", json={"nome": "Z"}, headers=h)
    client.post(f"/usuarios/{usuario['id']}/desativar", headers=h)
    acoes = set(db.scalars(select(Auditoria.acao)))
    assert {"usuario.criar", "usuario.editar", "usuario.desativar"} <= acoes


# Convites


@pytest.fixture
def filho(db):
    from datetime import date

    estudante = Estudante(nome="Bia", data_nascimento=date(2017, 3, 1))
    db.add(estudante)
    db.flush()
    return estudante


def _convidar(client, h, filho, email="mae@exemplo.com"):
    return client.post(
        "/convites",
        json={"nome": "Ana", "email": email, "estudante_id": filho.id, "parentesco": "mãe"},
        headers=h,
    )


def test_convite_guarda_so_o_hash_e_o_codigo_aparece_uma_vez(client, db, cabecalhos, filho):
    resposta = _convidar(client, cabecalhos(Perfil.GESTOR), filho)
    assert resposta.status_code == 201
    codigo = resposta.json()["codigo"]
    assert len(codigo) >= 30
    convite = db.scalars(select(Convite)).one()
    assert codigo not in (convite.codigo_hash, convite.email)
    listagem = client.get("/convites", headers=cabecalhos(Perfil.GESTOR))
    assert codigo not in listagem.text


def test_responsavel_entra_so_pelo_convite_e_o_convite_nao_funciona_duas_vezes(
    client, db, cabecalhos, filho
):
    codigo = _convidar(client, cabecalhos(Perfil.GESTOR), filho).json()["codigo"]
    url = f"/auth/convites/{codigo}/aceitar"

    aceite = client.post(url, json={"senha": "senha-da-mae-1"})
    assert aceite.status_code == 201
    acesso = {"Authorization": f"Bearer {aceite.json()['access_token']}"}
    assert client.get("/auth/me", headers=acesso).json()["perfil"] == "responsavel"
    filhos = client.get("/responsavel/filhos", headers=acesso).json()
    assert [f["estudante_id"] for f in filhos] == [filho.id]
    assert filhos[0]["consentimento_pendente"] is True

    assert client.post(url, json={"senha": "outra-senha-2"}).status_code == 404
    entrada = client.post(
        "/auth/login", data={"username": "mae@exemplo.com", "password": "senha-da-mae-1"}
    )
    assert entrada.status_code == 200
    assert db.scalars(select(ResponsavelEstudante)).one().parentesco == "mãe"


def test_convite_expirado_ou_inexistente_da_404(client, db, cabecalhos, filho):
    codigo = _convidar(client, cabecalhos(Perfil.GESTOR), filho).json()["codigo"]
    db.scalars(select(Convite)).one().expira_em = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    corpo = {"senha": "senha-da-mae-1"}
    assert client.post(f"/auth/convites/{codigo}/aceitar", json=corpo).status_code == 404
    assert client.post("/auth/convites/inventado/aceitar", json=corpo).status_code == 404
    assert db.scalar(select(Usuario).where(Usuario.email == "mae@exemplo.com")) is None


def test_convite_valido_por_72_horas(client, db, cabecalhos, filho):
    resposta = _convidar(client, cabecalhos(Perfil.GESTOR), filho).json()
    expira = datetime.fromisoformat(resposta["expira_em"])
    assert timedelta(hours=71, minutes=55) < expira - datetime.now(UTC) <= timedelta(hours=72)


def test_senha_fraca_nao_consome_o_convite(client, cabecalhos, filho):
    codigo = _convidar(client, cabecalhos(Perfil.GESTOR), filho).json()["codigo"]
    url = f"/auth/convites/{codigo}/aceitar"
    assert client.post(url, json={"senha": "curta"}).status_code == 422
    assert client.post(url, json={"senha": "senha-da-mae-1"}).status_code == 201


def test_convite_recusa_email_com_conta_e_estudante_inexistente(
    client, cabecalhos, criar_usuario, filho
):
    h = cabecalhos(Perfil.GESTOR)
    existente = criar_usuario(Perfil.RESPONSAVEL)
    assert _convidar(client, h, filho, existente.email).status_code == 409
    corpo = {"nome": "A", "email": "x@exemplo.com", "estudante_id": 999999, "parentesco": "pai"}
    assert client.post("/convites", json=corpo, headers=h).status_code == 404


def test_limite_de_tentativas_no_aceite(client):
    corpo = {"senha": "senha-da-mae-1"}
    for _ in range(10):
        assert client.post("/auth/convites/errado/aceitar", json=corpo).status_code == 404
    bloqueado = client.post("/auth/convites/errado/aceitar", json=corpo)
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers


def test_convite_e_aceite_ficam_na_auditoria(client, db, cabecalhos, filho):
    codigo = _convidar(client, cabecalhos(Perfil.GESTOR), filho).json()["codigo"]
    client.post(f"/auth/convites/{codigo}/aceitar", json={"senha": "senha-da-mae-1"})
    registros = list(db.scalars(select(Auditoria).where(Auditoria.acao.like("convite.%"))))
    assert {r.acao for r in registros} == {"convite.criar", "convite.aceitar"}
    assert codigo not in str([r.detalhes for r in registros])
