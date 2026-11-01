from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models import (
    Estudante,
    Frequencia,
    Matricula,
    Perfil,
    Polo,
    StatusMatricula,
    Turma,
    Turno,
)


@pytest.fixture
def cenario(db, criar_escola):
    """Polo Norte com a escola A; escola B sem polo. Três matrículas ativas desde fevereiro."""
    polo = Polo(nome="Polo Norte")
    db.add(polo)
    db.flush()
    a, b = criar_escola("Escola A"), criar_escola("Escola B")
    a.polo_id = polo.id
    t_a = Turma(escola_id=a.id, nome="A1", serie="1", turno=Turno.MANHA, ano_letivo=2025)
    t_b = Turma(escola_id=b.id, nome="B1", serie="1", turno=Turno.MANHA, ano_letivo=2025)
    estudantes = [Estudante(nome=n, data_nascimento=date(2015, 1, 1)) for n in ("E1", "E2", "E3")]
    db.add_all([t_a, t_b, *estudantes])
    db.flush()
    matriculas = [
        Matricula(
            estudante_id=e.id,
            turma_id=t.id,
            data_inicio=date(2025, 2, 1),
            status=StatusMatricula.ATIVA,
        )
        for e, t in zip(estudantes, [t_a, t_a, t_b], strict=True)
    ]
    db.add_all(matriculas)
    db.commit()
    return {
        "polo": polo,
        "a": a,
        "b": b,
        "t_a": t_a,
        "t_b": t_b,
        "m1": matriculas[0],
        "m2": matriculas[1],
        "m3": matriculas[2],
        "e1": estudantes[0],
    }


def _lancar(client, h, matricula, data="2025-03-10", presente=True):
    return client.post(
        "/frequencias",
        json={"matricula_id": matricula, "data": data, "presente": presente},
        headers=h,
    )


def _total(db):
    return db.scalar(select(func.count()).select_from(Frequencia))


def test_lancamento_individual_e_idempotente(client, db, cenario, cabecalhos):
    h = cabecalhos()
    m = cenario["m1"].id
    primeira = _lancar(client, h, m, presente=True)
    assert primeira.status_code == 200
    repetida = _lancar(client, h, m, presente=True)
    assert repetida.json()["id"] == primeira.json()["id"]
    corrigida = _lancar(client, h, m, presente=False)
    assert corrigida.json()["id"] == primeira.json()["id"]
    assert corrigida.json()["presente"] is False
    assert _total(db) == 1


def test_validacoes_de_data_e_matricula(client, db, cenario, cabecalhos):
    h = cabecalhos()
    m = cenario["m1"]
    futura = (date.today() + timedelta(days=1)).isoformat()
    assert _lancar(client, h, m.id, data=futura).status_code == 422
    assert _lancar(client, h, m.id, data="2025-01-31").status_code == 422  # antes do início
    assert _lancar(client, h, 999999).status_code == 404

    m.data_fim = date(2025, 3, 1)
    m.status = StatusMatricula.ENCERRADA
    db.commit()
    assert _lancar(client, h, m.id, data="2025-03-02").status_code == 422  # depois do fim
    assert _lancar(client, h, m.id, data="2025-03-01").status_code == 200  # limite do período
    assert _total(db) == 1


def _lote(client, h, turma, registros, data="2025-03-10"):
    return client.post(
        "/frequencias/lote",
        json={"turma_id": turma, "data": data, "registros": registros},
        headers=h,
    )


def test_lote_por_turma_e_idempotente(client, db, cenario, cabecalhos):
    h = cabecalhos()
    registros = [
        {"matricula_id": cenario["m1"].id, "presente": True},
        {"matricula_id": cenario["m2"].id, "presente": False},
    ]
    resposta = _lote(client, h, cenario["t_a"].id, registros)
    assert resposta.status_code == 200
    assert len(resposta.json()) == 2
    assert _lote(client, h, cenario["t_a"].id, registros).status_code == 200
    assert _total(db) == 2


def test_lote_invalido_nao_grava_nada(client, db, cenario, cabecalhos):
    h = cabecalhos()
    t = cenario["t_a"].id
    m1, m3 = cenario["m1"].id, cenario["m3"].id
    outra_turma = [
        {"matricula_id": m1, "presente": True},
        {"matricula_id": m3, "presente": True},
    ]
    assert _lote(client, h, t, outra_turma).status_code == 422
    repetida = [{"matricula_id": m1, "presente": True}, {"matricula_id": m1, "presente": False}]
    assert _lote(client, h, t, repetida).status_code == 422
    assert _lote(client, h, t, []).status_code == 422
    fora_do_periodo = [{"matricula_id": m1, "presente": True}]
    assert _lote(client, h, t, fora_do_periodo, data="2025-01-10").status_code == 422
    assert _lote(client, h, 999999, fora_do_periodo).status_code == 404
    assert _total(db) == 0


def test_consulta_com_filtros(client, cenario, cabecalhos):
    h = cabecalhos()
    _lancar(client, h, cenario["m1"].id, data="2025-03-10")
    _lancar(client, h, cenario["m1"].id, data="2025-03-20")
    _lancar(client, h, cenario["m3"].id, data="2025-03-10")

    casos = [
        ({"matricula_id": cenario["m1"].id}, 2),
        ({"estudante_id": cenario["e1"].id}, 2),
        ({"turma_id": cenario["t_b"].id}, 1),
        ({"data_inicio": "2025-03-15"}, 1),
        ({"data_fim": "2025-03-15"}, 2),
        ({"data_inicio": "2025-03-10", "data_fim": "2025-03-10"}, 2),
    ]
    for filtros, esperado in casos:
        resposta = client.get("/frequencias", params=filtros, headers=h)
        assert len(resposta.json()) == esperado, filtros
    invertido = {"data_inicio": "2025-04-01", "data_fim": "2025-03-01"}
    assert client.get("/frequencias", params=invertido, headers=h).status_code == 422


def test_permissoes_e_escopo(client, cenario, cabecalhos):
    admin = cabecalhos()
    _lancar(client, admin, cenario["m1"].id)
    _lancar(client, admin, cenario["m3"].id)
    periodo = {"agrupar": "escola", "data_inicio": "2025-01-01", "data_fim": "2025-12-31"}

    assert client.get("/frequencias").status_code == 401
    assert client.get("/frequencias/agregada", params=periodo).status_code == 401
    coordenador = cabecalhos(Perfil.COORDENADOR)
    assert client.get("/frequencias", headers=coordenador).status_code == 403
    assert (
        client.get("/frequencias/agregada", params=periodo, headers=coordenador).status_code == 403
    )
    assert _lancar(client, coordenador, cenario["m1"].id).status_code == 403

    diretor_a = cabecalhos(Perfil.DIRETOR, cenario["a"].id)
    assert _lancar(client, diretor_a, cenario["m1"].id, data="2025-04-01").status_code == 200
    assert _lancar(client, diretor_a, cenario["m3"].id, data="2025-04-01").status_code == 403
    lote = [{"matricula_id": cenario["m3"].id, "presente": True}]
    assert _lote(client, diretor_a, cenario["t_b"].id, lote).status_code == 403
    vistos = client.get("/frequencias", headers=diretor_a).json()
    assert {f["matricula_id"] for f in vistos} == {cenario["m1"].id}
    agregada = client.get("/frequencias/agregada", params=periodo, headers=diretor_a).json()
    assert [g["grupo_nome"] for g in agregada] == ["Escola A"]


def test_agregada_valores(client, cenario, cabecalhos):
    h = cabecalhos()
    lancamentos = [
        # Escola A, turma A1: 4 registros no período, 1 falta.
        ("m1", "2025-03-10", True),
        ("m1", "2025-03-11", True),
        ("m1", "2025-03-12", False),
        ("m2", "2025-03-10", True),
        # Fora do período: não pode contar.
        ("m2", "2025-05-10", False),
        # Escola B, sem polo: 2 registros no período, 1 falta.
        ("m3", "2025-03-10", True),
        ("m3", "2025-03-11", False),
    ]
    for chave, data, presente in lancamentos:
        assert _lancar(client, h, cenario[chave].id, data, presente).status_code == 200

    def consultar(agrupar):
        resposta = client.get(
            "/frequencias/agregada",
            params={"agrupar": agrupar, "data_inicio": "2025-03-01", "data_fim": "2025-03-31"},
            headers=h,
        )
        assert resposta.status_code == 200
        return {
            g["grupo_nome"]: (
                g["grupo_id"],
                g["total_registros"],
                g["presencas"],
                g["faltas"],
                g["taxa_infrequencia"],
            )
            for g in resposta.json()
        }

    assert consultar("escola") == {
        "Escola A": (cenario["a"].id, 4, 3, 1, 0.25),
        "Escola B": (cenario["b"].id, 2, 1, 1, 0.5),
    }
    assert consultar("turma") == {
        "A1": (cenario["t_a"].id, 4, 3, 1, 0.25),
        "B1": (cenario["t_b"].id, 2, 1, 1, 0.5),
    }
    assert consultar("polo") == {
        "Polo Norte": (cenario["polo"].id, 4, 3, 1, 0.25),
        None: (None, 2, 1, 1, 0.5),
    }


def test_agregada_sem_dados_e_parametros(client, cenario, cabecalhos):
    h = cabecalhos()
    periodo = {"data_inicio": "2025-01-01", "data_fim": "2025-12-31"}
    assert (
        client.get("/frequencias/agregada", params={"agrupar": "polo"} | periodo, headers=h).json()
        == []
    )
    assert client.get("/frequencias/agregada", params=periodo, headers=h).status_code == 422
    sem_fim = {"agrupar": "polo", "data_inicio": "2025-01-01"}
    assert client.get("/frequencias/agregada", params=sem_fim, headers=h).status_code == 422
    assert (
        client.get(
            "/frequencias/agregada",
            params={"agrupar": "bairro"} | periodo,
            headers=h,
        ).status_code
        == 422
    )
    invertido = {"agrupar": "polo", "data_inicio": "2025-12-31", "data_fim": "2025-01-01"}
    assert client.get("/frequencias/agregada", params=invertido, headers=h).status_code == 422
