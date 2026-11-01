"""Falhas encontradas nas revisões de código e de segurança."""

from datetime import date

import pytest

from app.geo import Coordenadas, para_ponto
from app.models import (
    Estudante,
    Frequencia,
    Matricula,
    Parada,
    Perfil,
    StatusMatricula,
    Turma,
    Turno,
)
from app.routers.auth import MAX_FALHAS_LOGIN

GRANDE = 2**40
# Ano passado fixo: as datas nunca são futuras nem cruzam a virada do ano letivo.
ANO = date.today().year - 1
INICIO = date(ANO, 2, 1)
ONTEM = date(ANO, 6, 1)
HOJE = date(ANO, 6, 2)


def _turma(db, escola, nome="A"):
    turma = Turma(escola_id=escola.id, nome=nome, serie="1", turno=Turno.MANHA, ano_letivo=ANO)
    db.add(turma)
    db.flush()
    return turma


def _matriculado(db, turma, inicio=INICIO):
    estudante = Estudante(nome="Ana", data_nascimento=date(2015, 1, 1))
    db.add(estudante)
    db.flush()
    matricula = Matricula(estudante_id=estudante.id, turma_id=turma.id, data_inicio=inicio)
    db.add(matricula)
    db.flush()
    return estudante, matricula


@pytest.mark.parametrize(
    ("metodo", "rota", "corpo"),
    [
        ("get", f"/matriculas/{GRANDE}", None),
        ("get", f"/matriculas?estudante_id={GRANDE}", None),
        ("get", f"/matriculas/historico/{GRANDE}", None),
        ("get", f"/frequencias?turma_id={GRANDE}", None),
        ("get", f"/rotas/{GRANDE}", None),
        ("get", f"/paradas/{GRANDE}", None),
        ("get", "/rotas?offset=99999999999999999999", None),
        ("get", "/paradas?offset=99999999999999999999", None),
        ("get", "/matriculas?deslocamento=99999999999999999999", None),
        (
            "post",
            "/matriculas",
            {"estudante_id": GRANDE, "turma_id": 1, "data_inicio": "2026-02-01"},
        ),
        ("post", "/frequencias", {"matricula_id": GRANDE, "data": "2026-02-01", "presente": True}),
        (
            "post",
            "/frequencias/lote",
            {
                "turma_id": GRANDE,
                "data": "2026-02-01",
                "registros": [{"matricula_id": 1, "presente": True}],
            },
        ),
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
            "/auth/usuarios",
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


def test_diretor_nao_transfere_para_outra_escola(client, db, cabecalhos, criar_escola):
    origem, destino = criar_escola("Origem"), criar_escola("Destino")
    turma_origem, turma_destino = _turma(db, origem), _turma(db, destino)
    estudante, matricula = _matriculado(db, turma_origem)
    corpo = {
        "estudante_id": estudante.id,
        "turma_destino_id": turma_destino.id,
        "data": ONTEM.isoformat(),
    }
    resposta = client.post(
        "/matriculas/transferencias", json=corpo, headers=cabecalhos(Perfil.DIRETOR, origem.id)
    )
    assert resposta.status_code == 403
    db.refresh(matricula)
    assert matricula.status == StatusMatricula.ATIVA
    admin = client.post("/matriculas/transferencias", json=corpo, headers=cabecalhos(Perfil.ADMIN))
    assert admin.status_code == 201


def test_diretor_nao_se_apropria_de_estudante_alheio_matriculando(
    client, db, cabecalhos, criar_escola
):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    turma = _turma(db, minha)
    estudante, matricula = _matriculado(db, _turma(db, outra))
    matricula.status = StatusMatricula.ENCERRADA
    matricula.data_fim = INICIO
    db.flush()
    h = cabecalhos(Perfil.DIRETOR, minha.id)
    corpo = {"turma_id": turma.id, "data_inicio": INICIO.isoformat()}
    alheio = client.post("/matriculas", json=corpo | {"estudante_id": estudante.id}, headers=h)
    inexistente = client.post("/matriculas", json=corpo | {"estudante_id": 999_999}, headers=h)
    assert alheio.status_code == inexistente.status_code == 403
    assert alheio.json() == inexistente.json()
    assert client.get(f"/estudantes/{estudante.id}", headers=h).status_code == 403


def test_diretor_rematricula_ex_aluno_da_propria_escola(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    turma = _turma(db, escola)
    estudante, matricula = _matriculado(db, turma)
    matricula.status = StatusMatricula.ENCERRADA
    matricula.data_fim = INICIO
    db.flush()
    resposta = client.post(
        "/matriculas",
        json={
            "estudante_id": estudante.id,
            "turma_id": _turma(db, escola, "B").id,
            "data_inicio": HOJE.isoformat(),
        },
        headers=cabecalhos(Perfil.DIRETOR, escola.id),
    )
    assert resposta.status_code == 201


def test_nova_matricula_nao_sobrepoe_periodo_anterior(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    turma = _turma(db, escola)
    estudante, matricula = _matriculado(db, turma)
    matricula.status = StatusMatricula.ENCERRADA
    matricula.data_fim = ONTEM
    db.flush()
    h = cabecalhos(Perfil.ADMIN)

    def matricular(inicio):
        corpo = {
            "estudante_id": estudante.id,
            "turma_id": _turma(db, escola, f"T{inicio}").id,
            "data_inicio": inicio.isoformat(),
        }
        return client.post("/matriculas", json=corpo, headers=h).status_code

    assert matricular(INICIO) == 422
    assert matricular(ONTEM) == 422
    assert matricular(HOJE) == 201


def test_turma_com_matriculas_nao_muda_de_escola_nem_de_ano(client, db, cabecalhos, criar_escola):
    escola, outra = criar_escola("Uma"), criar_escola("Outra")
    turma = _turma(db, escola)
    _matriculado(db, turma)
    h = cabecalhos(Perfil.ADMIN)
    base = {"escola_id": escola.id, "nome": "A", "serie": "2", "turno": "tarde", "ano_letivo": ANO}
    url = f"/turmas/{turma.id}"
    assert client.put(url, json=base | {"escola_id": outra.id}, headers=h).status_code == 409
    assert client.put(url, json=base | {"ano_letivo": ANO + 1}, headers=h).status_code == 409
    assert client.put(url, json=base, headers=h).status_code == 200


def test_so_admin_remove_estudante(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    estudante = Estudante(nome="Sem vínculo", data_nascimento=date(2015, 1, 1))
    db.add(estudante)
    db.flush()
    url = f"/estudantes/{estudante.id}"
    assert client.delete(url, headers=cabecalhos(Perfil.DIRETOR, escola.id)).status_code == 403
    assert client.delete(url, headers=cabecalhos(Perfil.ADMIN)).status_code == 204


def test_diretor_nao_descobre_ids_de_estudantes(client, db, cabecalhos, criar_escola):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    estudante, _ = _matriculado(db, _turma(db, outra))
    h = cabecalhos(Perfil.DIRETOR, minha.id)
    assert client.get(f"/estudantes/{estudante.id}", headers=h).status_code == 403
    assert client.get("/estudantes/999999", headers=h).status_code == 403
    assert client.get(f"/matriculas/historico/{estudante.id}", headers=h).json() == []
    assert client.get("/matriculas/historico/999999", headers=h).json() == []


def _cadastro(**extra):
    return {"nome": "Bia", "data_nascimento": "2015-05-05"} | extra


def test_diretor_cadastra_estudante_com_matricula_e_passa_a_ver(
    client, db, cabecalhos, criar_escola
):
    escola = criar_escola()
    turma = _turma(db, escola)
    h = cabecalhos(Perfil.DIRETOR, escola.id)
    matricula = {"turma_id": turma.id, "data_inicio": HOJE.isoformat()}
    resposta = client.post("/estudantes", json=_cadastro(matricula=matricula), headers=h)
    assert resposta.status_code == 201
    assert client.get(f"/estudantes/{resposta.json()['id']}", headers=h).status_code == 200


def test_diretor_nao_cadastra_sem_matricula_nem_em_turma_alheia(
    client, db, cabecalhos, criar_escola
):
    minha, outra = criar_escola("Minha"), criar_escola("Outra")
    h = cabecalhos(Perfil.DIRETOR, minha.id)
    assert client.post("/estudantes", json=_cadastro(), headers=h).status_code == 422
    matricula = {"turma_id": _turma(db, outra).id, "data_inicio": HOJE.isoformat()}
    resposta = client.post("/estudantes", json=_cadastro(matricula=matricula), headers=h)
    assert resposta.status_code == 403


def test_admin_cadastra_sem_matricula(client, cabecalhos):
    resposta = client.post("/estudantes", json=_cadastro(), headers=cabecalhos(Perfil.ADMIN))
    assert resposta.status_code == 201


def test_diretor_nao_altera_parada_do_estudante(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    estudante, _ = _matriculado(db, _turma(db, escola))
    parada = Parada(nome="P", localizacao=para_ponto(Coordenadas(latitude=0, longitude=0)))
    db.add(parada)
    db.flush()
    h = cabecalhos(Perfil.DIRETOR, escola.id)
    base = {"nome": "Ana", "data_nascimento": "2015-01-01"}
    com_parada = client.put(
        f"/estudantes/{estudante.id}", json=base | {"parada_id": parada.id}, headers=h
    )
    assert com_parada.status_code == 403
    assert client.put(f"/estudantes/{estudante.id}", json=base, headers=h).status_code == 200


def test_transferencia_recusa_frequencia_na_data_ou_depois(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    estudante, matricula = _matriculado(db, _turma(db, escola))
    db.add(Frequencia(matricula_id=matricula.id, data=HOJE, presente=False))
    db.flush()
    corpo = {
        "estudante_id": estudante.id,
        "turma_destino_id": _turma(db, escola, "B").id,
        "data": HOJE.isoformat(),
    }
    h = cabecalhos(Perfil.ADMIN)
    assert client.post("/matriculas/transferencias", json=corpo, headers=h).status_code == 422
    db.refresh(matricula)
    assert matricula.status == StatusMatricula.ATIVA


def test_encerramento_recusa_frequencia_posterior(client, db, cabecalhos, criar_escola):
    _, matricula = _matriculado(db, _turma(db, criar_escola()))
    db.add(Frequencia(matricula_id=matricula.id, data=HOJE, presente=True))
    db.flush()
    h = cabecalhos(Perfil.ADMIN)
    rota = f"/matriculas/{matricula.id}/encerrar"
    assert client.post(rota, json={"data_fim": ONTEM.isoformat()}, headers=h).status_code == 422
    assert client.post(rota, json={"data_fim": HOJE.isoformat()}, headers=h).status_code == 200


def test_dia_da_transferencia_pertence_a_nova_matricula(client, db, cabecalhos, criar_escola):
    escola = criar_escola()
    estudante, antiga = _matriculado(db, _turma(db, escola))
    h = cabecalhos(Perfil.ADMIN)
    nova = client.post(
        "/matriculas/transferencias",
        json={
            "estudante_id": estudante.id,
            "turma_destino_id": _turma(db, escola, "B").id,
            "data": HOJE.isoformat(),
        },
        headers=h,
    ).json()

    def lancar(matricula_id):
        corpo = {"matricula_id": matricula_id, "data": HOJE.isoformat(), "presente": True}
        return client.post("/frequencias", json=corpo, headers=h).status_code

    assert lancar(antiga.id) == 422
    assert lancar(nova["id"]) == 200
