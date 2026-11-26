"""Novo na reformulação: a equipe da escola confirma que recebeu as crianças da ida.

Só o perfil escola usa estas rotas, e só para a própria escola e o dia de hoje. A confirmação não
mexe no status da lista do motorista (que vem dos eventos imutáveis): fica em
`viagem_aluno.recebido_em`. Criança que desceu e não foi confirmada no prazo vira alerta crítico
(`alertas.nao_recebido_pela_escola`).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app import alertas, auditoria, notificacoes
from app.cadastros import Db, IdRota
from app.models import (
    Estudante,
    Perfil,
    Rota,
    Sentido,
    StatusAluno,
    StatusViagem,
    Usuario,
    Veiculo,
    Viagem,
    ViagemAluno,
)
from app.schemas.recebimento import (
    AlunoChegando,
    ChegadaDaViagem,
    Recebimento,
    RecebimentoResultado,
)
from app.security import exigir_perfil
from app.tempo import hoje as _hoje

router = APIRouter(tags=["recebimento na escola"])
EquipeDaEscola = Annotated[Usuario, exigir_perfil(Perfil.ESCOLA)]
_ATIVAS = (StatusViagem.EM_ANDAMENTO, StatusViagem.CONCLUIDA)


def _viagens_de_hoje(db: Db, escola_id: int):
    return select(Viagem).where(
        Viagem.escola_id == escola_id,
        Viagem.data == _hoje(),
        Viagem.sentido == Sentido.IDA,
        Viagem.status.in_(_ATIVAS),
    )


@router.get("/escola/chegadas")
def chegadas(db: Db, usuario: EquipeDaEscola) -> list[ChegadaDaViagem]:
    """As viagens de ida de hoje da escola, com quem está a caminho, quem desceu e quem já foi
    recebido. Quem não embarcou não aparece."""
    resultado = []
    for viagem in db.scalars(_viagens_de_hoje(db, usuario.escola_id).order_by(Viagem.id)):
        desceu_em = dict(alertas.pendentes_de_recebimento(db, viagem.id))
        linhas = db.execute(
            select(ViagemAluno, Estudante.nome)
            .join(Estudante, Estudante.id == ViagemAluno.estudante_id)
            .where(
                ViagemAluno.viagem_id == viagem.id,
                ViagemAluno.status.in_([StatusAluno.EMBARCOU, StatusAluno.DESEMBARCOU]),
            )
            .order_by(Estudante.nome)
        )
        alunos = []
        for aluno, nome in linhas:
            if aluno.status == StatusAluno.EMBARCOU:
                situacao = "a_caminho"
            elif aluno.recebido_em is None:
                situacao = "aguardando"
            else:
                situacao = "recebido"
            alunos.append(
                AlunoChegando(
                    estudante_id=aluno.estudante_id,
                    nome=nome,
                    situacao=situacao,
                    desembarcou_em=desceu_em.get(aluno.estudante_id),
                    recebido_em=aluno.recebido_em,
                )
            )
        resultado.append(
            ChegadaDaViagem(
                viagem_id=viagem.id,
                rota=db.scalar(select(Rota.nome).where(Rota.id == viagem.rota_id)) or "",
                placa=db.scalar(select(Veiculo.placa).where(Veiculo.id == viagem.veiculo_id)),
                status=viagem.status.value,
                alunos=alunos,
            )
        )
    return resultado


@router.post("/viagens/{viagem_id}/recebimentos")
def confirmar(
    viagem_id: IdRota, dados: Recebimento, request: Request, db: Db, usuario: EquipeDaEscola
) -> RecebimentoResultado:
    """Confirma as crianças que a escola recebeu. Repetir não muda nada (idempotente)."""
    viagem = db.get(Viagem, viagem_id, with_for_update=True)
    # Viagem de outra escola, de outro dia ou de volta some, como para a equipe do ônibus.
    if (
        viagem is None
        or viagem.escola_id != usuario.escola_id
        or viagem.data != _hoje()
        or viagem.sentido != Sentido.IDA
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viagem não encontrada")
    if viagem.status not in _ATIVAS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    ids = set(dados.estudante_ids)
    alunos = {
        a.estudante_id: a
        for a in db.scalars(
            select(ViagemAluno).where(
                ViagemAluno.viagem_id == viagem.id, ViagemAluno.estudante_id.in_(ids)
            )
        )
    }
    fora = sorted(ids - alunos.keys())
    if fora:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Fora da lista desta viagem: {fora}"
        )
    sem_desembarque = sorted(e for e, a in alunos.items() if a.status != StatusAluno.DESEMBARCOU)
    if sem_desembarque:
        # A escola não substitui o toque do motorista: sem o desembarque registrado, a lista
        # dele continua mostrando a criança a bordo. A gestão resolve com o motorista.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"O motorista ainda não registrou o desembarque de: {sem_desembarque}",
        )
    agora = datetime.now(UTC)
    novos = [a for a in alunos.values() if a.recebido_em is None]
    for aluno in novos:
        aluno.recebido_em = agora
        aluno.recebido_por_id = usuario.id
        nome = notificacoes.nome_curto(db.get(Estudante, aluno.estudante_id))
        notificacoes.para_responsaveis(
            db,
            aluno.estudante_id,
            "recebido_escola",
            "Recebido pela escola",
            f"A escola confirmou que recebeu {nome}.",
            viagem_id=viagem.id,
        )
    if novos:
        db.flush()
        aberto = alertas._aberto(db, viagem.id, alertas.TIPO_NAO_RECEBIDO)
        if aberto is not None and not alertas.pendentes_de_recebimento(db, viagem.id):
            alertas._resolver_sozinho(db, aberto, agora)
        auditoria.registrar(
            db,
            "recebimento.confirmar",
            request=request,
            usuario=usuario,
            recurso="viagem",
            recurso_id=viagem.id,
            estudante_ids=sorted(a.estudante_id for a in novos),
        )
    db.commit()
    return RecebimentoResultado(recebidos=len(novos), ja_recebidos=len(alunos) - len(novos))
