"""Worker de alertas: uma regra por teste, mais reconhecer, resolver, limites e emergência."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text

from app import alertas, tempo_real
from app.config import settings
from app.models import (
    Alerta,
    Configuracao,
    Inscricao,
    Motorista,
    Notificacao,
    Perfil,
    Posicao,
    ResponsavelEstudante,
    Sentido,
    StatusViagem,
    Turno,
    Veiculo,
    Viagem,
)
from app.security import criar_token
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste
from tests.test_rotas import _parada

HOJE = date.today()
AGORA = datetime.now(UTC)
LAT_ESCOLA = 0.03


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


@pytest.fixture
def mundo(client, db, cabecalhos, criar_usuario):
    escola = escola_de_teste(db, "Escola", LAT_ESCOLA, 0.0, raio_cerca_m=150)
    a, na_escola = _parada(db, 0.01, nome="A"), _parada(db, LAT_ESCOLA, nome="Escola")
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
        f"/rotas/{rota.id}/paradas",
        json={
            "paradas": [
                {"parada_id": a.id, "horario_previsto": "06:30:00"},
                {"parada_id": na_escola.id, "horario_previsto": "07:10:00"},
            ]
        },
        headers=gestor,
    )
    ana = estudante_de_teste(db, "Ana Souza", escola_id=escola.id)
    db.add(
        Inscricao(
            estudante_id=ana.id,
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
        "motorista": motorista,
        "hm": _h(motorista),
        "ana": ana,
        "a": a,
        "escola": escola,
        "rota": rota,
        "veiculo": veiculo,
    }


def _iniciar(client, m):
    r = client.post(f"/viagens/{m['viagem']['id']}/iniciar", headers=m["hm"])
    assert r.status_code == 200, r.text


def _posicao_redis(m, lat, *, desde_s=0, velocidade=30.0, desvio=0.0):
    tempo_real.guardar_posicao(
        m["viagem"]["id"],
        {
            "viagem_id": m["viagem"]["id"],
            "latitude": lat,
            "longitude": 0.0,
            "registrada_em": (AGORA - timedelta(seconds=desde_s)).isoformat(),
            "ts": (AGORA - timedelta(seconds=desde_s)).timestamp(),
            "velocidade_kmh": velocidade,
            "desvio_m": desvio,
        },
    )


def _tipos(criados):
    return sorted(a.tipo for a in criados)


# R6 viagem não iniciada


def test_r6_viagem_nao_iniciada(client, db, mundo):
    local = datetime.now(ZoneInfo(settings.fuso_horario))
    # 06:30 previsto; "agora" é 06:45 locais de hoje (15 min de atraso, limite 10).
    quando = local.replace(hour=6, minute=45, second=0, microsecond=0).astimezone(UTC)
    criados = alertas.executar_regras(db, quando)
    assert _tipos(criados) == ["viagem_nao_iniciada"]
    assert criados[0].dados["atraso_min"] == 15
    # Repetir não abre outro.
    assert alertas.executar_regras(db, quando) == []


def test_r6_dentro_da_tolerancia_ou_ja_iniciada_nao_alerta(client, db, mundo):
    local = datetime.now(ZoneInfo(settings.fuso_horario))
    cedo = local.replace(hour=6, minute=38, second=0, microsecond=0).astimezone(UTC)
    assert alertas.executar_regras(db, cedo) == []
    _iniciar(client, mundo)
    tarde = local.replace(hour=7, minute=0, second=0, microsecond=0).astimezone(UTC)
    assert "viagem_nao_iniciada" not in _tipos(alertas.executar_regras(db, tarde))


# R7 sem sinal


def test_r7_sem_sinal_abre_e_resolve_sozinho(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.001, desde_s=300)
    criados = alertas.executar_regras(db, AGORA)
    assert _tipos(criados) == ["sem_sinal"]
    assert criados[0].resolvido_em is None
    assert criados[0].dados["limite_s"] == 120

    # O sinal volta: o alerta se resolve sem ninguém mexer.
    _posicao_redis(mundo, 0.002, desde_s=5)
    alertas.executar_regras(db, AGORA)
    db.refresh(criados[0])
    assert criados[0].resolvido_em is not None
    assert criados[0].resolvido_automaticamente is True
    assert criados[0].resolvido_por_id is None


def test_r7_viagem_sem_nenhuma_posicao_conta_desde_o_inicio(client, db, mundo):
    _iniciar(client, mundo)
    viagem = db.get(Viagem, mundo["viagem"]["id"])
    viagem.iniciada_em = AGORA - timedelta(minutes=10)
    db.flush()
    assert _tipos(alertas.executar_regras(db, AGORA)) == ["sem_sinal"]


def test_r7_viagem_concluida_fecha_o_alerta_de_sem_sinal(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.001, desde_s=400)
    [alerta] = alertas.executar_regras(db, AGORA)
    db.get(Viagem, mundo["viagem"]["id"]).status = StatusViagem.CONCLUIDA
    db.flush()
    alertas.executar_regras(db, AGORA)
    db.refresh(alerta)
    assert alerta.resolvido_automaticamente is True


# R8 desvio


def test_r8_desvio_de_rota(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, desvio=450)
    criados = alertas.executar_regras(db, AGORA)
    assert _tipos(criados) == ["desvio_de_rota"]
    assert criados[0].dados["desvio_m"] == 450
    assert criados[0].dados["latitude"] == 0.015


def test_r8_dentro_do_limite_nao_alerta(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, desvio=250)
    assert alertas.executar_regras(db, AGORA) == []


# R9 parada não prevista


def _gravar(db, viagem_id, lat, minutos_atras):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    db.add(
        Posicao(
            viagem_id=viagem_id,
            registrada_em=AGORA - timedelta(minutes=minutos_atras),
            localizacao=from_shape(Point(0.0, lat), srid=4326),
        )
    )


def test_r9_parada_nao_prevista(client, db, mundo):
    _iniciar(client, mundo)
    # Parado a 0,02 (entre a parada A em 0,01 e a escola em 0,03) por mais de 5 min.
    for minutos in (5, 3, 1, 0):
        _gravar(db, mundo["viagem"]["id"], 0.02, minutos)
    db.flush()
    _posicao_redis(mundo, 0.02, velocidade=0)
    criados = alertas.executar_regras(db, AGORA)
    assert _tipos(criados) == ["parada_nao_prevista"]


def test_r9_parado_numa_parada_ou_na_escola_nao_alerta(client, db, mundo):
    _iniciar(client, mundo)
    for lat in (0.01, LAT_ESCOLA):
        db.execute(text("DELETE FROM posicao"))
        for minutos in (5, 3, 0):
            _gravar(db, mundo["viagem"]["id"], lat, minutos)
        db.flush()
        _posicao_redis(mundo, lat, velocidade=0)
        assert alertas.executar_regras(db, AGORA) == []


def test_r9_andando_ou_parado_pouco_tempo_nao_alerta(client, db, mundo):
    _iniciar(client, mundo)
    for minutos, lat in ((5, 0.018), (3, 0.019), (0, 0.020)):  # andando: ~110 m por posição
        _gravar(db, mundo["viagem"]["id"], lat, minutos)
    db.flush()
    _posicao_redis(mundo, 0.02)
    assert alertas.executar_regras(db, AGORA) == []
    db.execute(text("DELETE FROM posicao"))
    for minutos in (2, 1, 0):  # parado, mas só há 2 min
        _gravar(db, mundo["viagem"]["id"], 0.02, minutos)
    db.flush()
    assert alertas.executar_regras(db, AGORA) == []


# R10 velocidade


def test_r10_velocidade_acima_do_limite(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, velocidade=95)
    criados = alertas.executar_regras(db, AGORA)
    assert _tipos(criados) == ["velocidade_acima_do_limite"]
    assert criados[0].dados["velocidade_kmh"] == 95
    assert criados[0].dados["limite_kmh"] == 80


def test_r10_no_limite_nao_alerta(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, velocidade=80)
    assert alertas.executar_regras(db, AGORA) == []


# Limites na tabela


def test_limites_vem_da_tabela_e_mudam_sem_deploy(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, velocidade=60)
    assert alertas.executar_regras(db, AGORA) == []
    db.get(Configuracao, "velocidade_max_kmh").valor = 50
    db.flush()
    assert _tipos(alertas.executar_regras(db, AGORA)) == ["velocidade_acima_do_limite"]


def test_configuracao_so_o_admin_altera(client, db, mundo, cabecalhos):
    corpo = {"valores": {"velocidade_max_kmh": 70}}
    assert (
        client.put("/configuracao/alertas", json=corpo, headers=mundo["gestor"]).status_code == 403
    )
    admin = cabecalhos(Perfil.ADMIN)
    lista = client.put("/configuracao/alertas", json=corpo, headers=admin).json()
    assert {c["chave"]: c["valor"] for c in lista}["velocidade_max_kmh"] == 70
    assert (
        client.put(
            "/configuracao/alertas", json={"valores": {"inventada": 1}}, headers=admin
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/configuracao/alertas", json={"valores": {"sem_sinal_s": -5}}, headers=admin
        ).status_code
        == 422
    )
    assert (
        client.put("/configuracao/alertas", json={"valores": {}}, headers=admin).status_code == 422
    )
    chaves = {
        c["chave"] for c in client.get("/configuracao/alertas", headers=mundo["gestor"]).json()
    }
    assert {"sem_sinal_s", "velocidade_max_kmh", "retencao_posicoes_dias"} <= chaves


# Reconhecer e resolver


def _alerta(client, db, mundo):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.015, velocidade=95)
    [a] = alertas.executar_regras(db, AGORA)
    return a


def test_reconhecer_e_resolver(client, db, mundo):
    alerta = _alerta(client, db, mundo)
    h = mundo["gestor"]
    assert client.get("/alertas", headers=h).json()[0]["situacao"] == "aberto"
    reconhecido = client.post(f"/alertas/{alerta.id}/reconhecer", headers=h).json()
    assert reconhecido["situacao"] == "reconhecido"
    assert reconhecido["reconhecido_por_id"] is not None
    assert [a["id"] for a in client.get("/alertas", headers=h).json()] == [alerta.id]
    resolvido = client.post(f"/alertas/{alerta.id}/resolver", headers=h).json()
    assert resolvido["situacao"] == "resolvido"
    assert resolvido["resolvido_por_id"] is not None
    assert resolvido["resolvido_automaticamente"] is False
    assert client.get("/alertas", headers=h).json() == []
    assert len(client.get("/alertas?abertos=false", headers=h).json()) == 1
    assert client.post(f"/alertas/{alerta.id}/reconhecer", headers=h).status_code == 409


def test_resolver_sem_reconhecer_tambem_reconhece(client, db, mundo):
    alerta = _alerta(client, db, mundo)
    r = client.post(f"/alertas/{alerta.id}/resolver", headers=mundo["gestor"]).json()
    assert r["reconhecido_por_id"] == r["resolvido_por_id"]


def test_filtros_da_lista_e_404(client, db, mundo):
    _alerta(client, db, mundo)
    h = mundo["gestor"]
    assert len(client.get("/alertas?tipo=velocidade_acima_do_limite", headers=h).json()) == 1
    assert client.get("/alertas?tipo=outro", headers=h).json() == []
    assert client.get("/alertas?severidade=critico", headers=h).json() == []
    assert client.get(f"/alertas?viagem_id={mundo['viagem']['id']}", headers=h)
    assert client.post("/alertas/999999/reconhecer", headers=h).status_code == 404


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_alertas_so_para_a_gestao(client, db, mundo, cabecalhos, perfil):
    alerta = _alerta(client, db, mundo)
    h = cabecalhos(perfil)
    assert client.get("/alertas", headers=h).status_code == 403
    assert client.post(f"/alertas/{alerta.id}/resolver", headers=h).status_code == 403
    assert client.get("/configuracao/alertas", headers=h).status_code == 403


# Emergência (R11)


def test_emergencia_cria_alerta_critico_com_posicao_e_avisa_gestores(client, db, mundo, cabecalhos):
    _iniciar(client, mundo)
    _posicao_redis(mundo, 0.012)
    gestor = cabecalhos(Perfil.GESTOR)
    r = client.post(
        f"/viagens/{mundo['viagem']['id']}/emergencia",
        json={"observacao": "Pneu furado"},
        headers=mundo["hm"],
    )
    assert r.status_code == 202
    assert r.json()["gestores_avisados"] >= 2
    [alerta] = client.get("/alertas?severidade=critico", headers=mundo["gestor"]).json()
    assert alerta["tipo"] == "emergencia"
    assert alerta["dados"]["latitude"] == 0.012
    assert alerta["dados"]["observacao"] == "Pneu furado"
    assert gestor
    pendentes = db.scalars(select(Notificacao).where(Notificacao.tipo == "emergencia")).all()
    assert len(pendentes) == r.json()["gestores_avisados"]
    assert all(n.enviada_em is None for n in pendentes)
    assert "AAA1A11" in pendentes[0].mensagem


def test_emergencia_chega_ao_canal_da_frota(client, db, mundo, criar_usuario):
    from starlette.testclient import TestClient  # noqa: F401

    publicadas = []
    original = tempo_real.publicar
    tempo_real.publicar = lambda canal, msg: publicadas.append((canal, msg))
    try:
        _iniciar(client, mundo)
        client.post(f"/viagens/{mundo['viagem']['id']}/emergencia", json={}, headers=mundo["hm"])
    finally:
        tempo_real.publicar = original
    frota = [
        m for c, m in publicadas if c == tempo_real.CANAL_FROTA and m.get("alerta") == "emergencia"
    ]
    assert frota and frota[0]["severidade"] == "critico"


def test_emergencia_nao_duplica_com_toque_duplo(client, db, mundo):
    _iniciar(client, mundo)
    url = f"/viagens/{mundo['viagem']['id']}/emergencia"
    primeira = client.post(url, json={}, headers=mundo["hm"]).json()
    segunda = client.post(url, json={}, headers=mundo["hm"]).json()
    assert segunda["alerta_id"] == primeira["alerta_id"]
    assert segunda["gestores_avisados"] == 0
    assert len(db.scalars(select(Alerta).where(Alerta.tipo == "emergencia")).all()) == 1


def test_emergencia_so_a_equipe_escalada_e_com_viagem_em_andamento(
    client, db, mundo, criar_usuario
):
    url = f"/viagens/{mundo['viagem']['id']}/emergencia"
    assert client.post(url, json={}, headers=mundo["hm"]).status_code == 409  # ainda agendada
    _iniciar(client, mundo)
    assert client.post(url, json={}, headers=_h(criar_usuario(Perfil.MOTORISTA))).status_code == 404
    assert (
        client.post(url, json={}, headers=_h(criar_usuario(Perfil.RESPONSAVEL))).status_code == 403
    )
    assert client.post(url, json={}).status_code == 401


def test_emergencia_avisa_responsaveis_so_se_a_opcao_estiver_ligada(
    client, db, mundo, criar_usuario
):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    db.add(
        ResponsavelEstudante(
            responsavel_id=mae.id,
            estudante_id=mundo["ana"].id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC),
            consentimento_versao=settings.versao_termo_consentimento,
        )
    )
    db.flush()
    _iniciar(client, mundo)
    url = f"/viagens/{mundo['viagem']['id']}/emergencia"
    r = client.post(url, json={}, headers=mundo["hm"]).json()
    assert r["responsaveis_avisados"] == 0
    assert not db.scalars(
        select(Notificacao).where(
            Notificacao.usuario_id == mae.id, Notificacao.tipo == "ocorrencia"
        )
    ).all()

    # O grupo decide ligar: um novo alerta (o anterior é resolvido) avisa as famílias.
    client.post(f"/alertas/{r['alerta_id']}/resolver", headers=mundo["gestor"])
    db.get(Configuracao, "emergencia_avisa_responsaveis").valor = 1
    db.flush()
    r2 = client.post(url, json={}, headers=mundo["hm"]).json()
    assert r2["responsaveis_avisados"] == 1
    aviso = db.scalar(
        select(Notificacao).where(
            Notificacao.usuario_id == mae.id, Notificacao.tipo == "ocorrencia"
        )
    )
    assert "Ana" not in aviso.mensagem
    assert "Souza" not in aviso.mensagem


# Atraso aos responsáveis


def test_atraso_avisa_a_familia_uma_unica_vez(client, db, mundo, criar_usuario):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    db.add(
        ResponsavelEstudante(
            responsavel_id=mae.id,
            estudante_id=mundo["ana"].id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC),
            consentimento_versao=settings.versao_termo_consentimento,
        )
    )
    db.flush()
    _iniciar(client, mundo)
    local = datetime.now(ZoneInfo(settings.fuso_horario))
    quando = local.replace(hour=6, minute=50, second=0, microsecond=0).astimezone(UTC)  # 20 min
    _posicao_redis(mundo, 0.001)
    alertas.executar_regras(db, quando)
    alertas.executar_regras(db, quando)
    atrasos = db.scalars(
        select(Notificacao).where(Notificacao.usuario_id == mae.id, Notificacao.tipo == "atraso")
    ).all()
    assert len(atrasos) == 1
    assert "Ana" in atrasos[0].mensagem and "Souza" not in atrasos[0].mensagem
