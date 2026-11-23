"""Viagem do dia: geração, início (R1), lista, eventos, correções, conclusão (R2) e cancelamento."""

import io
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.geo import Coordenadas
from app.models import (
    Alerta,
    Ausencia,
    EventoViagem,
    Inscricao,
    Motorista,
    Notificacao,
    Perfil,
    ResponsavelEstudante,
    Sentido,
    StatusViagem,
    Turno,
    Veiculo,
    Viagem,
    ViagemAluno,
)
from app.security import criar_token
from app.viagens import verificar_saida_da_cerca
from tests.conftest import escola_de_teste, estudante_de_teste, rota_de_teste
from tests.test_rotas import _parada

HOJE = date.today()
AGORA = datetime.now(UTC)


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def _hora(minutos):
    """Hora do aparelho, `minutos` depois do início fictício (sempre no passado)."""
    return (AGORA - timedelta(hours=2) + timedelta(minutes=minutos)).isoformat()


def _ev(tipo, estudante=None, minutos=0, **extra):
    corpo = {"id": str(uuid.uuid4()), "tipo": tipo, "hora_aparelho": _hora(minutos), **extra}
    if estudante is not None:
        corpo["estudante_id"] = estudante.id
    return corpo


@pytest.fixture
def mundo(client, db, cabecalhos, criar_usuario):
    """Rota de ida com duas crianças, motorista habilitado, veículo em dia e monitor."""
    escola = escola_de_teste(db, "Escola", 0.0, 0.0, raio_cerca_m=150)
    a, b = _parada(db, 0.01, nome="A"), _parada(db, 0.02, nome="B")
    na_escola = _parada(db, 0.0001, nome="Escola")
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
    ok = client.put(
        f"/rotas/{rota.id}/paradas", json={"parada_ids": [a.id, b.id, na_escola.id]}, headers=gestor
    )
    assert ok.status_code == 200, ok.text
    ana = estudante_de_teste(db, "Ana", escola_id=escola.id, observacoes_cuidado="Alergia")
    beto = estudante_de_teste(db, "Beto", escola_id=escola.id)
    for estudante, parada in ((ana, a), (beto, b)):
        db.add(
            Inscricao(
                estudante_id=estudante.id,
                rota_id=rota.id,
                parada_id=parada.id,
                turno=Turno.MANHA,
                sentido=Sentido.IDA,
                dias_semana=[0, 1, 2, 3, 4, 5, 6],
                vigencia_inicio=HOJE,
            )
        )
    monitor = criar_usuario(Perfil.MONITOR)
    db.flush()
    return {
        "escola": escola,
        "rota": rota,
        "a": a,
        "b": b,
        "na_escola": na_escola,
        "ana": ana,
        "beto": beto,
        "motorista": motorista,
        "monitor": monitor,
        "veiculo": veiculo,
        "gestor": gestor,
        "hm": _h(motorista),
        "hmon": _h(monitor),
    }


def _gerar(client, m, **corpo):
    r = client.post("/viagens/gerar", json={"rota_id": m["rota"].id, **corpo}, headers=m["gestor"])
    assert r.status_code == 201, r.text
    return r.json()[0]


def _iniciar(client, m, viagem):
    return client.post(f"/viagens/{viagem['id']}/iniciar", headers=m["hm"])


@pytest.fixture
def em_andamento(client, mundo):
    viagem = _gerar(client, mundo)
    client.patch(
        f"/viagens/{viagem['id']}/escala",
        json={"monitor_id": mundo["monitor"].id},
        headers=mundo["gestor"],
    )
    assert _iniciar(client, mundo, viagem).status_code == 200
    return viagem


def _eventos(client, m, viagem, *eventos, quem="hm"):
    return client.post(
        f"/viagens/{viagem['id']}/eventos", json={"eventos": list(eventos)}, headers=m[quem]
    )


def _status(client, m, viagem):
    lista = client.get(f"/viagens/{viagem['id']}/lista", headers=m["hm"]).json()
    return {a["nome"]: a["status"] for a in lista["alunos"]}


# Geração


def test_gerar_cria_a_viagem_do_dia_e_nao_duplica(client, db, mundo):
    viagem = _gerar(client, mundo)
    assert viagem["status"] == "agendada"
    assert viagem["data"] == HOJE.isoformat()
    assert viagem["motorista_id"] == mundo["motorista"].id
    assert viagem["veiculo_id"] == mundo["veiculo"].id
    assert _gerar(client, mundo)["id"] == viagem["id"]
    assert db.scalar(select(text("count(*)")).select_from(Viagem)) == 1


def test_rota_sem_inscritos_nao_gera_viagem(client, db, mundo):
    vazia = rota_de_teste(db, "Vazia")
    r = client.post("/viagens/gerar", json={"rota_id": vazia.id}, headers=mundo["gestor"])
    assert r.json() == []


def test_inscricao_fora_da_vigencia_ou_do_dia_da_semana_nao_conta(client, db, mundo):
    amanha = HOJE + timedelta(days=1)
    for i in db.scalars(select(Inscricao)):
        i.vigencia_inicio = amanha
    db.flush()
    assert (
        client.post(
            "/viagens/gerar", json={"rota_id": mundo["rota"].id}, headers=mundo["gestor"]
        ).json()
        == []
    )
    outro_dia = client.post(
        "/viagens/gerar",
        json={"rota_id": mundo["rota"].id, "data": amanha.isoformat()},
        headers=mundo["gestor"],
    )
    assert len(outro_dia.json()) == 1
    for i in db.scalars(select(Inscricao)):
        i.dias_semana = [(amanha.weekday() + 1) % 7]
    db.flush()
    outra = client.post(
        "/viagens/gerar",
        json={"rota_id": mundo["rota"].id, "data": (amanha + timedelta(days=0)).isoformat()},
        headers=mundo["gestor"],
    )
    assert len(outra.json()) == 1  # já existia: devolve a mesma


def test_so_a_gestao_gera_e_lista(client, mundo, cabecalhos):
    for perfil in (Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL):
        h = cabecalhos(perfil)
        assert client.post("/viagens/gerar", json={}, headers=h).status_code == 403
        assert client.get("/viagens", headers=h).status_code == 403
    assert client.post("/viagens/gerar", json={}).status_code == 401


def test_listar_com_filtros(client, mundo):
    viagem = _gerar(client, mundo)
    h = mundo["gestor"]
    assert [v["id"] for v in client.get(f"/viagens?data={HOJE}", headers=h).json()] == [
        viagem["id"]
    ]
    assert client.get("/viagens?situacao=concluida", headers=h).json() == []


# Início (R1)


def test_inicia_com_tudo_em_dia_e_copia_a_lista(client, mundo):
    viagem = _gerar(client, mundo)
    r = _iniciar(client, mundo, viagem)
    assert r.status_code == 200
    assert r.json()["status"] == "em_andamento"
    assert r.json()["totais"]["aguardando"] == 2
    lista = client.get(f"/viagens/{viagem['id']}/lista", headers=mundo["hm"]).json()
    assert [(a["nome"], a["parada_nome"]) for a in lista["alunos"]] == [("Ana", "A"), ("Beto", "B")]
    assert [p["nome"] for p in lista["paradas"]] == ["A", "B", "Escola"]


@pytest.mark.parametrize(
    ("mexer", "motivo"),
    [
        (
            lambda m, db: setattr(
                db.get(Motorista, m["motorista"].id), "cnh_valida_ate", HOJE - timedelta(days=1)
            ),
            "CNH vencida",
        ),
        (
            lambda m, db: setattr(
                db.get(Motorista, m["motorista"].id),
                "curso_transporte_escolar_ate",
                HOJE - timedelta(days=1),
            ),
            "Curso de transporte escolar vencido",
        ),
        (
            lambda m, db: setattr(db.get(Motorista, m["motorista"].id), "categoria_cnh", "B"),
            "Categoria da CNH não permite transporte escolar",
        ),
        (
            lambda m, db: setattr(m["veiculo"], "vistoria_valida_ate", HOJE - timedelta(days=1)),
            "Vistoria do veículo vencida",
        ),
        (lambda m, db: setattr(m["veiculo"], "ativo", False), "Veículo inativo"),
        (lambda m, db: setattr(m["motorista"], "ativo", False), "Conta desativada"),
    ],
)
def test_recusa_o_inicio_dizendo_o_motivo(client, db, mundo, mexer, motivo):
    viagem = _gerar(client, mundo)
    mexer(mundo, db)
    db.flush()
    r = client.post(
        f"/viagens/{viagem['id']}/iniciar",
        headers=_h(mundo["motorista"]) if motivo != "Conta desativada" else mundo["gestor"],
    )
    assert r.status_code == 422
    assert motivo in r.json()["detail"]["motivos"]
    assert db.get(Viagem, viagem["id"]).status == StatusViagem.AGENDADA


def test_recusa_sem_motorista_ou_veiculo_escalado(client, db, mundo):
    viagem = _gerar(client, mundo)
    client.patch(
        f"/viagens/{viagem['id']}/escala",
        json={"motorista_id": None, "veiculo_id": None},
        headers=mundo["gestor"],
    )
    r = client.post(f"/viagens/{viagem['id']}/iniciar", headers=mundo["gestor"])
    assert r.status_code == 422
    assert r.json()["detail"]["motivos"] == ["Sem motorista escalado", "Sem veículo escalado"]


def test_so_inicia_no_proprio_dia_e_uma_vez(client, mundo):
    amanha = (HOJE + timedelta(days=1)).isoformat()
    viagem = _gerar(client, mundo, data=amanha)
    assert (
        client.post(f"/viagens/{viagem['id']}/iniciar", headers=mundo["gestor"]).status_code == 409
    )
    hoje = _gerar(client, mundo)
    assert _iniciar(client, mundo, hoje).status_code == 200
    assert _iniciar(client, mundo, hoje).status_code == 409


def test_ausencia_avisada_entra_como_ausencia_avisada(client, db, mundo):
    viagem = _gerar(client, mundo)
    db.add(Ausencia(estudante_id=mundo["ana"].id, data=HOJE, sentido=None))
    db.add(Ausencia(estudante_id=mundo["beto"].id, data=HOJE, sentido=Sentido.VOLTA))
    db.flush()
    _iniciar(client, mundo, viagem)
    # A de Beto era da volta: na ida ele continua esperado.
    assert _status(client, mundo, viagem) == {"Ana": "ausencia_avisada", "Beto": "aguardando"}


def test_mudar_a_rota_durante_a_viagem_nao_muda_a_lista(client, db, mundo):
    viagem = _gerar(client, mundo)
    _iniciar(client, mundo, viagem)
    antes = client.get(f"/viagens/{viagem['id']}/lista", headers=mundo["hm"]).json()

    # O gestor mexe nas inscrições, renomeia a parada e troca a sequência no meio da viagem.
    client.put(
        f"/rotas/{mundo['rota'].id}/inscricoes", json={"inscricoes": []}, headers=mundo["gestor"]
    )
    client.patch(f"/paradas/{mundo['a'].id}", json={"nome": "Renomeada"}, headers=mundo["gestor"])
    client.put(
        f"/rotas/{mundo['rota'].id}/paradas",
        json={"parada_ids": [mundo["b"].id, mundo["na_escola"].id]},
        headers=mundo["gestor"],
    )
    db.add(Ausencia(estudante_id=mundo["ana"].id, data=HOJE + timedelta(days=1)))
    db.flush()

    depois = client.get(f"/viagens/{viagem['id']}/lista", headers=mundo["hm"]).json()
    assert depois["alunos"] == antes["alunos"]
    assert depois["paradas"] == antes["paradas"]


# Escala e acesso


def test_so_o_motorista_escalado_alcanca_a_viagem(client, db, mundo, criar_usuario):
    viagem = _gerar(client, mundo)
    url = f"/viagens/{viagem['id']}"
    outro = _h(criar_usuario(Perfil.MOTORISTA))
    assert client.get(url, headers=outro).status_code == 404
    assert client.get(f"{url}/lista", headers=outro).status_code == 404
    assert client.post(f"{url}/iniciar", headers=outro).status_code == 404
    assert client.get(url, headers=mundo["hm"]).status_code == 200
    # Monitor não escalado também não vê.
    assert client.get(url, headers=mundo["hmon"]).status_code == 404


def test_monitor_escalado_ve_mas_nao_inicia(client, mundo):
    viagem = _gerar(client, mundo)
    client.patch(
        f"/viagens/{viagem['id']}/escala",
        json={"monitor_id": mundo["monitor"].id},
        headers=mundo["gestor"],
    )
    assert client.get(f"/viagens/{viagem['id']}", headers=mundo["hmon"]).status_code == 200
    assert client.post(f"/viagens/{viagem['id']}/iniciar", headers=mundo["hmon"]).status_code == 404


def test_viagem_de_outro_dia_some_para_a_equipe_mas_nao_para_a_gestao(client, db, mundo):
    viagem = _gerar(client, mundo)
    db.get(Viagem, viagem["id"]).data = HOJE - timedelta(days=3)
    db.flush()
    assert client.get(f"/viagens/{viagem['id']}", headers=mundo["hm"]).status_code == 404
    assert client.get(f"/viagens/{viagem['id']}", headers=mundo["gestor"]).status_code == 200


def test_escala_valida_monitor_motorista_e_veiculo(client, db, mundo, criar_usuario):
    viagem = _gerar(client, mundo)
    url = f"/viagens/{viagem['id']}/escala"
    h = mundo["gestor"]
    assert (
        client.patch(url, json={"monitor_id": mundo["motorista"].id}, headers=h).status_code == 422
    )
    assert (
        client.patch(
            url, json={"motorista_id": criar_usuario(Perfil.MOTORISTA).id}, headers=h
        ).status_code
        == 422
    )
    assert client.patch(url, json={"veiculo_id": 999999}, headers=h).status_code == 422
    assert client.patch(url, json={}, headers=h).status_code == 422
    _iniciar(client, mundo, viagem)
    assert client.patch(url, json={"monitor_id": None}, headers=h).status_code == 409


def test_viagens_de_hoje_do_motorista(client, db, mundo):
    viagem = _gerar(client, mundo)
    assert [v["id"] for v in client.get("/motorista/viagens-hoje", headers=mundo["hm"]).json()] == [
        viagem["id"]
    ]
    assert client.get("/motorista/viagens-hoje", headers=mundo["hmon"]).json() == []
    client.patch(
        f"/viagens/{viagem['id']}/escala",
        json={"monitor_id": mundo["monitor"].id},
        headers=mundo["gestor"],
    )
    assert len(client.get("/motorista/viagens-hoje", headers=mundo["hmon"]).json()) == 1


# Lista


def test_lista_nao_expoe_nascimento_nem_endereco_e_traz_cuidados_e_foto(client, db, mundo):
    imagem = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(imagem, "JPEG")
    settings.fotos_dir = str(__import__("pathlib").Path(__import__("tempfile").mkdtemp()))
    client.put(
        f"/estudantes/{mundo['ana'].id}/foto",
        files={"foto": ("f.jpg", imagem.getvalue(), "image/jpeg")},
        headers=mundo["gestor"],
    )
    viagem = _gerar(client, mundo)
    _iniciar(client, mundo, viagem)
    lista = client.get(f"/viagens/{viagem['id']}/lista", headers=mundo["hm"])
    texto = lista.text
    for proibido in (
        "data_nascimento",
        "2015-01-01",
        "localizacao_casa",
        "endereco",
        "nome_responsavel",
    ):
        assert proibido not in texto
    ana = next(a for a in lista.json()["alunos"] if a["nome"] == "Ana")
    assert ana["observacoes_cuidado"] == "Alergia"
    assert ana["foto_url"].startswith("/fotos/")
    assert client.get(ana["foto_url"]).status_code == 200


# Eventos


def test_embarque_e_desembarque_mudam_o_status(client, mundo, em_andamento):
    r = _eventos(
        client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1, parada_id=mundo["a"].id)
    )
    assert [x["resultado"] for x in r.json()] == ["aceito"]
    assert _status(client, mundo, em_andamento)["Ana"] == "embarcou"
    _eventos(client, mundo, em_andamento, _ev("desembarque", mundo["ana"], 30))
    _eventos(client, mundo, em_andamento, _ev("nao_embarcou", mundo["beto"], 5))
    assert _status(client, mundo, em_andamento) == {"Ana": "desembarcou", "Beto": "nao_embarcou"}


def test_reenviar_o_mesmo_evento_nao_duplica(client, db, mundo, em_andamento):
    e = _ev("embarque", mundo["ana"], 1)
    assert _eventos(client, mundo, em_andamento, e).json()[0]["resultado"] == "aceito"
    assert _eventos(client, mundo, em_andamento, e).json()[0]["resultado"] == "duplicado"
    assert db.scalar(select(text("count(*)")).select_from(EventoViagem)) == 1


def test_lote_com_evento_novo_e_repetido(client, mundo, em_andamento):
    primeiro = _ev("embarque", mundo["ana"], 1)
    _eventos(client, mundo, em_andamento, primeiro)
    r = _eventos(client, mundo, em_andamento, primeiro, _ev("embarque", mundo["beto"], 2))
    assert [x["resultado"] for x in r.json()] == ["duplicado", "aceito"]


def test_eventos_fora_de_ordem_terminam_no_estado_certo(client, mundo, em_andamento):
    # Offline: o desembarque (07:30) chega antes do embarque (07:00).
    _eventos(client, mundo, em_andamento, _ev("desembarque", mundo["ana"], 30))
    assert _status(client, mundo, em_andamento)["Ana"] == "desembarcou"
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 0))
    assert _status(client, mundo, em_andamento)["Ana"] == "desembarcou"
    # Um embarque mais tardio que o desembarque reabre a criança a bordo.
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 45))
    assert _status(client, mundo, em_andamento)["Ana"] == "embarcou"


def test_aluno_fora_da_lista_exige_justificativa(client, db, mundo, em_andamento):
    intruso = estudante_de_teste(db, "Intruso", escola_id=mundo["escola"].id)
    r = _eventos(client, mundo, em_andamento, _ev("embarque", intruso, 1))
    assert r.json()[0]["resultado"] == "rejeitado"
    assert "fora da lista" in r.json()[0]["motivo"]
    sem = _eventos(client, mundo, em_andamento, _ev("embarque_fora_da_lista", intruso, 2))
    assert sem.json()[0]["resultado"] == "rejeitado"
    assert _status(client, mundo, em_andamento).get("Intruso") is None


def test_embarque_fora_da_lista_entra_na_lista_e_avisa_a_gestao(client, db, mundo, em_andamento):
    intruso = estudante_de_teste(db, "Intruso", escola_id=mundo["escola"].id)
    r = _eventos(
        client,
        mundo,
        em_andamento,
        _ev(
            "embarque_fora_da_lista",
            intruso,
            1,
            parada_id=mundo["a"].id,
            justificativa="Troca de carona autorizada",
        ),
    )
    assert r.json()[0]["resultado"] == "aceito"
    lista = client.get(f"/viagens/{em_andamento['id']}/lista", headers=mundo["hm"]).json()
    extra = next(a for a in lista["alunos"] if a["nome"] == "Intruso")
    assert extra["fora_da_lista"] is True
    assert extra["status"] == "embarcou"
    alertas = client.get("/alertas", headers=mundo["gestor"]).json()
    assert [a["tipo"] for a in alertas] == ["aluno_fora_da_lista"]


def test_parada_errada_e_registro_longe_sao_aceitos_mas_sinalizados(client, mundo, em_andamento):
    errada = _eventos(
        client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1, parada_id=mundo["b"].id)
    )
    assert errada.json()[0]["anomalia"] == "parada_errada"
    # Beto tem a parada B (0.02,0); o toque veio de 5 km dali.
    longe = _eventos(
        client,
        mundo,
        em_andamento,
        _ev("embarque", mundo["beto"], 2, localizacao={"latitude": 0.07, "longitude": 0.0}),
    )
    assert longe.json()[0]["anomalia"] == "longe_da_parada"
    perto = _eventos(
        client,
        mundo,
        em_andamento,
        _ev("desembarque", mundo["beto"], 3, localizacao={"latitude": 0.0201, "longitude": 0.0}),
    )
    assert perto.json()[0]["anomalia"] is None
    tipos = {a["tipo"] for a in client.get("/alertas", headers=mundo["gestor"]).json()}
    assert tipos == {"registro_anomalo"}


def test_hora_no_futuro_e_sem_fuso_e_lote_grande_sao_recusados(client, mundo, em_andamento):
    futuro = _ev("embarque", mundo["ana"])
    futuro["hora_aparelho"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert _eventos(client, mundo, em_andamento, futuro).json()[0]["resultado"] == "rejeitado"
    sem_fuso = _ev("embarque", mundo["ana"])
    sem_fuso["hora_aparelho"] = "2026-11-23T07:00:00"
    assert _eventos(client, mundo, em_andamento, sem_fuso).status_code == 422
    muitos = [_ev("onibus_vazio", minutos=i) for i in range(201)]
    assert _eventos(client, mundo, em_andamento, *muitos).status_code == 422
    assert (
        client.post(
            f"/viagens/{em_andamento['id']}/eventos", json={"eventos": []}, headers=mundo["hm"]
        ).status_code
        == 422
    )


def test_correcao_nao_passa_pelo_lote_de_eventos(client, mundo, em_andamento):
    r = _eventos(client, mundo, em_andamento, _ev("correcao", mundo["ana"], 1))
    assert r.json()[0]["resultado"] == "rejeitado"


def test_eventos_so_com_a_viagem_em_andamento(client, mundo):
    viagem = _gerar(client, mundo)
    assert _eventos(client, mundo, viagem, _ev("onibus_vazio")).status_code == 409


def test_monitor_tambem_registra_eventos(client, mundo, em_andamento):
    r = _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1), quem="hmon")
    assert r.json()[0]["resultado"] == "aceito"
    eventos = client.get(f"/viagens/{em_andamento['id']}/eventos", headers=mundo["gestor"]).json()
    assert eventos[0]["autor_id"] == mundo["monitor"].id


def test_equipe_sincroniza_eventos_do_dia_anterior_mas_nao_le_a_lista(
    client, db, mundo, em_andamento
):
    db.get(Viagem, em_andamento["id"]).data = HOJE - timedelta(days=1)
    db.flush()
    assert (
        _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1)).status_code == 200
    )
    assert (
        client.get(f"/viagens/{em_andamento['id']}/lista", headers=mundo["hm"]).status_code == 404
    )
    db.get(Viagem, em_andamento["id"]).data = HOJE - timedelta(days=2)
    db.flush()
    assert (
        _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 2)).status_code == 404
    )


# Imutabilidade e correções (R13)


def test_evento_nao_se_altera_nem_se_apaga_nem_pelo_banco(client, db, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    for sql in ("UPDATE evento_viagem SET tipo = 'desembarque'", "DELETE FROM evento_viagem"):
        with pytest.raises(DBAPIError, match="só de inclusão"), db.begin_nested():
            db.execute(text(sql))
    assert db.scalar(select(text("count(*)")).select_from(EventoViagem)) == 1


def test_gestor_corrige_com_motivo_e_o_historico_fica(client, db, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    url = f"/viagens/{em_andamento['id']}/correcoes"
    corpo = {
        "estudante_id": mundo["ana"].id,
        "status": "nao_embarcou",
        "motivo": "Toque errado no aparelho",
    }
    r = client.post(url, json=corpo, headers=mundo["gestor"])
    assert r.status_code == 201
    assert _status(client, mundo, em_andamento)["Ana"] == "nao_embarcou"
    eventos = client.get(f"/viagens/{em_andamento['id']}/eventos", headers=mundo["gestor"]).json()
    assert [e["tipo"] for e in eventos] == ["embarque", "correcao"]
    assert eventos[1]["justificativa"] == "Toque errado no aparelho"
    assert eventos[1]["status_corrigido"] == "nao_embarcou"
    assert eventos[1]["autor_id"] is not None


def test_correcao_so_pelo_gestor_com_motivo_e_aluno_da_lista(client, db, mundo, em_andamento):
    url = f"/viagens/{em_andamento['id']}/correcoes"
    corpo = {
        "estudante_id": mundo["ana"].id,
        "status": "desembarcou",
        "motivo": "Confirmado por ligação",
    }
    assert client.post(url, json=corpo, headers=mundo["hm"]).status_code == 403
    assert (
        client.post(url, json={**corpo, "motivo": "ok"}, headers=mundo["gestor"]).status_code == 422
    )
    fora = estudante_de_teste(db, "Fora", escola_id=mundo["escola"].id)
    assert (
        client.post(
            url, json={**corpo, "estudante_id": fora.id}, headers=mundo["gestor"]
        ).status_code
        == 404
    )


def test_evento_posterior_vence_a_correcao_anterior(client, mundo, em_andamento):
    url = f"/viagens/{em_andamento['id']}/correcoes"
    client.post(
        url,
        json={
            "estudante_id": mundo["ana"].id,
            "status": "nao_embarcou",
            "motivo": "Falta confirmada",
        },
        headers=mundo["gestor"],
    )
    # Evento do aparelho com hora anterior à correção não a derruba.
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    assert _status(client, mundo, em_andamento)["Ana"] == "nao_embarcou"


# Conclusão (R2)


def _tudo_resolvido(client, m, viagem):
    _eventos(client, m, viagem, _ev("embarque", m["ana"], 1), _ev("embarque", m["beto"], 2))
    _eventos(client, m, viagem, _ev("desembarque", m["ana"], 30), _ev("desembarque", m["beto"], 31))
    _eventos(client, m, viagem, _ev("onibus_vazio", minutos=40))


def test_conclui_quando_todos_tem_destino_e_o_onibus_esta_vazio(client, mundo, em_andamento):
    _tudo_resolvido(client, mundo, em_andamento)
    r = client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    assert r.status_code == 200
    assert r.json()["viagem"]["status"] == "concluida"
    assert r.json()["viagem"]["concluida_em"] is not None


def test_nao_conclui_com_crianca_sem_registro_e_diz_quem(client, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("onibus_vazio", minutos=40))
    r = client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    assert r.status_code == 409
    assert r.json()["detail"]["pendencias"] == ["Ana: sem registro", "Beto: sem registro"]


def test_nao_conclui_com_crianca_a_bordo(client, mundo, em_andamento):
    _eventos(
        client,
        mundo,
        em_andamento,
        _ev("embarque", mundo["ana"], 1),
        _ev("nao_embarcou", mundo["beto"], 2),
    )
    _eventos(client, mundo, em_andamento, _ev("onibus_vazio", minutos=40))
    r = client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    assert r.status_code == 409
    assert r.json()["detail"]["pendencias"] == ["Ana: ainda está a bordo"]


def test_onibus_vazio_e_obrigatorio(client, mundo, em_andamento):
    _eventos(
        client,
        mundo,
        em_andamento,
        _ev("nao_embarcou", mundo["ana"], 1),
        _ev("nao_embarcou", mundo["beto"], 2),
    )
    r = client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    assert r.status_code == 409
    assert r.json()["detail"]["pendencias"] == [
        "Falta confirmar que o ônibus foi percorrido e está vazio"
    ]


def test_movimento_depois_do_onibus_vazio_exige_nova_confirmacao(client, mundo, em_andamento):
    _eventos(
        client,
        mundo,
        em_andamento,
        _ev("nao_embarcou", mundo["ana"], 1),
        _ev("onibus_vazio", minutos=10),
    )
    _eventos(client, mundo, em_andamento, _ev("desembarque", mundo["beto"], 20))
    r = client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    assert r.status_code == 409
    assert any("depois da confirmação" in p for p in r.json()["detail"]["pendencias"])
    _eventos(client, mundo, em_andamento, _ev("onibus_vazio", minutos=30))
    assert (
        client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"]).status_code
        == 200
    )


def test_ausencia_avisada_conta_como_status_final(client, db, mundo):
    viagem = _gerar(client, mundo)
    db.add(Ausencia(estudante_id=mundo["ana"].id, data=HOJE))
    db.flush()
    _iniciar(client, mundo, viagem)
    _eventos(
        client, mundo, viagem, _ev("desembarque", mundo["beto"], 5), _ev("onibus_vazio", minutos=10)
    )
    assert client.post(f"/viagens/{viagem['id']}/concluir", headers=mundo["hm"]).status_code == 200


def test_eventos_atrasados_do_offline_liberam_a_conclusao(client, mundo, em_andamento):
    """O aparelho ficou sem rede: tudo chega de uma vez, fora de ordem, e a viagem fecha."""
    lote = [
        _ev("onibus_vazio", minutos=40),
        _ev("desembarque", mundo["beto"], 31),
        _ev("desembarque", mundo["ana"], 30),
        _ev("embarque", mundo["beto"], 2),
        _ev("embarque", mundo["ana"], 1),
    ]
    assert (
        client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"]).status_code
        == 409
    )
    r = _eventos(client, mundo, em_andamento, *lote)
    assert [x["resultado"] for x in r.json()] == ["aceito"] * 5
    assert (
        client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"]).status_code
        == 200
    )


def test_evento_atrasado_apos_a_conclusao_abre_alerta_critico(client, mundo, em_andamento):
    _tudo_resolvido(client, mundo, em_andamento)
    client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hm"])
    # Chega depois um embarque mais tardio que o desembarque: a criança voltou ao ônibus.
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 50))
    alertas = client.get("/alertas", headers=mundo["gestor"]).json()
    assert [(a["tipo"], a["severidade"]) for a in alertas] == [
        ("crianca_a_bordo_apos_conclusao", "critico")
    ]


def test_concluir_so_com_viagem_em_andamento_e_por_quem_pode(
    client, mundo, em_andamento, criar_usuario
):
    outro = _h(criar_usuario(Perfil.MOTORISTA))
    assert client.post(f"/viagens/{em_andamento['id']}/concluir", headers=outro).status_code == 404
    agendada = _gerar(client, mundo, data=(HOJE + timedelta(days=1)).isoformat())
    assert (
        client.post(f"/viagens/{agendada['id']}/concluir", headers=mundo["gestor"]).status_code
        == 409
    )


def test_monitor_conclui(client, mundo, em_andamento):
    _eventos(
        client,
        mundo,
        em_andamento,
        _ev("nao_embarcou", mundo["ana"], 1),
        _ev("nao_embarcou", mundo["beto"], 2),
        _ev("onibus_vazio", minutos=10),
        quem="hmon",
    )
    assert (
        client.post(f"/viagens/{em_andamento['id']}/concluir", headers=mundo["hmon"]).status_code
        == 200
    )


# Saída da cerca da escola


def _ponto(lat):
    return Coordenadas(latitude=lat, longitude=0.0)


def test_saiu_da_cerca_com_crianca_a_bordo_abre_alerta_critico(client, db, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    viagem = db.get(Viagem, em_andamento["id"])
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.05)) is None  # ainda não chegou à escola
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.0005)) is None  # chegou
    alerta = verificar_saida_da_cerca(db, viagem, _ponto(0.01))  # saiu com a Ana a bordo
    assert alerta is not None
    assert (alerta.tipo, alerta.severidade.value) == ("crianca_a_bordo_fora_da_escola", "critico")
    assert "1 criança" in alerta.mensagem
    # Sem o motorista tentar concluir, a gestão já vê o alerta.
    assert [a["tipo"] for a in client.get("/alertas", headers=mundo["gestor"]).json()] == [
        "crianca_a_bordo_fora_da_escola"
    ]


def test_alerta_de_saida_nao_se_repete(client, db, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    viagem = db.get(Viagem, em_andamento["id"])
    verificar_saida_da_cerca(db, viagem, _ponto(0.0005))
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.01)) is not None
    verificar_saida_da_cerca(db, viagem, _ponto(0.0005))
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.01)) is None
    assert len(db.scalars(select(Alerta)).all()) == 1


def test_saida_da_cerca_sem_crianca_a_bordo_nao_alerta(client, db, mundo, em_andamento):
    _eventos(
        client,
        mundo,
        em_andamento,
        _ev("desembarque", mundo["ana"], 30),
        _ev("nao_embarcou", mundo["beto"], 2),
    )
    viagem = db.get(Viagem, em_andamento["id"])
    verificar_saida_da_cerca(db, viagem, _ponto(0.0005))
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.01)) is None


def test_na_volta_sair_da_escola_com_criancas_e_normal(client, db, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    viagem = db.get(Viagem, em_andamento["id"])
    viagem.sentido = Sentido.VOLTA
    db.flush()
    verificar_saida_da_cerca(db, viagem, _ponto(0.0005))
    assert verificar_saida_da_cerca(db, viagem, _ponto(0.01)) is None


# Cancelamento


def _vincular(db, responsavel, estudante, consentido=True):
    db.add(
        ResponsavelEstudante(
            responsavel_id=responsavel.id,
            estudante_id=estudante.id,
            parentesco="mãe",
            consentimento_em=datetime.now(UTC) if consentido else None,
            consentimento_versao=settings.versao_termo_consentimento if consentido else None,
        )
    )
    db.flush()


def test_gestor_cancela_com_motivo_e_avisa_os_responsaveis(client, db, mundo, criar_usuario):
    mae, pai = criar_usuario(Perfil.RESPONSAVEL), criar_usuario(Perfil.RESPONSAVEL)
    _vincular(db, mae, mundo["ana"])
    _vincular(db, pai, mundo["beto"], consentido=False)
    viagem = _gerar(client, mundo)
    r = client.post(
        f"/viagens/{viagem['id']}/cancelar",
        json={"motivo": "Ônibus quebrou"},
        headers=mundo["gestor"],
    )
    assert r.status_code == 200
    assert r.json()["viagem"]["status"] == "cancelada"
    assert r.json()["viagem"]["motivo_cancelamento"] == "Ônibus quebrou"
    assert r.json()["responsaveis_avisados"] == 1
    avisos = client.get("/notificacoes", headers=_h(mae)).json()
    assert [a["tipo"] for a in avisos] == ["viagem_cancelada"]
    assert avisos[0]["titulo"] == "Viagem cancelada"
    assert "Ônibus quebrou" in avisos[0]["mensagem"]
    assert client.get("/notificacoes", headers=_h(pai)).json() == []
    assert db.scalar(select(text("count(*)")).select_from(Notificacao)) == 1


def test_cancelar_exige_gestor_motivo_e_estado_valido(client, db, mundo):
    viagem = _gerar(client, mundo)
    url = f"/viagens/{viagem['id']}/cancelar"
    assert client.post(url, json={"motivo": "Greve geral"}, headers=mundo["hm"]).status_code == 403
    assert client.post(url, json={"motivo": "x"}, headers=mundo["gestor"]).status_code == 422
    assert (
        client.post(url, json={"motivo": "Greve geral"}, headers=mundo["gestor"]).status_code == 200
    )
    assert (
        client.post(url, json={"motivo": "Greve geral"}, headers=mundo["gestor"]).status_code == 409
    )
    assert _iniciar(client, mundo, viagem).status_code == 409


def test_nao_cancela_com_crianca_a_bordo(client, mundo, em_andamento):
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["ana"], 1))
    r = client.post(
        f"/viagens/{em_andamento['id']}/cancelar",
        json={"motivo": "Pane no motor"},
        headers=mundo["gestor"],
    )
    assert r.status_code == 409
    assert "criança a bordo" in r.json()["detail"]


# R12


def test_ausencia_avisada_com_a_viagem_andando_vira_aviso_na_lista(
    client, db, mundo, em_andamento, criar_usuario
):
    mae = criar_usuario(Perfil.RESPONSAVEL)
    _vincular(db, mae, mundo["beto"])
    r = client.post(
        "/ausencias",
        json={"estudante_id": mundo["beto"].id, "data": HOJE.isoformat()},
        headers=_h(mae),
    )
    assert r.status_code == 201
    lista = client.get(f"/viagens/{em_andamento['id']}/lista", headers=mundo["hm"]).json()
    beto = next(a for a in lista["alunos"] if a["nome"] == "Beto")
    assert beto["status"] == "ausencia_avisada"
    assert beto["ausencia_avisada_depois"] is True
    # Se mesmo assim a criança aparecer, o toque do motorista prevalece.
    _eventos(client, mundo, em_andamento, _ev("embarque", mundo["beto"], 1))
    assert _status(client, mundo, em_andamento)["Beto"] == "embarcou"
    assert (
        db.get(ViagemAluno, (em_andamento["id"], mundo["beto"].id)).ausencia_avisada_em is not None
    )
