"""Inscrição da criança na rota (gestão) e aviso de ausência (responsável)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import auditoria, viagens
from app.cadastros import Db, IdRota
from app.models import (
    Ausencia,
    Estudante,
    Inscricao,
    Perfil,
    ResponsavelEstudante,
    Rota,
    RotaParada,
    Turno,
    Usuario,
    Veiculo,
)
from app.schemas.inscricoes import AusenciaCriar, AusenciaLer, InscricaoLer, InscricoesSubstituir
from app.security import Responsavel, exigir_perfil, garantir_responsavel

router = APIRouter(tags=["inscrições"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
CONFLITO_TURNO = "Estudante já inscrito em outra rota no mesmo turno e sentido"


def _rota(db: Db, rota_id: int, travar: bool = False) -> Rota:
    rota = db.get(Rota, rota_id, with_for_update=travar)
    if rota is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rota não encontrada")
    return rota


def _ler(db: Db, rota_id: int, so_ativas: bool = True) -> list[InscricaoLer]:
    consulta = (
        select(Inscricao, Estudante.nome)
        .join(Estudante, Estudante.id == Inscricao.estudante_id)
        .where(Inscricao.rota_id == rota_id)
        .order_by(Estudante.nome, Inscricao.id)
    )
    if so_ativas:
        consulta = consulta.where(Inscricao.ativa.is_(True))
    return [
        InscricaoLer.model_validate(i).model_copy(update={"estudante_nome": nome})
        for i, nome in db.execute(consulta)
    ]


@router.get("/rotas/{rota_id}/inscricoes")
def listar_inscricoes(
    rota_id: IdRota, db: Db, _: Gestao, historico: bool = False
) -> list[InscricaoLer]:
    _rota(db, rota_id)
    return _ler(db, rota_id, so_ativas=not historico)


@router.put("/rotas/{rota_id}/inscricoes")
def substituir_inscricoes(
    rota_id: IdRota, dados: InscricoesSubstituir, request: Request, db: Db, ator: Gestao
) -> list[InscricaoLer]:
    rota = _rota(db, rota_id, travar=True)
    itens = dados.inscricoes
    paradas_da_rota = set(
        db.scalars(select(RotaParada.parada_id).where(RotaParada.rota_id == rota.id))
    )
    estudantes = {
        e.id: e
        for e in db.scalars(
            select(Estudante).where(Estudante.id.in_([i.estudante_id for i in itens]))
        )
    }
    for item in itens:
        estudante = estudantes.get(item.estudante_id)
        if estudante is None:
            raise HTTPException(422, f"Estudante inexistente: {item.estudante_id}")
        if item.parada_id not in paradas_da_rota:
            raise HTTPException(422, f"A parada {item.parada_id} não faz parte da rota")
        if estudante.escola_id != rota.escola_id:
            raise HTTPException(422, f"{estudante.nome} estuda em outra escola")
        if estudante.turno != Turno.INTEGRAL and estudante.turno != rota.turno:
            raise HTTPException(422, f"{estudante.nome} estuda em outro turno")
    if rota.veiculo_id is not None:
        capacidade = db.scalar(select(Veiculo.capacidade).where(Veiculo.id == rota.veiculo_id))
        if capacidade is not None and len(itens) > capacidade:
            raise HTTPException(
                422, f"A rota tem {len(itens)} inscritos e o veículo comporta {capacidade}"
            )

    hoje = date.today()
    atuais = {
        i.estudante_id: i
        for i in db.scalars(
            select(Inscricao).where(Inscricao.rota_id == rota.id, Inscricao.ativa.is_(True))
        )
    }
    enviados = {i.estudante_id for i in itens}
    # Desativar antes de inserir, para a restrição de uma inscrição ativa por turno não atrapalhar.
    for estudante_id, inscricao in atuais.items():
        if estudante_id not in enviados:
            inscricao.ativa = False
            inscricao.vigencia_fim = inscricao.vigencia_fim or hoje
    db.flush()
    for item in itens:
        campos = {
            "parada_id": item.parada_id,
            "dias_semana": item.dias_semana,
            "vigencia_inicio": item.vigencia_inicio,
            "vigencia_fim": item.vigencia_fim,
        }
        existente = atuais.get(item.estudante_id)
        if existente is not None:
            for campo, valor in campos.items():
                setattr(existente, campo, valor)
        else:
            db.add(
                Inscricao(
                    estudante_id=item.estudante_id,
                    rota_id=rota.id,
                    turno=rota.turno,
                    sentido=rota.sentido,
                    **campos,
                )
            )
    auditoria.registrar(
        db,
        "inscricoes.substituir",
        request=request,
        usuario=ator,
        recurso="rota",
        recurso_id=rota.id,
        total=len(itens),
    )
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO_TURNO) from erro
    return _ler(db, rota.id)


@router.get("/ausencias")
def minhas_ausencias(db: Db, usuario: Responsavel) -> list[AusenciaLer]:
    """Ausências de hoje em diante dos filhos do responsável."""
    filhos = select(ResponsavelEstudante.estudante_id).where(
        ResponsavelEstudante.responsavel_id == usuario.id,
        ResponsavelEstudante.consentimento_em.is_not(None),
    )
    consulta = (
        select(Ausencia)
        .where(Ausencia.estudante_id.in_(filhos), Ausencia.data >= date.today())
        .order_by(Ausencia.data, Ausencia.id)
    )
    return [AusenciaLer.model_validate(a) for a in db.scalars(consulta)]


@router.post("/ausencias", status_code=status.HTTP_201_CREATED)
def avisar_ausencia(
    dados: AusenciaCriar, request: Request, db: Db, usuario: Responsavel
) -> AusenciaLer:
    garantir_responsavel(db, usuario, dados.estudante_id)
    # Ida e volta separadas e "ambos" não coexistem no mesmo dia.
    existentes = db.scalars(
        select(Ausencia).where(
            Ausencia.estudante_id == dados.estudante_id, Ausencia.data == dados.data
        )
    ).all()
    if any(
        a.sentido is None or dados.sentido is None or a.sentido == dados.sentido for a in existentes
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ausência já avisada para esse dia")
    ausencia = Ausencia(**dados.model_dump(), criada_por_id=usuario.id)
    db.add(ausencia)
    db.flush()
    if dados.data == date.today():
        viagens.aviso_de_ausencia_tardia(db, dados.estudante_id, dados.data, dados.sentido)
    auditoria.registrar(
        db,
        "ausencia.criar",
        request=request,
        usuario=usuario,
        recurso="estudante",
        recurso_id=dados.estudante_id,
        ausencia_id=ausencia.id,
    )
    db.commit()
    return AusenciaLer.model_validate(ausencia)


@router.delete("/ausencias/{ausencia_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_ausencia(ausencia_id: IdRota, request: Request, db: Db, usuario: Responsavel) -> None:
    ausencia = db.get(Ausencia, ausencia_id)
    if ausencia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausência não encontrada")
    # Sem vínculo, a resposta é a mesma de uma ausência inexistente.
    try:
        garantir_responsavel(db, usuario, ausencia.estudante_id)
    except HTTPException as erro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausência não encontrada") from erro
    if ausencia.data < date.today():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ausência de dia passado não pode ser cancelada"
        )
    db.delete(ausencia)
    auditoria.registrar(
        db,
        "ausencia.cancelar",
        request=request,
        usuario=usuario,
        recurso="estudante",
        recurso_id=ausencia.estudante_id,
        ausencia_id=ausencia_id,
    )
    db.commit()
