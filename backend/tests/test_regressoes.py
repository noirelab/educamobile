"""Falhas encontradas nas revisões de código e de segurança."""

import pytest

from app.models import Perfil
from app.routers.auth import MAX_FALHAS_LOGIN
from tests.conftest import estudante_de_teste

GRANDE = 2**40


@pytest.mark.parametrize(
    ("metodo", "rota", "corpo"),
    [
        ("get", f"/rotas/{GRANDE}", None),
        ("get", f"/paradas/{GRANDE}", None),
        ("get", "/rotas?offset=99999999999999999999", None),
        ("get", "/paradas?offset=99999999999999999999", None),
        ("put", "/rotas/1/paradas", {"parada_ids": [GRANDE]}),
    ],
)
def test_id_fora_do_limite_nao_vira_erro_500(client, cabecalhos, metodo, rota, corpo):
    kwargs = {"json": corpo} if corpo else {}
    resposta = getattr(client, metodo)(rota, headers=cabecalhos(Perfil.ADMIN), **kwargs)
    assert resposta.status_code == 422, resposta.text


@pytest.mark.parametrize(
    ("rota", "corpo"),
    [
        ("/paradas", {"nome": "a\x00b", "localizacao": {"latitude": 0, "longitude": 0}}),
        ("/rotas", {"nome": "a\x00b"}),
        (
            "/usuarios",
            {
                "nome": "a\x00b",
                "email": "n@exemplo.com",
                "senha": "senha-forte-1",
                "perfil": "admin",
            },
        ),
    ],
)
def test_nul_em_texto_e_rejeitado(client, cabecalhos, rota, corpo):
    resposta = client.post(rota, json=corpo, headers=cabecalhos(Perfil.ADMIN))
    assert resposta.status_code == 422


def test_login_com_nul_ou_senha_gigante_nao_quebra(client, criar_usuario):
    usuario = criar_usuario()
    nul = client.post("/auth/login", data={"username": "a\x00b", "password": "x"})
    assert nul.status_code == 401
    gigante = client.post("/auth/login", data={"username": usuario.email, "password": "x" * 5000})
    assert gigante.status_code == 401


def test_login_bloqueia_depois_de_muitas_falhas(client, criar_usuario):
    usuario = criar_usuario()
    dados = {"username": usuario.email, "password": "errada"}
    for _ in range(MAX_FALHAS_LOGIN):
        assert client.post("/auth/login", data=dados).status_code == 401
    certa = {"username": usuario.email, "password": "senha-forte-1"}
    bloqueado = client.post("/auth/login", data=certa)
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers
    outro = criar_usuario()
    livre = {"username": outro.email, "password": "senha-forte-1"}
    assert client.post("/auth/login", data=livre).status_code == 200


def test_so_admin_remove_estudante(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    url = f"/estudantes/{estudante.id}"
    assert client.delete(url, headers=cabecalhos(Perfil.GESTOR)).status_code == 403
    assert client.delete(url, headers=cabecalhos(Perfil.ADMIN)).status_code == 204
