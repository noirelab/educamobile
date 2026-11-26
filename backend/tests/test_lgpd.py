"""LGPD: retenção, consulta à auditoria e novo aceite quando o termo muda."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import retencao, tempo
from app.config import settings
from app.models import (
    Alerta,
    Auditoria,
    Ausencia,
    Configuracao,
    Convite,
    EventoViagem,
    Notificacao,
    Perfil,
    Posicao,
    ResponsavelEstudante,
    Sentido,
    Severidade,
    TipoEvento,
    Turno,
    Viagem,
)
from app.security import criar_token
from tests.conftest import estudante_de_teste, rota_de_teste

AGORA = datetime.now(UTC)


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _viagem(db, dia, nome):
    rota = rota_de_teste(db, nome)
    v = Viagem(
        rota_id=rota.id, data=dia, turno=Turno.MANHA, sentido=Sentido.IDA, escola_id=rota.escola_id
    )
    db.add(v)
    db.flush()
    return v


def _ponto(lat=0.0):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    return from_shape(Point(0.0, lat), srid=4326)


# Retenção


def test_posicoes_somem_depois_de_90_dias_e_o_resto_fica(db):
    v = _viagem(db, AGORA.date(), "Recente")
    db.add_all(
        [
            Posicao(viagem_id=v.id, registrada_em=AGORA - timedelta(days=91), localizacao=_ponto()),
            Posicao(viagem_id=v.id, registrada_em=AGORA - timedelta(days=89), localizacao=_ponto()),
        ]
    )
    db.flush()
    saiu = retencao.executar(db, AGORA)
    assert saiu["posicao"] == 1
    assert len(db.scalars(select(Posicao)).all()) == 1
    assert db.get(Viagem, v.id) is not None


def test_viagens_e_o_que_depende_delas_somem_no_prazo_inclusive_eventos(db, criar_usuario):
    dono = criar_usuario(Perfil.RESPONSAVEL)
    velha = _viagem(db, (AGORA - timedelta(days=400)).date(), "Velha")
    nova = _viagem(db, (AGORA - timedelta(days=10)).date(), "Nova")
    aluno = estudante_de_teste(db, "Ana")
    for viagem in (velha, nova):
        db.add(
            EventoViagem(
                id=uuid.uuid4(),
                viagem_id=viagem.id,
                tipo=TipoEvento.ONIBUS_VAZIO,
                hora_aparelho=AGORA,
            )
        )
        db.add(Alerta(viagem_id=viagem.id, tipo="x", severidade=Severidade.AVISO, mensagem="m"))
        db.add(
            Notificacao(usuario_id=dono.id, viagem_id=viagem.id, tipo="x", titulo="t", mensagem="m")
        )
    db.add(Ausencia(estudante_id=aluno.id, data=(AGORA - timedelta(days=400)).date()))
    db.add(
        Ausencia(
            estudante_id=aluno.id, data=(AGORA - timedelta(days=5)).date(), sentido=Sentido.IDA
        )
    )
    db.flush()

    saiu = retencao.executar(db, AGORA)
    assert saiu["viagem"] == 1 and saiu["evento_viagem"] == 1 and saiu["ausencia"] == 1
    assert [v.id for v in db.scalars(select(Viagem).where(Viagem.id.in_([velha.id, nova.id])))] == [
        nova.id
    ]
    assert db.scalar(select(text("count(*)")).select_from(EventoViagem)) == 1
    assert len(db.scalars(select(Alerta)).all()) == 1


def test_a_auditoria_tem_prazo_proprio_mais_longo(db, criar_usuario):
    u = criar_usuario(Perfil.ADMIN)
    db.add_all(
        [
            Auditoria(usuario_id=u.id, acao="velha", em=AGORA - timedelta(days=800)),
            Auditoria(usuario_id=u.id, acao="meio", em=AGORA - timedelta(days=500)),
        ]
    )
    db.flush()
    retencao.executar(db, AGORA)
    acoes = set(db.scalars(select(Auditoria.acao).where(Auditoria.usuario_id == u.id)))
    assert "meio" in acoes and "velha" not in acoes


def test_prazos_vem_da_tabela(db):
    v = _viagem(db, AGORA.date(), "Recente")
    db.add(Posicao(viagem_id=v.id, registrada_em=AGORA - timedelta(days=20), localizacao=_ponto()))
    db.flush()
    assert retencao.executar(db, AGORA)["posicao"] == 0
    db.get(Configuracao, "retencao_posicoes_dias").valor = 10
    db.flush()
    assert retencao.executar(db, AGORA)["posicao"] == 1


def test_a_excecao_de_apagar_evento_nao_vaza_para_fora_da_rotina(db):
    """Depois da retenção, o trigger volta a recusar DELETE em qualquer conexão."""
    v = _viagem(db, AGORA.date(), "Recente")
    db.add(
        EventoViagem(
            id=uuid.uuid4(), viagem_id=v.id, tipo=TipoEvento.ONIBUS_VAZIO, hora_aparelho=AGORA
        )
    )
    db.flush()
    retencao.executar(db, AGORA)
    with pytest.raises(DBAPIError, match="só de inclusão"), db.begin_nested():
        db.execute(text("DELETE FROM evento_viagem"))


def test_o_trigger_continua_recusando_delete_sem_a_declaracao(db):
    v = _viagem(db, AGORA.date(), "Recente")
    db.add(
        EventoViagem(
            id=uuid.uuid4(), viagem_id=v.id, tipo=TipoEvento.ONIBUS_VAZIO, hora_aparelho=AGORA
        )
    )
    db.flush()
    with pytest.raises(DBAPIError, match="só de inclusão"), db.begin_nested():
        db.execute(text("DELETE FROM evento_viagem"))


# Consulta à auditoria


def test_so_o_admin_consulta_a_auditoria_com_filtros(client, db, criar_usuario):
    admin, gestor = criar_usuario(Perfil.ADMIN), criar_usuario(Perfil.GESTOR)
    db.add_all(
        [
            Auditoria(
                usuario_id=gestor.id, acao="posicao.consultar", recurso="viagem", recurso_id="7"
            ),
            Auditoria(
                usuario_id=gestor.id, acao="relatorio.exportar", recurso="relatorio", recurso_id="x"
            ),
            Auditoria(usuario_id=admin.id, acao="login.ok"),
        ]
    )
    db.flush()
    h = _h(admin)
    assert client.get("/auditoria", headers=_h(gestor)).status_code == 403
    assert client.get("/auditoria").status_code == 401

    por_usuario = client.get(f"/auditoria?usuario_id={gestor.id}", headers=h).json()
    assert {r["acao"] for r in por_usuario} == {"posicao.consultar", "relatorio.exportar"}
    exata = client.get("/auditoria?acao=login.ok", headers=h).json()
    assert [r["acao"] for r in exata] == ["login.ok"]
    prefixo = client.get("/auditoria?acao=posicao.", headers=h).json()
    assert [r["acao"] for r in prefixo] == ["posicao.consultar"]
    assert (
        client.get("/auditoria?recurso=viagem&recurso_id=7", headers=h).json()[0]["acao"]
        == "posicao.consultar"
    )
    futuro = (AGORA + timedelta(days=1)).isoformat()
    assert client.get("/auditoria", params={"desde": futuro}, headers=h).json() == []


def test_consultar_a_auditoria_tambem_fica_registrado(client, db, criar_usuario):
    admin = criar_usuario(Perfil.ADMIN)
    client.get("/auditoria", headers=_h(admin))
    assert db.scalar(select(Auditoria.acao).where(Auditoria.acao == "auditoria.consultar"))


def test_prefixo_com_curinga_do_like_e_tratado_como_texto(client, db, criar_usuario):
    admin = criar_usuario(Perfil.ADMIN)
    db.add(Auditoria(usuario_id=admin.id, acao="abc.def"))
    db.flush()
    assert client.get("/auditoria?acao=%25.", headers=_h(admin)).json() == []


# Novo termo de consentimento


@pytest.fixture
def mae(db, criar_usuario):
    filho = estudante_de_teste(db, "Bia")
    mae = criar_usuario(Perfil.RESPONSAVEL)
    vinculo = ResponsavelEstudante(
        responsavel_id=mae.id,
        estudante_id=filho.id,
        parentesco="mãe",
        consentimento_em=datetime.now(UTC),
        consentimento_versao=settings.versao_termo_consentimento,
    )
    db.add(vinculo)
    db.flush()
    return mae, filho, vinculo


def test_com_o_termo_atual_o_responsavel_ve_o_filho(client, mae):
    usuario, filho, _ = mae
    assert client.get(f"/responsavel/filhos/{filho.id}", headers=_h(usuario)).status_code == 200
    assert (
        client.get("/responsavel/filhos", headers=_h(usuario)).json()[0]["consentimento_pendente"]
        is False
    )


def test_nova_versao_do_termo_obriga_novo_aceite(client, mae, monkeypatch):
    usuario, filho, _ = mae
    h = _h(usuario)
    monkeypatch.setattr(settings, "versao_termo_consentimento", "2027-02")

    assert client.get(f"/responsavel/filhos/{filho.id}", headers=h).status_code == 403
    assert client.get(f"/responsavel/filhos/{filho.id}/hoje", headers=h).status_code == 403
    assert client.get(f"/responsavel/filhos/{filho.id}/foto-url", headers=h).status_code == 403
    assert (
        client.post(
            "/ausencias",
            json={"estudante_id": filho.id, "data": tempo.hoje().isoformat()},
            headers=h,
        ).status_code
        == 403
    )
    assert client.get("/responsavel/filhos", headers=h).json()[0]["consentimento_pendente"] is True

    # O termo antigo já não serve; o novo, sim.
    antigo = client.post(
        f"/responsavel/filhos/{filho.id}/consentimento", json={"versao_termo": "2026-11"}, headers=h
    )
    assert antigo.status_code == 422
    novo = client.post(
        f"/responsavel/filhos/{filho.id}/consentimento", json={"versao_termo": "2027-02"}, headers=h
    )
    assert novo.status_code == 200
    assert client.get(f"/responsavel/filhos/{filho.id}", headers=h).status_code == 200


def test_sem_novo_aceite_nao_chegam_notificacoes_nem_avisos(db, mae, monkeypatch):
    from app import notificacoes

    usuario, filho, _ = mae
    assert notificacoes.para_responsaveis(db, filho.id, "x", "t", "m") == 1
    monkeypatch.setattr(settings, "versao_termo_consentimento", "2027-02")
    assert notificacoes.para_responsaveis(db, filho.id, "x", "t", "m") == 0


def test_convite_usado_ou_vencido_sai_depois_de_30_dias(db):
    """O caso da revisão: nome e e-mail do convidado ficavam para sempre."""
    filho = estudante_de_teste(db)
    agora = datetime.now(UTC)

    def convite(codigo, expira_dias, usado_dias=None):
        db.add(
            Convite(
                codigo_hash=codigo,
                nome="Mãe",
                email=f"{codigo}@exemplo.com",
                estudante_id=filho.id,
                parentesco="mãe",
                expira_em=agora + timedelta(days=expira_dias),
                usado_em=agora - timedelta(days=usado_dias) if usado_dias is not None else None,
            )
        )

    convite("pendente", 2)
    convite("vencido-ha-pouco", -5)
    convite("vencido-ha-muito", -40)
    convite("usado-ha-muito", -37, usado_dias=40)
    db.flush()
    assert retencao.executar(db, agora)["convite"] == 2
    assert set(db.scalars(select(Convite.codigo_hash))) == {"pendente", "vencido-ha-pouco"}
