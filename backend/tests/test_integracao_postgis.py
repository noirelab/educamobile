"""Integridade referencial e consultas espaciais contra o PostGIS real."""

from datetime import date

import pytest
from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.geo import Coordenadas, para_ponto
from app.models import (
    SRID,
    Estudante,
    Frequencia,
    Matricula,
    Parada,
    Perfil,
    Polo,
    Professor,
    Rota,
    RotaParada,
    StatusMatricula,
    Turma,
    Turno,
    Usuario,
)

QUADRADO = "MULTIPOLYGON(((-49.3 -25.5,-49.2 -25.5,-49.2 -25.4,-49.3 -25.4,-49.3 -25.5)))"


def _ponto(latitude, longitude):
    return para_ponto(Coordenadas(latitude=latitude, longitude=longitude))


def _falha_integridade(db, acao):
    with pytest.raises(IntegrityError), db.begin_nested():
        acao()
        db.flush()


@pytest.fixture
def cenario(db, criar_escola):
    escola = criar_escola()
    turma = Turma(escola_id=escola.id, nome="A", serie="1", turno=Turno.MANHA, ano_letivo=2026)
    estudante = Estudante(nome="Ana", data_nascimento=date(2015, 1, 1))
    db.add_all([turma, estudante])
    db.flush()
    matricula = Matricula(
        estudante_id=estudante.id, turma_id=turma.id, data_inicio=date(2026, 2, 1)
    )
    db.add(matricula)
    db.flush()
    return escola, turma, estudante, matricula


# Integridade referencial


def test_nao_remove_escola_com_turma(db, cenario):
    _falha_integridade(db, lambda: db.delete(cenario[0]))


def test_nao_remove_turma_nem_estudante_com_matricula(db, cenario):
    _, turma, estudante, _ = cenario
    _falha_integridade(db, lambda: db.delete(turma))
    _falha_integridade(db, lambda: db.delete(estudante))


def test_turma_exige_escola_existente(db):
    turma = Turma(escola_id=999_999, nome="A", serie="1", turno=Turno.MANHA, ano_letivo=2026)
    _falha_integridade(db, lambda: db.add(turma))


def test_turma_repetida_na_mesma_escola_e_ano(db, cenario):
    escola = cenario[0]
    turma = Turma(escola_id=escola.id, nome="A", serie="2", turno=Turno.TARDE, ano_letivo=2026)
    _falha_integridade(db, lambda: db.add(turma))


def test_uma_so_matricula_ativa_e_historico_permitido(db, cenario):
    _, turma, estudante, matricula = cenario
    nova = dict(estudante_id=estudante.id, turma_id=turma.id, data_inicio=date(2026, 3, 1))
    _falha_integridade(db, lambda: db.add(Matricula(**nova)))

    matricula.status = StatusMatricula.TRANSFERIDA
    db.flush()
    db.add(Matricula(**nova))
    db.flush()


def test_matricula_nao_termina_antes_de_comecar(db, cenario):
    matricula = cenario[3]

    def invalida():
        matricula.data_fim = date(2026, 1, 1)

    _falha_integridade(db, invalida)
    db.refresh(matricula)


def test_uma_frequencia_por_matricula_e_dia(db, cenario):
    matricula = cenario[3]
    dia = date(2026, 3, 2)
    db.add(Frequencia(matricula_id=matricula.id, data=dia, presente=True))
    db.flush()
    repetida = Frequencia(matricula_id=matricula.id, data=dia, presente=False)
    _falha_integridade(db, lambda: db.add(repetida))


def test_remover_matricula_remove_frequencias(db, cenario):
    matricula = cenario[3]
    db.add(Frequencia(matricula_id=matricula.id, data=date(2026, 3, 2), presente=True))
    db.flush()
    db.delete(matricula)
    db.flush()
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Frequencia)) == 0


def test_remover_parada_solta_estudante_mas_nao_rota(db, cenario):
    estudante = cenario[2]
    livre = Parada(nome="Livre", localizacao=_ponto(-25.4, -49.2))
    usada = Parada(nome="Usada", localizacao=_ponto(-25.5, -49.3))
    rota = Rota(nome="R1")
    db.add_all([livre, usada, rota])
    db.flush()
    estudante.parada_id = livre.id
    db.add(RotaParada(rota_id=rota.id, parada_id=usada.id, ordem=1))
    db.flush()

    db.delete(livre)
    db.flush()
    db.refresh(estudante)
    assert estudante.parada_id is None
    _falha_integridade(db, lambda: db.delete(usada))


def test_remover_escola_solta_professor(db, criar_escola):
    escola = criar_escola()
    professor = Professor(nome="Rui", email="rui@exemplo.com", escola_id=escola.id)
    db.add(professor)
    db.flush()
    db.delete(escola)
    db.flush()
    db.refresh(professor)
    assert professor.escola_id is None


def test_diretor_sem_escola_barrado_pelo_banco(db):
    usuario = Usuario(nome="D", email="d@exemplo.com", senha_hash="x", perfil=Perfil.DIRETOR)
    _falha_integridade(db, lambda: db.add(usuario))


# Consultas espaciais


def test_st_distance_em_metros(db):
    """Um grau de latitude mede cerca de 110,7 km perto de 25 graus sul."""
    origem = func.ST_GeogFromText("SRID=4326;POINT(-49 -25)")
    destino = func.ST_GeogFromText("SRID=4326;POINT(-49 -26)")
    assert db.scalar(select(func.ST_Distance(origem, destino))) == pytest.approx(110_700, rel=0.005)


def test_st_distance_por_paradas_cadastradas(db):
    a = Parada(nome="A", localizacao=_ponto(-25.43, -49.27))
    b = Parada(nome="B", localizacao=_ponto(-25.44, -49.27))
    db.add_all([a, b])
    db.flush()
    pa, pb = aliased(Parada), aliased(Parada)
    consulta = select(
        func.ST_Distance(cast(pa.localizacao, Geography), cast(pb.localizacao, Geography))
    ).where(pa.id == a.id, pb.id == b.id)
    assert db.scalar(consulta) == pytest.approx(1_107, rel=0.005)


def test_st_contains_separa_dentro_fora_e_borda(db):
    area = WKTElement(QUADRADO, srid=SRID)
    casos = {
        (-25.45, -49.25): True,
        (-25.45, -49.35): False,
        (-25.4, -49.25): False,  # ST_Contains não inclui a borda
    }
    for (latitude, longitude), esperado in casos.items():
        assert db.scalar(select(func.ST_Contains(area, _ponto(latitude, longitude)))) is esperado


def test_st_contains_nao_confunde_latitude_com_longitude(db):
    area = WKTElement(QUADRADO, srid=SRID)
    assert db.scalar(select(func.ST_Contains(area, _ponto(-25.45, -49.25)))) is True
    trocado = WKTElement("POINT(-25.45 -49.25)", srid=SRID)
    assert db.scalar(select(func.ST_Contains(area, trocado))) is False


def test_rota_escolas_na_area(client, db, cabecalhos, criar_escola):
    polo = Polo(nome="Centro", area=WKTElement(QUADRADO, srid=SRID))
    sem_area = Polo(nome="Sem área")
    db.add_all([polo, sem_area])
    db.flush()
    dentro = criar_escola("Dentro", -25.45, -49.25)
    criar_escola("Fora", -25.45, -49.35)

    h = cabecalhos(Perfil.COORDENADOR)
    resposta = client.get(f"/polos/{polo.id}/escolas-na-area", headers=h)
    assert resposta.status_code == 200
    assert [e["id"] for e in resposta.json()] == [dentro.id]
    assert client.get(f"/polos/{sem_area.id}/escolas-na-area", headers=h).json() == []
    assert client.get("/polos/999999/escolas-na-area", headers=h).status_code == 404
    assert client.get(f"/polos/{polo.id}/escolas-na-area").status_code == 401


def test_indices_espaciais_existem(db):
    consulta = text("SELECT indexname FROM pg_indexes WHERE indexdef ILIKE '%USING gist%'")
    nomes = set(db.scalars(consulta))
    assert {"idx_escola_localizacao", "idx_parada_localizacao", "idx_polo_area"} <= nomes
