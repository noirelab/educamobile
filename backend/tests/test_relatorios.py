"""Relatórios: viagens, pontualidade, ausências e ocorrências, em JSON e CSV."""

import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.config import settings
from app.models import (
    Alerta,
    Auditoria,
    Ausencia,
    Perfil,
    Sentido,
    Severidade,
    StatusAluno,
    StatusViagem,
    Turno,
    Veiculo,
    Viagem,
    ViagemAluno,
    ViagemParada,
)
from app.security import criar_token
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste

HOJE = date.today()
FUSO = ZoneInfo(settings.fuso_horario)


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _local(dia, hora, minuto):
    return datetime.combine(dia, time(hora, minuto), tzinfo=FUSO).astimezone(UTC)


def _viagem(db, rota, dia, status=StatusViagem.CONCLUIDA, **campos):
    v = Viagem(
        rota_id=rota.id,
        data=dia,
        turno=Turno.MANHA,
        sentido=Sentido.IDA,
        escola_id=rota.escola_id,
        status=status,
        **campos,
    )
    db.add(v)
    db.flush()
    return v


def _parada(db, viagem, parada_id, ordem, previsto, chegada=None):
    db.add(
        ViagemParada(
            viagem_id=viagem.id,
            parada_id=parada_id,
            ordem=ordem,
            nome=f"P{ordem}",
            localizacao=from_shape(Point(0.0, 0.01 * ordem), srid=4326),
            horario_previsto=previsto,
            raio_cerca_m=50,
            chegada_em=chegada,
        )
    )
    db.flush()


def _aluno(db, viagem, estudante, status, parada=None, fora=False):
    db.add(
        ViagemAluno(
            viagem_id=viagem.id,
            estudante_id=estudante.id,
            parada_id=parada,
            status=status,
            status_inicial=status,
            fora_da_lista=fora,
        )
    )
    db.flush()


@pytest.fixture
def mundo(db, cabecalhos):
    escola = escola_de_teste(db, "Escola A")
    outra_escola = escola_de_teste(db, "Escola B")
    rota = rota_de_teste(db, "Linha 1", escola_id=escola.id)
    rota_b = rota_de_teste(db, "Linha 2", escola_id=outra_escola.id)
    veiculo = Veiculo(
        placa="AAA1A11", capacidade=40, modelo="V", ano=2020, vistoria_valida_ate=HOJE
    )
    db.add(veiculo)
    db.flush()

    ontem = HOJE - timedelta(days=1)
    v1 = _viagem(
        db,
        rota,
        ontem,
        motorista_id=None,
        veiculo_id=veiculo.id,
        iniciada_em=_local(ontem, 6, 28),
        concluida_em=_local(ontem, 7, 20),
    )
    _parada(db, v1, 1, 0, time(6, 30), chegada=_local(ontem, 6, 33))
    _parada(db, v1, 2, 1, time(7, 10), chegada=_local(ontem, 7, 13))
    ana = estudante_de_teste(db, "Ana Souza", escola_id=escola.id)
    beto = estudante_de_teste(db, "Beto Lima", escola_id=escola.id)
    carla = estudante_de_teste(db, "Carla Dias", escola_id=escola.id)
    extra = estudante_de_teste(db, "Extra", escola_id=escola.id)
    _aluno(db, v1, ana, StatusAluno.DESEMBARCOU)
    _aluno(db, v1, beto, StatusAluno.NAO_EMBARCOU)
    _aluno(db, v1, carla, StatusAluno.AUSENCIA_AVISADA)
    _aluno(db, v1, extra, StatusAluno.DESEMBARCOU, fora=True)

    atrasada = _viagem(
        db,
        rota,
        HOJE - timedelta(days=3),
        iniciada_em=_local(HOJE - timedelta(days=3), 6, 45),
        concluida_em=_local(HOJE - timedelta(days=3), 7, 50),
    )
    _parada(db, atrasada, 1, 0, time(6, 30), chegada=_local(HOJE - timedelta(days=3), 6, 50))
    _parada(db, atrasada, 2, 1, time(7, 10), chegada=_local(HOJE - timedelta(days=3), 7, 30))

    b = _viagem(db, rota_b, ontem, status=StatusViagem.CANCELADA)
    antiga = _viagem(db, rota, HOJE - timedelta(days=200))

    db.add(Ausencia(estudante_id=carla.id, data=ontem))
    db.add(Ausencia(estudante_id=carla.id, data=HOJE - timedelta(days=2)))
    db.add(Ausencia(estudante_id=ana.id, data=HOJE - timedelta(days=300)))
    alerta = Alerta(
        viagem_id=v1.id,
        tipo="sem_sinal",
        severidade=Severidade.AVISO,
        mensagem="Sem sinal",
        criado_em=_local(ontem, 6, 40),
        reconhecido_em=_local(ontem, 6, 45),
        resolvido_em=_local(ontem, 6, 52),
    )
    db.add(alerta)
    db.add(Alerta(viagem_id=v1.id, tipo="emergencia", severidade=Severidade.CRITICO, mensagem="X"))
    db.add(Alerta(viagem_id=b.id, tipo="sem_sinal", severidade=Severidade.AVISO, mensagem="B"))
    db.flush()
    return {
        "gestor": cabecalhos(Perfil.GESTOR),
        "rota": rota,
        "rota_b": rota_b,
        "escola": escola,
        "outra": outra_escola,
        "v1": v1,
        "atrasada": atrasada,
        "antiga": antiga,
        "ana": ana,
        "carla": carla,
        "beto": beto,
    }


def _get(client, m, caminho, **params):
    r = client.get(f"/relatorios/{caminho}", params=params, headers=m["gestor"])
    assert r.status_code == 200, r.text
    return r.json()


# Viagens


def test_relatorio_de_viagens_conta_cada_situacao(client, mundo):
    r = _get(client, mundo, "viagens")
    por_id = {x["viagem_id"]: x for x in r["linhas"]}
    v1 = por_id[mundo["v1"].id]
    assert v1["status"] == "concluida"
    assert v1["placa"] == "AAA1A11"
    assert v1["duracao_min"] == 52
    assert v1["alunos_na_lista"] == 4
    assert v1["embarcaram"] == 2
    assert v1["nao_embarcaram"] == 1
    assert v1["ausencias_avisadas"] == 1
    assert v1["fora_da_lista"] == 1
    assert mundo["antiga"].id not in por_id  # fora do período padrão de 30 dias
    assert r["resumo"]["viagens"] == 3
    assert r["resumo"]["por_status"] == {"concluida": 2, "cancelada": 1}


def test_filtros_de_periodo_rota_e_escola(client, mundo):
    ids = lambda r: {x["viagem_id"] for x in r["linhas"]}  # noqa: E731
    amplo = _get(client, mundo, "viagens", de=(HOJE - timedelta(days=250)).isoformat())
    assert mundo["antiga"].id in ids(amplo)
    assert ids(_get(client, mundo, "viagens", rota_id=mundo["rota_b"].id)) == {
        v
        for v in ids(_get(client, mundo, "viagens"))
        if v not in (mundo["v1"].id, mundo["atrasada"].id)
    }
    so_a = _get(client, mundo, "viagens", escola_id=mundo["escola"].id)
    assert mundo["v1"].id in ids(so_a) and len(ids(so_a)) == 2
    ate_ontem = _get(client, mundo, "viagens", ate=(HOJE - timedelta(days=2)).isoformat())
    assert ids(ate_ontem) == {mundo["atrasada"].id}


@pytest.mark.parametrize(
    "params",
    [
        {"de": "2026-02-01", "ate": "2026-01-01"},
        {"de": "2020-01-01", "ate": "2026-01-01"},
        {"de": "ontem"},
        {"rota_id": 0},
        {"formato": "xml"},
    ],
)
def test_filtros_invalidos_dao_422(client, mundo, params):
    r = client.get("/relatorios/viagens", params=params, headers=mundo["gestor"])
    assert r.status_code == 422


# Pontualidade


def test_pontualidade_mede_o_atraso_na_chegada_a_escola(client, mundo):
    r = _get(client, mundo, "pontualidade")
    por_id = {x["viagem_id"]: x for x in r["linhas"]}
    ok = por_id[mundo["v1"].id]
    assert (ok["atraso_saida_min"], ok["atraso_chegada_min"], ok["no_horario"]) == (-2, 3, True)
    tarde = por_id[mundo["atrasada"].id]
    assert (tarde["atraso_saida_min"], tarde["atraso_chegada_min"], tarde["no_horario"]) == (
        15,
        20,
        False,
    )
    assert mundo["antiga"].id not in por_id  # sem paradas copiadas: nada a medir
    assert r["resumo"] == {
        "viagens_medidas": 2,
        "no_horario": 1,
        "percentual_no_horario": 50.0,
        "atraso_medio_chegada_min": 11.5,
        "tolerancia_min": 5,
    }


def test_pontualidade_sem_dados_nao_divide_por_zero(client, mundo):
    r = _get(client, mundo, "pontualidade", rota_id=mundo["rota_b"].id)
    assert r["linhas"] == []
    assert r["resumo"]["percentual_no_horario"] is None


# Ausências


def test_ausencias_somam_avisos_e_faltas_sem_aviso(client, mundo):
    r = _get(client, mundo, "ausencias")
    linhas = {x["nome"]: x for x in r["linhas"]}
    assert linhas["Carla Dias"]["ausencias_avisadas"] == 2
    assert linhas["Beto Lima"]["nao_embarcou_sem_aviso"] == 1
    assert linhas["Ana Souza"]["ausencias_avisadas"] == 0  # a de 300 dias atrás ficou de fora
    assert r["linhas"][0]["nome"] == "Carla Dias"  # a que mais faltou, primeiro
    assert r["resumo"]["ausencias_avisadas"] == 2
    assert r["resumo"]["nao_embarcou_sem_aviso"] == 1
    assert "data_nascimento" not in str(r)


def test_ausencias_filtradas_por_escola(client, mundo):
    assert _get(client, mundo, "ausencias", escola_id=mundo["outra"].id)["linhas"] == []


# Ocorrências


def test_ocorrencias_com_tempos_de_resposta(client, mundo):
    r = _get(client, mundo, "ocorrencias")
    por_tipo = {x["tipo"]: x for x in r["linhas"]}
    sem_sinal = next(x for x in r["linhas"] if x["mensagem"] == "Sem sinal")
    assert sem_sinal["minutos_ate_reconhecer"] == 5
    assert sem_sinal["minutos_ate_resolver"] == 12
    assert sem_sinal["situacao"] == "resolvido"
    assert por_tipo["emergencia"]["situacao"] == "aberto"
    assert r["resumo"]["ocorrencias"] == 3
    assert r["resumo"]["criticas"] == 1
    assert r["resumo"]["por_tipo"] == {"sem_sinal": 2, "emergencia": 1}
    so_a = _get(client, mundo, "ocorrencias", escola_id=mundo["escola"].id)
    assert so_a["resumo"]["ocorrencias"] == 2


# CSV e auditoria


@pytest.mark.parametrize("nome", ["viagens", "pontualidade", "ausencias", "ocorrencias"])
def test_exportacao_csv_e_registrada_na_auditoria(client, db, mundo, nome):
    r = client.get(f"/relatorios/{nome}", params={"formato": "csv"}, headers=mundo["gestor"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f"{nome}-" in r.headers["content-disposition"]
    assert "attachment" in r.headers["content-disposition"]
    linhas = list(csv.reader(io.StringIO(r.text)))
    json_linhas = _get(client, mundo, nome)["linhas"]
    assert len(linhas) - 1 == len(json_linhas)
    assert linhas[0] == list(json_linhas[0].keys())
    registro = db.scalar(
        select(Auditoria).where(
            Auditoria.acao == "relatorio.exportar", Auditoria.recurso_id == nome
        )
    )
    assert registro is not None
    assert registro.detalhes["linhas"] == len(json_linhas)
    assert registro.detalhes["filtros"]["rota_id"] is None


def test_json_nao_gera_registro_de_exportacao(client, db, mundo):
    _get(client, mundo, "viagens")
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "relatorio.exportar")) is None


def test_csv_vazio_e_so_o_corpo_vazio(client, mundo):
    r = client.get(
        "/relatorios/viagens", params={"formato": "csv", "rota_id": 999999}, headers=mundo["gestor"]
    )
    assert r.status_code == 200 and r.text == ""


def test_csv_nao_vira_formula_na_planilha(client, db, mundo):
    mundo["carla"].nome = '=HYPERLINK("http://mal.example","clique")'
    db.flush()
    r = client.get("/relatorios/ausencias", params={"formato": "csv"}, headers=mundo["gestor"])
    celulas = [c for linha in csv.reader(io.StringIO(r.text)) for c in linha]
    assert '\'=HYPERLINK("http://mal.example","clique")' in celulas
    assert not any(c.startswith("=") for c in celulas)


# Permissões


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_relatorios_so_para_a_gestao(client, mundo, cabecalhos, perfil):
    for nome in ("viagens", "pontualidade", "ausencias", "ocorrencias"):
        assert client.get(f"/relatorios/{nome}", headers=cabecalhos(perfil)).status_code == 403
    assert client.get("/relatorios/viagens").status_code == 401


def test_csv_nao_estraga_numero_negativo(client, mundo):
    r = client.get("/relatorios/pontualidade", params={"formato": "csv"}, headers=mundo["gestor"])
    celulas = [c for linha in csv.reader(io.StringIO(r.text)) for c in linha]
    assert "-2" in celulas
    assert "'-2" not in celulas


def test_ausencias_por_rota_nao_traz_aluno_de_outra_rota(client, mundo):
    r = _get(client, mundo, "ausencias", rota_id=mundo["rota_b"].id)
    assert r["linhas"] == []


def test_ausencia_avisada_depois_da_saida_conta_como_ausencia_avisada(client, db, mundo):
    """O motorista confirma `nao_embarcou`, mas a família tinha avisado: não é falta sem aviso."""
    aluno = db.scalar(
        select(ViagemAluno).where(
            ViagemAluno.viagem_id == mundo["v1"].id,
            ViagemAluno.status == StatusAluno.NAO_EMBARCOU,
        )
    )
    aluno.ausencia_avisada_em = datetime.now(UTC)
    db.flush()
    v1 = next(
        x for x in _get(client, mundo, "viagens")["linhas"] if x["viagem_id"] == mundo["v1"].id
    )
    assert v1["nao_embarcaram"] == 0
    assert v1["ausencias_avisadas"] == 2
