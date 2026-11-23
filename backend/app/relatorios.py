"""Relatórios do transporte: viagens, pontualidade, ausências e ocorrências.

Cada função devolve linhas (dicts simples, prontas para JSON ou CSV) e um resumo. Todas aceitam o
mesmo filtro: período, rota e escola.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Alerta,
    Ausencia,
    Estudante,
    Rota,
    StatusAluno,
    StatusViagem,
    Usuario,
    Veiculo,
    Viagem,
    ViagemAluno,
    ViagemParada,
)

# Chegar até 5 minutos depois do previsto conta como no horário.
TOLERANCIA_PONTUALIDADE_MIN = 5
# Células que o Excel e o LibreOffice tratam como fórmula se vierem no início.
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class Filtro:
    de: date
    ate: date
    rota_id: int | None = None
    escola_id: int | None = None

    def como_dict(self) -> dict:
        return {
            "de": self.de.isoformat(),
            "ate": self.ate.isoformat(),
            "rota_id": self.rota_id,
            "escola_id": self.escola_id,
        }


def _viagens(db: Session, f: Filtro):
    consulta = (
        select(Viagem, Rota.nome)
        .join(Rota, Rota.id == Viagem.rota_id)
        .where(Viagem.data >= f.de, Viagem.data <= f.ate)
        .order_by(Viagem.data, Viagem.id)
    )
    if f.rota_id is not None:
        consulta = consulta.where(Viagem.rota_id == f.rota_id)
    if f.escola_id is not None:
        consulta = consulta.where(Viagem.escola_id == f.escola_id)
    return db.execute(consulta).all()


def _minutos(a: datetime | None, b: datetime | None) -> int | None:
    return None if a is None or b is None else round((b - a).total_seconds() / 60)


# Viagens


def viagens(db: Session, f: Filtro) -> tuple[list[dict], dict]:
    linhas_db = _viagens(db, f)
    ids = [v.id for v, _ in linhas_db]
    contagens: dict[int, dict[str, int]] = {i: {} for i in ids}
    if ids:
        for viagem_id, status, n in db.execute(
            select(ViagemAluno.viagem_id, ViagemAluno.status, func.count())
            .where(ViagemAluno.viagem_id.in_(ids))
            .group_by(ViagemAluno.viagem_id, ViagemAluno.status)
        ):
            contagens[viagem_id][status.value] = n
        fora = {
            i: n
            for i, n in db.execute(
                select(ViagemAluno.viagem_id, func.count())
                .where(ViagemAluno.viagem_id.in_(ids), ViagemAluno.fora_da_lista.is_(True))
                .group_by(ViagemAluno.viagem_id)
            )
        }
    else:
        fora = {}
    placas = {i: p for i, p in db.execute(select(Veiculo.id, Veiculo.placa))}
    nomes = {i: n for i, n in db.execute(select(Usuario.id, Usuario.nome))}
    linhas = []
    for v, rota_nome in linhas_db:
        c = contagens[v.id]
        linhas.append(
            {
                "viagem_id": v.id,
                "data": v.data.isoformat(),
                "rota": rota_nome,
                "escola_id": v.escola_id,
                "turno": v.turno.value,
                "sentido": v.sentido.value,
                "status": v.status.value,
                "placa": placas.get(v.veiculo_id),
                "motorista": nomes.get(v.motorista_id),
                "iniciada_em": v.iniciada_em.isoformat() if v.iniciada_em else None,
                "concluida_em": v.concluida_em.isoformat() if v.concluida_em else None,
                "duracao_min": _minutos(v.iniciada_em, v.concluida_em),
                "alunos_na_lista": sum(c.values()),
                "embarcaram": c.get("embarcou", 0) + c.get("desembarcou", 0),
                "nao_embarcaram": c.get("nao_embarcou", 0),
                "ausencias_avisadas": c.get("ausencia_avisada", 0),
                "fora_da_lista": fora.get(v.id, 0),
            }
        )
    por_status: dict[str, int] = {}
    for linha in linhas:
        por_status[linha["status"]] = por_status.get(linha["status"], 0) + 1
    resumo = {
        "viagens": len(linhas),
        "por_status": por_status,
        "alunos_transportados": sum(linha["embarcaram"] for linha in linhas),
    }
    return linhas, resumo


# Pontualidade


def pontualidade(db: Session, f: Filtro) -> tuple[list[dict], dict]:
    fuso = ZoneInfo(settings.fuso_horario)
    linhas = []
    for v, rota_nome in _viagens(db, f):
        if v.status not in (StatusViagem.EM_ANDAMENTO, StatusViagem.CONCLUIDA):
            continue
        paradas = db.scalars(
            select(ViagemParada).where(ViagemParada.viagem_id == v.id).order_by(ViagemParada.ordem)
        ).all()
        if not paradas:
            continue
        primeira = paradas[0]
        # Na ida o destino é a escola (última parada); na volta, a última parada da lista.
        ultima = paradas[-1]

        def atraso(parada, quando):
            if parada.horario_previsto is None or quando is None:
                return None
            local = quando.astimezone(fuso)
            previsto = local.replace(
                hour=parada.horario_previsto.hour,
                minute=parada.horario_previsto.minute,
                second=0,
                microsecond=0,
            )
            return round((local - previsto).total_seconds() / 60)

        a_saida = atraso(primeira, v.iniciada_em)
        a_chegada = atraso(ultima, ultima.chegada_em)
        linhas.append(
            {
                "viagem_id": v.id,
                "data": v.data.isoformat(),
                "rota": rota_nome,
                "escola_id": v.escola_id,
                "sentido": v.sentido.value,
                "atraso_saida_min": a_saida,
                "atraso_chegada_min": a_chegada,
                "no_horario": None
                if a_chegada is None
                else a_chegada <= TOLERANCIA_PONTUALIDADE_MIN,
            }
        )
    medidas = [linha for linha in linhas if linha["no_horario"] is not None]
    atrasos = [linha["atraso_chegada_min"] for linha in medidas]
    resumo = {
        "viagens_medidas": len(medidas),
        "no_horario": sum(1 for linha in medidas if linha["no_horario"]),
        "percentual_no_horario": round(
            100 * sum(1 for linha in medidas if linha["no_horario"]) / len(medidas), 1
        )
        if medidas
        else None,
        "atraso_medio_chegada_min": round(sum(atrasos) / len(atrasos), 1) if atrasos else None,
        "tolerancia_min": TOLERANCIA_PONTUALIDADE_MIN,
    }
    return linhas, resumo


# Ausências


def ausencias(db: Session, f: Filtro) -> tuple[list[dict], dict]:
    avisadas = select(Ausencia.estudante_id, func.count().label("n")).where(
        Ausencia.data >= f.de, Ausencia.data <= f.ate
    )
    na_lista = (
        select(
            ViagemAluno.estudante_id,
            func.count().label("esperadas"),
            func.count()
            .filter(ViagemAluno.status == StatusAluno.NAO_EMBARCOU)
            .label("nao_embarcou"),
        )
        .join(Viagem, Viagem.id == ViagemAluno.viagem_id)
        .where(Viagem.data >= f.de, Viagem.data <= f.ate)
    )
    if f.rota_id is not None:
        na_lista = na_lista.where(Viagem.rota_id == f.rota_id)
    if f.escola_id is not None:
        na_lista = na_lista.where(Viagem.escola_id == f.escola_id)
    avisos = {i: n for i, n in db.execute(avisadas.group_by(Ausencia.estudante_id))}
    contagem = {
        e: (esperadas, nao)
        for e, esperadas, nao in db.execute(na_lista.group_by(ViagemAluno.estudante_id))
    }
    if f.rota_id is not None:
        # O aviso de ausência não tem rota: só vale para quem está nas viagens dela.
        avisos = {i: n for i, n in avisos.items() if i in contagem}
    ids = set(avisos) | set(contagem)
    estudantes = {}
    if ids:
        consulta = select(Estudante.id, Estudante.nome, Estudante.escola_id).where(
            Estudante.id.in_(ids)
        )
        if f.escola_id is not None:
            consulta = consulta.where(Estudante.escola_id == f.escola_id)
        estudantes = {i: (nome, escola) for i, nome, escola in db.execute(consulta)}
    linhas = [
        {
            "estudante_id": i,
            "nome": estudantes[i][0],
            "escola_id": estudantes[i][1],
            "viagens_esperadas": contagem.get(i, (0, 0))[0],
            "ausencias_avisadas": avisos.get(i, 0),
            "nao_embarcou_sem_aviso": contagem.get(i, (0, 0))[1],
        }
        for i in sorted(estudantes)
    ]
    linhas.sort(key=lambda x: (-(x["ausencias_avisadas"] + x["nao_embarcou_sem_aviso"]), x["nome"]))
    resumo = {
        "estudantes": len(linhas),
        "ausencias_avisadas": sum(x["ausencias_avisadas"] for x in linhas),
        "nao_embarcou_sem_aviso": sum(x["nao_embarcou_sem_aviso"] for x in linhas),
    }
    return linhas, resumo


# Ocorrências


def ocorrencias(db: Session, f: Filtro) -> tuple[list[dict], dict]:
    consulta = (
        select(Alerta, Rota.nome, Viagem.data)
        .join(Viagem, Viagem.id == Alerta.viagem_id)
        .join(Rota, Rota.id == Viagem.rota_id)
        .where(Viagem.data >= f.de, Viagem.data <= f.ate)
        .order_by(Alerta.criado_em, Alerta.id)
    )
    if f.rota_id is not None:
        consulta = consulta.where(Viagem.rota_id == f.rota_id)
    if f.escola_id is not None:
        consulta = consulta.where(Viagem.escola_id == f.escola_id)
    linhas = []
    for a, rota_nome, data in db.execute(consulta):
        linhas.append(
            {
                "alerta_id": a.id,
                "viagem_id": a.viagem_id,
                "data": data.isoformat(),
                "rota": rota_nome,
                "tipo": a.tipo,
                "severidade": a.severidade.value,
                "mensagem": a.mensagem,
                "criado_em": a.criado_em.isoformat(),
                "situacao": "resolvido"
                if a.resolvido_em
                else ("reconhecido" if a.reconhecido_em else "aberto"),
                "minutos_ate_reconhecer": _minutos(a.criado_em, a.reconhecido_em),
                "minutos_ate_resolver": _minutos(a.criado_em, a.resolvido_em),
                "resolvido_automaticamente": a.resolvido_automaticamente,
            }
        )
    por_tipo: dict[str, int] = {}
    for linha in linhas:
        por_tipo[linha["tipo"]] = por_tipo.get(linha["tipo"], 0) + 1
    resumo = {
        "ocorrencias": len(linhas),
        "criticas": sum(1 for x in linhas if x["severidade"] == "critico"),
        "por_tipo": por_tipo,
    }
    return linhas, resumo


# CSV


def _celula(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor)
    if not isinstance(valor, str):
        return texto  # número negativo é número, não fórmula
    # Defesa contra injeção de fórmula: quem abre o arquivo numa planilha não executa nada.
    return "'" + texto if texto.startswith(_INICIO_DE_FORMULA) else texto


def para_csv(linhas: list[dict]) -> str:
    saida = io.StringIO()
    if not linhas:
        return ""
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(linhas[0].keys())
    for linha in linhas:
        escritor.writerow([_celula(v) for v in linha.values()])
    return saida.getvalue()
