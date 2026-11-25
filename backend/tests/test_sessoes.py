"""Sessões: limite de aparelhos, lista, revogação individual e limpeza das antigas."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app import sessoes
from app.models import Perfil, Sessao

SENHA = "senha-forte-1"


def _login(client, usuario, agente="aparelho"):
    r = client.post(
        "/auth/login",
        data={"username": usuario.email, "password": SENHA},
        headers={"User-Agent": agente},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_lista_so_os_aparelhos_ativos_da_propria_conta(client, db, criar_usuario):
    eu, outro = criar_usuario(Perfil.RESPONSAVEL), criar_usuario(Perfil.RESPONSAVEL)
    a = _login(client, eu, "celular")
    _login(client, eu, "tablet")
    _login(client, outro, "alheio")
    lista = client.get("/auth/sessoes", headers=_h(a["access_token"])).json()
    assert [s["user_agent"] for s in lista] == ["tablet", "celular"]
    assert all(set(s) == {"id", "criada_em", "expira_em", "ip", "user_agent"} for s in lista)
    assert "token" not in str(lista).lower()


def test_revogar_um_aparelho_derruba_o_refresh_dele_e_so_dele(client, db, criar_usuario):
    eu = criar_usuario(Perfil.RESPONSAVEL)
    celular, tablet = _login(client, eu, "celular"), _login(client, eu, "tablet")
    h = _h(celular["access_token"])
    id_do_tablet = next(
        s["id"]
        for s in client.get("/auth/sessoes", headers=h).json()
        if s["user_agent"] == "tablet"
    )

    assert client.delete(f"/auth/sessoes/{id_do_tablet}", headers=h).status_code == 204
    assert (
        client.post("/auth/refresh", json={"refresh_token": tablet["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post("/auth/refresh", json={"refresh_token": celular["refresh_token"]}).status_code
        == 200
    )
    # O refresh do celular o trocou por uma sessão nova; o tablet continua fora.
    restantes = client.get("/auth/sessoes", headers=h).json()
    assert len(restantes) == 1 and restantes[0]["id"] != id_do_tablet


def test_nao_revoga_sessao_de_outra_pessoa_nem_inexistente_nem_repetida(client, db, criar_usuario):
    eu, outro = criar_usuario(Perfil.RESPONSAVEL), criar_usuario(Perfil.RESPONSAVEL)
    meu = _login(client, eu)
    do_outro = _login(client, outro)
    id_alheio = client.get("/auth/sessoes", headers=_h(do_outro["access_token"])).json()[0]["id"]
    h = _h(meu["access_token"])
    assert client.delete(f"/auth/sessoes/{id_alheio}", headers=h).status_code == 404
    assert client.delete("/auth/sessoes/999999", headers=h).status_code == 404
    assert (
        client.post("/auth/refresh", json={"refresh_token": do_outro["refresh_token"]}).status_code
        == 200
    )
    proprio = client.get("/auth/sessoes", headers=h).json()[0]["id"]
    assert client.delete(f"/auth/sessoes/{proprio}", headers=h).status_code == 204
    assert client.delete(f"/auth/sessoes/{proprio}", headers=h).status_code == 404


def test_no_maximo_dez_aparelhos_o_mais_antigo_cai(client, db, criar_usuario):
    eu = criar_usuario(Perfil.RESPONSAVEL)
    logins = [_login(client, eu, f"aparelho-{i}") for i in range(12)]
    ativas = sessoes.listar_ativas(db, eu)
    assert len(ativas) == sessoes.MAX_SESSOES_ATIVAS
    assert {s.user_agent for s in ativas} == {f"aparelho-{i}" for i in range(2, 12)}
    assert (
        client.post("/auth/refresh", json={"refresh_token": logins[0]["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": logins[11]["refresh_token"]}
        ).status_code
        == 200
    )


def test_renovar_nao_conta_como_aparelho_novo(client, db, criar_usuario):
    eu = criar_usuario(Perfil.RESPONSAVEL)
    atual = _login(client, eu)
    for _ in range(15):
        atual = client.post("/auth/refresh", json={"refresh_token": atual["refresh_token"]}).json()
    assert len(sessoes.listar_ativas(db, eu)) == 1


def test_limpeza_apaga_so_o_que_passou_dos_30_dias(client, db, criar_usuario):
    eu = criar_usuario(Perfil.RESPONSAVEL)
    agora = datetime.now(UTC)
    ativa = _login(client, eu)
    db.flush()

    def sessao(**campos):
        s = Sessao(usuario_id=eu.id, token_hash=campos.pop("h"), **campos)
        db.add(s)
        return s

    sessao(h="a", expira_em=agora - timedelta(days=31))  # expirada há mais de 30 dias
    sessao(h="b", expira_em=agora + timedelta(days=5), revogada_em=agora - timedelta(days=31))
    recente_expirada = sessao(h="c", expira_em=agora - timedelta(days=2))
    recente_revogada = sessao(
        h="d", expira_em=agora + timedelta(days=5), revogada_em=agora - timedelta(days=2)
    )
    db.flush()

    assert sessoes.limpar_antigas(db, agora) == 2
    restantes = {s.token_hash for s in db.scalars(select(Sessao))}
    assert {recente_expirada.token_hash, recente_revogada.token_hash} <= restantes
    assert "a" not in restantes and "b" not in restantes
    assert client.get("/auth/sessoes", headers=_h(ativa["access_token"])).status_code == 200


def test_listar_e_revogar_exigem_login(client):
    assert client.get("/auth/sessoes").status_code == 401
    assert client.delete("/auth/sessoes/1").status_code == 401


def test_renovar_com_dez_aparelhos_nao_derruba_outro(client, db, criar_usuario):
    """O caso da revisão: com 10 sessões, renovar uma revogava a mais antiga (ficavam 9)."""
    eu = criar_usuario(Perfil.RESPONSAVEL)
    logins = [_login(client, eu, f"aparelho-{i}") for i in range(sessoes.MAX_SESSOES_ATIVAS)]
    r = client.post("/auth/refresh", json={"refresh_token": logins[5]["refresh_token"]})
    assert r.status_code == 200
    assert len(sessoes.listar_ativas(db, eu)) == sessoes.MAX_SESSOES_ATIVAS
    assert (
        client.post("/auth/refresh", json={"refresh_token": logins[0]["refresh_token"]}).status_code
        == 200
    )


def test_reuso_de_refresh_token_nao_apaga_os_aparelhos_de_push(client, db, criar_usuario):
    """Quem guardou um token antigo não pode cortar os avisos do responsável."""
    from app.models import Dispositivo

    eu = criar_usuario(Perfil.RESPONSAVEL)
    login = _login(client, eu)
    db.add(Dispositivo(usuario_id=eu.id, token="d" * 40, plataforma="android"))
    db.flush()
    client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    reuso = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert reuso.status_code == 401
    assert sessoes.listar_ativas(db, eu) == []
    assert len(db.scalars(select(Dispositivo)).all()) == 1
