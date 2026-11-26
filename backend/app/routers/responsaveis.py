"""Vínculo responsável–estudante e as rotas que o responsável usa.

O responsável nunca passa pelas rotas de cadastro (`/estudantes`, `/paradas`...). Tudo o que ele
vê sai daqui, filtrado pelo vínculo e liberado só depois do consentimento.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app import auditoria, consentimento
from app.cadastros import Db, IdRota, buscar
from app.config import settings
from app.models import Estudante, Parada, Perfil, ResponsavelEstudante, Usuario
from app.routers.estudantes import url_assinada
from app.schemas.estudantes import ContatoEmergencia, FotoUrl
from app.schemas.responsaveis import (
    Consentimento,
    FilhoDetalhe,
    FilhoResumo,
    ParadaDoFilho,
    VinculoCriar,
    VinculoLer,
)
from app.security import Responsavel, exigir_perfil, garantir_responsavel

router = APIRouter(tags=["responsáveis"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]


@router.get("/estudantes/{estudante_id}/responsaveis")
def listar_vinculos(estudante_id: IdRota, db: Db, _: Gestao) -> list[VinculoLer]:
    buscar(db, Estudante, estudante_id)
    vinculos = db.scalars(
        select(ResponsavelEstudante)
        .where(ResponsavelEstudante.estudante_id == estudante_id)
        .order_by(ResponsavelEstudante.responsavel_id)
    )
    return [VinculoLer.model_validate(v) for v in vinculos]


@router.post("/estudantes/{estudante_id}/responsaveis", status_code=status.HTTP_201_CREATED)
def vincular(
    estudante_id: IdRota, dados: VinculoCriar, request: Request, db: Db, gestor: Gestao
) -> VinculoLer:
    buscar(db, Estudante, estudante_id)
    responsavel = db.get(Usuario, dados.responsavel_id)
    if responsavel is None or responsavel.perfil != Perfil.RESPONSAVEL:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "O usuário informado não é um responsável"
        )
    if db.get(ResponsavelEstudante, (responsavel.id, estudante_id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vínculo já existe")
    vinculo = ResponsavelEstudante(
        responsavel_id=responsavel.id,
        estudante_id=estudante_id,
        parentesco=dados.parentesco,
        principal=dados.principal,
        criado_por_id=gestor.id,
    )
    db.add(vinculo)
    auditoria.registrar(
        db,
        "vinculo.criar",
        request=request,
        usuario=gestor,
        recurso="estudante",
        recurso_id=estudante_id,
        responsavel_id=responsavel.id,
    )
    db.commit()
    return VinculoLer.model_validate(vinculo)


@router.delete(
    "/estudantes/{estudante_id}/responsaveis/{responsavel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desvincular(
    estudante_id: IdRota, responsavel_id: IdRota, request: Request, db: Db, gestor: Gestao
) -> None:
    vinculo = db.get(ResponsavelEstudante, (responsavel_id, estudante_id))
    if vinculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vínculo não encontrado")
    db.delete(vinculo)
    auditoria.registrar(
        db,
        "vinculo.remover",
        request=request,
        usuario=gestor,
        recurso="estudante",
        recurso_id=estudante_id,
        responsavel_id=responsavel_id,
    )
    db.commit()


@router.get("/responsavel/filhos")
def meus_filhos(db: Db, usuario: Responsavel) -> list[FilhoResumo]:
    linhas = db.execute(
        select(ResponsavelEstudante, Estudante.nome)
        .join(Estudante, Estudante.id == ResponsavelEstudante.estudante_id)
        .where(ResponsavelEstudante.responsavel_id == usuario.id)
        .order_by(Estudante.nome, Estudante.id)
    ).all()
    return [
        FilhoResumo(
            estudante_id=v.estudante_id,
            nome=nome,
            parentesco=v.parentesco,
            consentimento_pendente=not consentimento.esta_vigente(v),
        )
        for v, nome in linhas
    ]


@router.post("/responsavel/filhos/{estudante_id}/consentimento")
def consentir(
    estudante_id: IdRota, dados: Consentimento, request: Request, db: Db, usuario: Responsavel
) -> VinculoLer:
    vinculo = garantir_responsavel(db, usuario, estudante_id, exigir_consentimento=False)
    if dados.versao_termo != settings.versao_termo_consentimento:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Termo desatualizado; a versão atual é {settings.versao_termo_consentimento}",
        )
    if vinculo.consentimento_em is None or vinculo.consentimento_versao != dados.versao_termo:
        vinculo.consentimento_em = datetime.now(UTC)
        vinculo.consentimento_versao = dados.versao_termo
        auditoria.registrar(
            db,
            "consentimento.aceitar",
            request=request,
            usuario=usuario,
            recurso="estudante",
            recurso_id=estudante_id,
            versao=dados.versao_termo,
        )
        db.commit()
    return VinculoLer.model_validate(vinculo)


@router.get("/responsavel/filhos/{estudante_id}")
def meu_filho(estudante_id: IdRota, db: Db, usuario: Responsavel) -> FilhoDetalhe:
    garantir_responsavel(db, usuario, estudante_id)
    estudante = buscar(db, Estudante, estudante_id)
    parada = db.get(Parada, estudante.parada_id) if estudante.parada_id else None
    return FilhoDetalhe(
        estudante_id=estudante.id,
        nome=estudante.nome,
        parada=ParadaDoFilho(id=parada.id, nome=parada.nome) if parada else None,
        contato_emergencia=_contato(estudante),
    )


def _contato(estudante: Estudante) -> ContatoEmergencia | None:
    """Novo na reformulação. O responsável só lê o contato de emergência: para trocar, ele pede
    à gestão, que confere quem está pedindo e grava pelo cadastro do aluno (`PUT /estudantes`).
    Assim um responsável não troca o contato que outro informou."""
    if estudante.contato_emergencia_nome is None:
        return None
    return ContatoEmergencia(
        nome=estudante.contato_emergencia_nome,
        telefone=estudante.contato_emergencia_telefone,
        parentesco=estudante.contato_emergencia_parentesco,
    )


@router.get("/responsavel/filhos/{estudante_id}/foto-url")
def foto_do_filho(estudante_id: IdRota, db: Db, usuario: Responsavel) -> FotoUrl:
    garantir_responsavel(db, usuario, estudante_id)
    return url_assinada(buscar(db, Estudante, estudante_id))
