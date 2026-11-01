from collections.abc import Iterable
from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import Float, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.cadastros import IdFiltro
from app.models import Escola, Frequencia, Matricula, Polo, StatusMatricula, Turma
from app.routers.matriculas import (
    Db,
    Deslocamento,
    Gestor,
    Limite,
    carregar_matricula,
    invalido,
    nao_encontrado,
    no_escopo,
)
from app.schemas.frequencias import (
    Agrupamento,
    FrequenciaAgregada,
    FrequenciaCriar,
    FrequenciaLer,
    FrequenciaLote,
)
from app.security import garantir_escola

router = APIRouter(prefix="/frequencias", tags=["frequências"])


def _validar_periodo_da_matricula(matricula: Matricula, data: date) -> None:
    # O dia da transferência já pertence à nova matrícula: um registro por estudante e dia.
    fim_exclusivo = matricula.status == StatusMatricula.TRANSFERIDA
    if (
        data < matricula.data_inicio
        or (matricula.data_fim and data > matricula.data_fim)
        or (fim_exclusivo and data == matricula.data_fim)
    ):
        raise invalido(f"Data fora do período da matrícula {matricula.id}")


def _validar_intervalo(data_inicio: date | None, data_fim: date | None) -> None:
    if data_inicio and data_fim and data_inicio > data_fim:
        raise invalido("data_inicio não pode ser posterior a data_fim")


def _gravar(db: Session, data: date, registros: Iterable[tuple[int, bool]]) -> list[FrequenciaLer]:
    """Grava ou corrige em um só comando, então repetir o lançamento não duplica registros."""
    insercao = insert(Frequencia).values(
        [{"matricula_id": m, "data": data, "presente": p} for m, p in registros]
    )
    comando = insercao.on_conflict_do_update(
        index_elements=[Frequencia.matricula_id, Frequencia.data],
        set_={"presente": insercao.excluded.presente},
    ).returning(Frequencia)
    gravados = db.scalars(comando, execution_options={"populate_existing": True}).all()
    db.commit()
    return [FrequenciaLer.model_validate(f) for f in gravados]


@router.post("", status_code=status.HTTP_200_OK)
def lancar(dados: FrequenciaCriar, db: Db, usuario: Gestor) -> FrequenciaLer:
    matricula = carregar_matricula(db, dados.matricula_id, usuario)
    _validar_periodo_da_matricula(matricula, dados.data)
    return _gravar(db, dados.data, [(matricula.id, dados.presente)])[0]


@router.post("/lote", status_code=status.HTTP_200_OK)
def lancar_lote(dados: FrequenciaLote, db: Db, usuario: Gestor) -> list[FrequenciaLer]:
    turma = db.get(Turma, dados.turma_id)
    if turma is None:
        raise nao_encontrado("Turma")
    garantir_escola(usuario, turma.escola_id)
    ids = [r.matricula_id for r in dados.registros]
    matriculas = db.scalars(
        select(Matricula).where(Matricula.id.in_(ids), Matricula.turma_id == turma.id)
    ).all()
    fora = sorted(set(ids) - {m.id for m in matriculas})
    if fora:
        raise invalido(f"Matrículas que não pertencem à turma: {fora}")
    for matricula in matriculas:
        _validar_periodo_da_matricula(matricula, dados.data)
    return _gravar(db, dados.data, [(r.matricula_id, r.presente) for r in dados.registros])


@router.get("/agregada")
def agregada(
    agrupar: Agrupamento, data_inicio: date, data_fim: date, db: Db, usuario: Gestor
) -> list[FrequenciaAgregada]:
    _validar_intervalo(data_inicio, data_fim)
    grupo_id, grupo_nome = {
        Agrupamento.ESCOLA: (Escola.id, Escola.nome),
        Agrupamento.POLO: (Polo.id, Polo.nome),
        Agrupamento.TURMA: (Turma.id, Turma.nome),
    }[agrupar]
    total = func.count()
    faltas = func.count().filter(Frequencia.presente.is_(False))
    consulta = (
        no_escopo(
            select(
                grupo_id.label("grupo_id"),
                grupo_nome.label("grupo_nome"),
                total.label("total_registros"),
                func.count().filter(Frequencia.presente).label("presencas"),
                faltas.label("faltas"),
                (cast(faltas, Float) / total).label("taxa_infrequencia"),
            )
            .select_from(Frequencia)
            .join(Matricula, Frequencia.matricula_id == Matricula.id)
            .join(Turma, Matricula.turma_id == Turma.id)
            .join(Escola, Turma.escola_id == Escola.id)
            .outerjoin(Polo, Escola.polo_id == Polo.id)
            .where(Frequencia.data.between(data_inicio, data_fim)),
            usuario,
        )
        .group_by(grupo_id, grupo_nome)
        .order_by(grupo_nome, grupo_id)
    )
    return [FrequenciaAgregada.model_validate(linha._asdict()) for linha in db.execute(consulta)]


@router.get("")
def listar(
    db: Db,
    usuario: Gestor,
    matricula_id: IdFiltro = None,
    estudante_id: IdFiltro = None,
    turma_id: IdFiltro = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: Limite = 100,
    deslocamento: Deslocamento = 0,
) -> list[FrequenciaLer]:
    _validar_intervalo(data_inicio, data_fim)
    consulta = no_escopo(select(Frequencia).join(Matricula).join(Turma), usuario)
    if matricula_id is not None:
        consulta = consulta.where(Frequencia.matricula_id == matricula_id)
    if estudante_id is not None:
        consulta = consulta.where(Matricula.estudante_id == estudante_id)
    if turma_id is not None:
        consulta = consulta.where(Matricula.turma_id == turma_id)
    if data_inicio is not None:
        consulta = consulta.where(Frequencia.data >= data_inicio)
    if data_fim is not None:
        consulta = consulta.where(Frequencia.data <= data_fim)
    consulta = consulta.order_by(Frequencia.data, Frequencia.id).limit(limite).offset(deslocamento)
    return [FrequenciaLer.model_validate(f) for f in db.scalars(consulta)]
