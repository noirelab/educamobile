from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select

from app import auditoria, fotos
from app.cadastros import Db, Deslocamento, IdFiltro, IdRota, Limite, buscar, salvar
from app.models import Estudante, Perfil, Turno, Usuario
from app.schemas.estudantes import (
    CAMPOS_CONTATO,
    EstudanteCriar,
    EstudanteLer,
    EstudantesPagina,
    FotoUrl,
)
from app.security import UsuarioInterno, exigir_perfil

router = APIRouter(prefix="/estudantes", tags=["estudantes"])
Editor = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
CONFLITO = "Escola ou parada inexistente"


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
def listar(
    db: Db,
    _: UsuarioInterno,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    escola_id: IdFiltro = None,
    turno: Turno | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> EstudantesPagina:
    filtros = []
    if q:
        filtros.append(Estudante.nome.ilike(f"%{_escapar_like(q.strip())}%", escape="\\"))
    if escola_id is not None:
        filtros.append(Estudante.escola_id == escola_id)
    if turno is not None:
        filtros.append(Estudante.turno == turno)
    total = db.scalar(select(func.count()).select_from(Estudante).where(*filtros))
    itens = db.scalars(
        select(Estudante)
        .where(*filtros)
        .order_by(Estudante.nome, Estudante.id)
        .limit(limit)
        .offset(offset)
    )
    return EstudantesPagina(total=total or 0, itens=[EstudanteLer.model_validate(e) for e in itens])


@router.get("/{estudante_id}")
def obter(estudante_id: IdRota, db: Db, _: UsuarioInterno) -> EstudanteLer:
    return EstudanteLer.model_validate(buscar(db, Estudante, estudante_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: EstudanteCriar, db: Db, _: Editor) -> EstudanteLer:
    estudante = Estudante(**dados.model_dump())
    db.add(estudante)
    salvar(db, CONFLITO)
    return EstudanteLer.model_validate(estudante)


@router.put("/{estudante_id}")
def atualizar(
    estudante_id: IdRota, dados: EstudanteCriar, request: Request, db: Db, gestor: Editor
) -> EstudanteLer:
    estudante = buscar(db, Estudante, estudante_id)
    # O contato de emergência só muda quando vem no corpo (com os três campos, como um bloco).
    mexe_no_contato = bool(dados.model_fields_set & set(CAMPOS_CONTATO))
    for campo, valor in dados.model_dump().items():
        if campo in CAMPOS_CONTATO and not mexe_no_contato:
            continue
        setattr(estudante, campo, valor)
    if mexe_no_contato:
        auditoria.registrar(
            db,
            "estudante.contato_emergencia",
            request=request,
            usuario=gestor,
            recurso="estudante",
            recurso_id=estudante.id,
            removido=dados.contato_emergencia_nome is None,
        )
    salvar(db, CONFLITO)
    return EstudanteLer.model_validate(estudante)


@router.delete(
    "/{estudante_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[exigir_perfil(Perfil.ADMIN)],
)
def remover(estudante_id: IdRota, db: Db) -> None:
    estudante = buscar(db, Estudante, estudante_id)
    arquivo = estudante.foto_arquivo
    db.delete(estudante)
    salvar(db, "O estudante tem registros vinculados")
    fotos.apagar(arquivo)


@router.put("/{estudante_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
def enviar_foto(
    estudante_id: IdRota,
    request: Request,
    db: Db,
    gestor: Editor,
    foto: Annotated[UploadFile, File()],
) -> None:
    estudante = buscar(db, Estudante, estudante_id)
    novo = fotos.salvar(foto.file.read(fotos.MAX_BYTES + 1))
    antigo, estudante.foto_arquivo = estudante.foto_arquivo, novo
    auditoria.registrar(
        db,
        "foto.enviar",
        request=request,
        usuario=gestor,
        recurso="estudante",
        recurso_id=estudante_id,
    )
    db.commit()
    fotos.apagar(antigo)


@router.delete("/{estudante_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
def remover_foto(estudante_id: IdRota, request: Request, db: Db, gestor: Editor) -> None:
    estudante = buscar(db, Estudante, estudante_id)
    antigo, estudante.foto_arquivo = estudante.foto_arquivo, None
    auditoria.registrar(
        db,
        "foto.remover",
        request=request,
        usuario=gestor,
        recurso="estudante",
        recurso_id=estudante_id,
    )
    db.commit()
    fotos.apagar(antigo)


@router.get("/{estudante_id}/foto-url")
def url_da_foto(estudante_id: IdRota, db: Db, _: UsuarioInterno) -> FotoUrl:
    return url_assinada(buscar(db, Estudante, estudante_id))


def url_assinada(estudante: Estudante) -> FotoUrl:
    if estudante.foto_arquivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante sem foto")
    token, expira = fotos.assinar(estudante.id)
    return FotoUrl(url=f"/fotos/{token}", expira_em=expira)
