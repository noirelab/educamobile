from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import auditoria, tempo
from app.cadastros import Db, Deslocamento, IdRota, Limite, buscar, salvar
from app.models import Perfil, Usuario, Veiculo
from app.schemas.veiculos import VeiculoCriar, VeiculoLer, VeiculosPagina
from app.security import UsuarioInterno, exigir_perfil

router = APIRouter(prefix="/veiculos", tags=["veículos"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
CONFLITO = "Placa já cadastrada"


@router.get("")
def listar(
    db: Db,
    _: UsuarioInterno,
    placa: Annotated[str | None, Query(min_length=1, max_length=10)] = None,
    vistoria_vencida: bool | None = None,
    ativo: bool | None = None,
    limit: Limite = 50,
    offset: Deslocamento = 0,
) -> VeiculosPagina:
    filtros = []
    if placa:
        trecho = "".join(c for c in placa.upper() if c.isalnum())
        filtros.append(Veiculo.placa.like(f"%{trecho}%"))
    if vistoria_vencida is not None:
        hoje = tempo.hoje()
        filtros.append(
            Veiculo.vistoria_valida_ate < hoje
            if vistoria_vencida
            else Veiculo.vistoria_valida_ate >= hoje
        )
    if ativo is not None:
        filtros.append(Veiculo.ativo == ativo)
    total = db.scalar(select(func.count()).select_from(Veiculo).where(*filtros))
    itens = db.scalars(
        select(Veiculo).where(*filtros).order_by(Veiculo.placa).limit(limit).offset(offset)
    )
    return VeiculosPagina(total=total or 0, itens=[VeiculoLer.model_validate(v) for v in itens])


@router.get("/{veiculo_id}")
def obter(veiculo_id: IdRota, db: Db, _: UsuarioInterno) -> VeiculoLer:
    return VeiculoLer.model_validate(buscar(db, Veiculo, veiculo_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: VeiculoCriar, request: Request, db: Db, ator: Gestao) -> VeiculoLer:
    veiculo = Veiculo(**dados.model_dump())
    db.add(veiculo)
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, CONFLITO) from erro
    auditoria.registrar(
        db, "veiculo.criar", request=request, usuario=ator, recurso="veiculo", recurso_id=veiculo.id
    )
    salvar(db, CONFLITO)
    return VeiculoLer.model_validate(veiculo)


@router.put("/{veiculo_id}")
def atualizar(
    veiculo_id: IdRota, dados: VeiculoCriar, request: Request, db: Db, ator: Gestao
) -> VeiculoLer:
    veiculo = buscar(db, Veiculo, veiculo_id)
    for campo, valor in dados.model_dump().items():
        setattr(veiculo, campo, valor)
    auditoria.registrar(
        db,
        "veiculo.editar",
        request=request,
        usuario=ator,
        recurso="veiculo",
        recurso_id=veiculo.id,
    )
    salvar(db, CONFLITO)
    return VeiculoLer.model_validate(veiculo)


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(veiculo_id: IdRota, request: Request, db: Db, ator: Gestao) -> None:
    veiculo = buscar(db, Veiculo, veiculo_id)
    db.delete(veiculo)
    auditoria.registrar(
        db,
        "veiculo.remover",
        request=request,
        usuario=ator,
        recurso="veiculo",
        recurso_id=veiculo_id,
    )
    salvar(db, "O veículo está em uso")
