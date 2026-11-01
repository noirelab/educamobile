from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.config import settings
from app.models import Perfil
from app.schemas.auth import UsuarioCriar
from app.security import ALGORITMO, criar_token


def _token(client, email, senha):
    return client.post("/auth/login", data={"username": email, "password": senha})


def test_login_e_me(client, criar_usuario):
    usuario = criar_usuario(Perfil.COORDENADOR)
    resposta = _token(client, usuario.email, "senha-forte-1")
    assert resposta.status_code == 200
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {resposta.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["perfil"] == "coordenador"
    assert "senha_hash" not in me.json()


@pytest.mark.parametrize("senha", ["errada", ""])
def test_login_senha_errada(client, criar_usuario, senha):
    assert _token(client, criar_usuario().email, senha).status_code in (401, 422)


def test_login_email_inexistente(client):
    assert _token(client, "ninguem@exemplo.com", "senha-forte-1").status_code == 401


def test_login_usuario_inativo(client, db, criar_usuario):
    usuario = criar_usuario()
    usuario.ativo = False
    db.flush()
    assert _token(client, usuario.email, "senha-forte-1").status_code == 401


def test_me_exige_token(client):
    assert client.get("/auth/me").status_code == 401


def test_token_invalidos(client, criar_usuario):
    usuario = criar_usuario()
    agora = datetime.now(UTC)
    expirado = jwt.encode(
        {"sub": str(usuario.id), "exp": agora - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=ALGORITMO,
    )
    outra_chave = jwt.encode(
        {"sub": str(usuario.id), "exp": agora + timedelta(minutes=5)},
        "x" * 40,
        algorithm=ALGORITMO,
    )
    sem_assinatura = jwt.encode(
        {"sub": str(usuario.id), "exp": agora + timedelta(minutes=5)}, "", algorithm="none"
    )
    for token in (expirado, outra_chave, sem_assinatura, "lixo"):
        resposta = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resposta.status_code == 401, token


def test_token_de_usuario_desativado_deixa_de_valer(client, db, criar_usuario):
    usuario = criar_usuario()
    token = criar_token(usuario)
    usuario.ativo = False
    db.flush()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


NOVO = {
    "nome": "Ana",
    "email": "Ana@Exemplo.com",
    "senha": "senha-forte-1",
    "perfil": "coordenador",
}


def test_admin_cria_usuario_e_email_duplicado_conflita(client, cabecalhos):
    h = cabecalhos(Perfil.ADMIN)
    resposta = client.post("/auth/usuarios", json=NOVO, headers=h)
    assert resposta.status_code == 201
    assert resposta.json()["email"] == "ana@exemplo.com"
    assert _token(client, "ANA@exemplo.com".lower(), NOVO["senha"]).status_code == 200
    assert client.post("/auth/usuarios", json=NOVO, headers=h).status_code == 409


@pytest.mark.parametrize("perfil", [Perfil.DIRETOR, Perfil.COORDENADOR])
def test_so_admin_cria_usuario(client, cabecalhos, perfil):
    assert client.post("/auth/usuarios", json=NOVO, headers=cabecalhos(perfil)).status_code == 403


def test_diretor_precisa_de_escola():
    with pytest.raises(ValidationError):
        UsuarioCriar(nome="D", email="d@exemplo.com", senha="senha-forte-1", perfil=Perfil.DIRETOR)


def test_senha_curta_rejeitada():
    with pytest.raises(ValidationError):
        UsuarioCriar(nome="D", email="d@exemplo.com", senha="curta", perfil=Perfil.ADMIN)
