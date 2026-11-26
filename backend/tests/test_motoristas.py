from datetime import timedelta

import pytest

from app import tempo
from app.models import Motorista, Perfil, StatusViagem, Viagem
from app.security import criar_token
from tests.conftest import rota_de_teste

HOJE = tempo.hoje()


def _corpo(usuario, **extra):
    return {
        "usuario_id": usuario.id,
        "cnh": "12345678901",
        "categoria_cnh": "D",
        "cnh_valida_ate": (HOJE + timedelta(days=365)).isoformat(),
        "curso_transporte_escolar_ate": (HOJE + timedelta(days=365)).isoformat(),
        **extra,
    }


def _cadastrar(db, usuario, **campos):
    m = Motorista(
        usuario_id=usuario.id,
        cnh=campos.pop("cnh", f"{usuario.id:011d}"),
        categoria_cnh=campos.pop("categoria_cnh", "D"),
        cnh_valida_ate=campos.pop("cnh_valida_ate", HOJE + timedelta(days=365)),
        curso_transporte_escolar_ate=campos.pop(
            "curso_transporte_escolar_ate", HOJE + timedelta(days=365)
        ),
    )
    db.add(m)
    db.flush()
    return m


def _h(usuario):
    return {"Authorization": f"Bearer {criar_token(usuario)}"}


def test_gestor_cadastra_e_ve_o_detalhe_com_cnh(client, cabecalhos, criar_usuario):
    h = cabecalhos(Perfil.GESTOR)
    motorista = criar_usuario(Perfil.MOTORISTA)
    criado = client.post("/motoristas", json=_corpo(motorista), headers=h)
    assert criado.status_code == 201
    assert criado.json()["cnh"] == "12345678901"
    assert criado.json()["habilitacao"] == {
        "data": HOJE.isoformat(),
        "pode_dirigir": True,
        "motivos": [],
    }
    assert client.get(f"/motoristas/{motorista.id}", headers=h).json() == criado.json()


def test_listagem_mascara_a_cnh(client, db, cabecalhos, criar_usuario):
    _cadastrar(db, criar_usuario(Perfil.MOTORISTA), cnh="12345678901")
    corpo = client.get("/motoristas", headers=cabecalhos(Perfil.GESTOR)).json()
    assert corpo["itens"][0]["cnh_final"] == "*******8901"
    assert "12345678901" not in str(corpo)


def test_so_usuario_motorista_tem_cadastro(client, cabecalhos, criar_usuario):
    h = cabecalhos()
    assert (
        client.post(
            "/motoristas", json=_corpo(criar_usuario(Perfil.MONITOR)), headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/motoristas",
            json={**_corpo(criar_usuario(Perfil.MOTORISTA)), "usuario_id": 999999},
            headers=h,
        ).status_code
        == 422
    )


def test_cnh_e_cadastro_unicos(client, db, cabecalhos, criar_usuario):
    h = cabecalhos()
    a, b = criar_usuario(Perfil.MOTORISTA), criar_usuario(Perfil.MOTORISTA)
    db.commit()
    assert client.post("/motoristas", json=_corpo(a), headers=h).status_code == 201
    assert client.post("/motoristas", json=_corpo(b), headers=h).status_code == 409


@pytest.mark.parametrize(
    "alteracao",
    [{"cnh": "123"}, {"cnh": "1234567890a"}, {"categoria_cnh": "Z"}, {"categoria_cnh": ""}],
)
def test_validacao(client, cabecalhos, criar_usuario, alteracao):
    corpo = _corpo(criar_usuario(Perfil.MOTORISTA), **alteracao)
    assert client.post("/motoristas", json=corpo, headers=cabecalhos()).status_code == 422


def test_pode_dirigir_hoje_e_por_que_nao(client, db, cabecalhos, criar_usuario):
    gestor = cabecalhos(Perfil.GESTOR)
    ontem = HOJE - timedelta(days=1)
    casos = {
        "em dia": ({}, True, []),
        "cnh vencida": ({"cnh_valida_ate": ontem}, False, ["CNH vencida"]),
        "curso vencido": (
            {"curso_transporte_escolar_ate": ontem},
            False,
            ["Curso de transporte escolar vencido"],
        ),
        "categoria B": (
            {"categoria_cnh": "B"},
            False,
            ["Categoria da CNH não permite transporte escolar"],
        ),
        "tudo errado": (
            {"cnh_valida_ate": ontem, "curso_transporte_escolar_ate": ontem, "categoria_cnh": "A"},
            False,
            [
                "CNH vencida",
                "Categoria da CNH não permite transporte escolar",
                "Curso de transporte escolar vencido",
            ],
        ),
        "vence hoje": ({"cnh_valida_ate": HOJE}, True, []),
    }
    for nome, (campos, esperado, motivos) in casos.items():
        usuario = criar_usuario(Perfil.MOTORISTA)
        _cadastrar(db, usuario, **campos)
        resposta = client.get(f"/motoristas/{usuario.id}/habilitacao", headers=gestor).json()
        assert resposta["pode_dirigir"] is esperado, nome
        assert resposta["motivos"] == motivos, nome


def test_habilitacao_numa_data_futura(client, db, cabecalhos, criar_usuario):
    usuario = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, usuario, cnh_valida_ate=HOJE + timedelta(days=10))
    h = cabecalhos(Perfil.GESTOR)
    url = f"/motoristas/{usuario.id}/habilitacao"
    assert client.get(f"{url}?data={HOJE + timedelta(days=10)}", headers=h).json()["pode_dirigir"]
    depois = client.get(f"{url}?data={HOJE + timedelta(days=11)}", headers=h).json()
    assert depois["motivos"] == ["CNH vencida"]


def test_conta_desativada_nao_dirige(client, db, cabecalhos, criar_usuario):
    usuario = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, usuario)
    usuario.ativo = False
    db.flush()
    resposta = client.get(f"/motoristas/{usuario.id}/habilitacao", headers=cabecalhos()).json()
    assert resposta == {
        "data": HOJE.isoformat(),
        "pode_dirigir": False,
        "motivos": ["Conta desativada"],
    }


def test_documentos_vencendo_em_30_dias(client, db, cabecalhos, criar_usuario):
    h = cabecalhos(Perfil.GESTOR)
    a = criar_usuario(Perfil.MOTORISTA)
    b = criar_usuario(Perfil.MOTORISTA)
    c = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, a, cnh_valida_ate=HOJE + timedelta(days=5))
    _cadastrar(db, b, curso_transporte_escolar_ate=HOJE - timedelta(days=2))
    _cadastrar(db, c, cnh_valida_ate=HOJE + timedelta(days=31))

    lista = client.get("/motoristas/vencendo", headers=h).json()
    assert [(d["usuario_id"], d["documento"], d["dias_restantes"]) for d in lista] == [
        (b.id, "curso_transporte_escolar", -2),
        (a.id, "cnh", 5),
    ]
    assert client.get("/motoristas/vencendo?dias=60", headers=h).json()[-1]["usuario_id"] == c.id
    assert client.get("/motoristas/vencendo?dias=0", headers=h).status_code == 422


def test_motorista_ve_so_o_proprio_cadastro(client, db, criar_usuario):
    eu, outro = criar_usuario(Perfil.MOTORISTA), criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, eu, cnh="11111111111")
    _cadastrar(db, outro, cnh="22222222222")
    h = _h(eu)

    meu = client.get("/motorista/eu", headers=h).json()
    assert meu["usuario_id"] == eu.id
    assert meu["cnh"] == "11111111111"
    assert client.get("/motorista/eu/habilitacao", headers=h).json()["pode_dirigir"] is True
    # Nenhuma rota de gestão serve ao motorista.
    assert client.get(f"/motoristas/{outro.id}", headers=h).status_code == 403
    assert client.get("/motoristas", headers=h).status_code == 403
    assert client.get("/motoristas/vencendo", headers=h).status_code == 403


def test_motorista_sem_cadastro_sabe_que_nao_pode_dirigir(client, criar_usuario):
    h = _h(criar_usuario(Perfil.MOTORISTA))
    assert client.get("/motorista/eu", headers=h).status_code == 404
    resposta = client.get("/motorista/eu/habilitacao", headers=h).json()
    assert resposta["pode_dirigir"] is False
    assert resposta["motivos"] == ["Motorista sem cadastro de documentos"]


def test_responsavel_nunca_ve_cnh(client, db, criar_usuario):
    motorista = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, motorista, cnh="98765432100")
    h = _h(criar_usuario(Perfil.RESPONSAVEL))
    for url in (
        "/motoristas",
        f"/motoristas/{motorista.id}",
        "/motorista/eu",
        "/motoristas/vencendo",
    ):
        resposta = client.get(url, headers=h)
        assert resposta.status_code == 403
        assert "98765432100" not in resposta.text


def test_atualizar_e_remover(client, db, cabecalhos, criar_usuario):
    h = cabecalhos(Perfil.GESTOR)
    usuario = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, usuario)
    url = f"/motoristas/{usuario.id}"
    corpo = {k: v for k, v in _corpo(usuario, categoria_cnh="E").items() if k != "usuario_id"}
    assert client.put(url, json=corpo, headers=h).json()["categoria_cnh"] == "E"
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize("situacao", [StatusViagem.AGENDADA, StatusViagem.EM_ANDAMENTO])
def test_nao_remove_motorista_escalado_em_viagem(client, db, cabecalhos, criar_usuario, situacao):
    """O caso da revisão: `SET NULL` tirava o ônibus do mapa no meio da viagem."""
    h = cabecalhos(Perfil.GESTOR)
    usuario = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, usuario)
    rota = rota_de_teste(db, motorista_id=usuario.id)
    db.add(
        Viagem(
            rota_id=rota.id,
            data=HOJE,
            turno=rota.turno,
            sentido=rota.sentido,
            escola_id=rota.escola_id,
            motorista_id=usuario.id,
            status=situacao,
        )
    )
    db.flush()
    assert client.delete(f"/motoristas/{usuario.id}", headers=h).status_code == 409
    assert client.get(f"/motoristas/{usuario.id}", headers=h).status_code == 200


def test_viagem_agendada_de_dia_que_passou_nao_trava_a_remocao(
    client, db, cabecalhos, criar_usuario
):
    h = cabecalhos(Perfil.GESTOR)
    usuario = criar_usuario(Perfil.MOTORISTA)
    _cadastrar(db, usuario)
    rota = rota_de_teste(db, motorista_id=usuario.id)
    db.add(
        Viagem(
            rota_id=rota.id,
            data=HOJE - timedelta(days=7),
            turno=rota.turno,
            sentido=rota.sentido,
            escola_id=rota.escola_id,
            motorista_id=usuario.id,
        )
    )
    db.flush()
    assert client.delete(f"/motoristas/{usuario.id}", headers=h).status_code == 204
