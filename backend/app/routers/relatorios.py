"""Relatórios do transporte em JSON ou CSV. Só a gestão lê; exportar vai para a auditoria."""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app import auditoria, relatorios
from app.cadastros import Db
from app.models import Perfil, Usuario
from app.relatorios import Filtro
from app.security import exigir_perfil

router = APIRouter(prefix="/relatorios", tags=["relatórios"])
Gestao = Annotated[Usuario, exigir_perfil(Perfil.ADMIN, Perfil.GESTOR)]
# Um período maior que isso vira consulta pesada sem utilidade; peça por partes.
MAX_DIAS = 366
ESCOLA_E_ROTA = Annotated[int | None, Query(ge=1, le=2_147_483_647)]


def _filtro(
    de: date | None, ate: date | None, rota_id: int | None, escola_id: int | None
) -> Filtro:
    fim = ate or date.today()
    inicio = de or fim - timedelta(days=29)
    if inicio > fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "`de` não pode ser depois de `ate`"
        )
    if (fim - inicio).days > MAX_DIAS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"O período não pode passar de {MAX_DIAS} dias"
        )
    return Filtro(de=inicio, ate=fim, rota_id=rota_id, escola_id=escola_id)


def _responder(
    nome: str,
    funcao,
    request: Request,
    db: Db,
    gestor: Usuario,
    filtro: Filtro,
    formato: str,
):
    linhas, resumo = funcao(db, filtro)
    if formato == "csv":
        auditoria.registrar(
            db,
            "relatorio.exportar",
            request=request,
            usuario=gestor,
            recurso="relatorio",
            recurso_id=nome,
            filtros=filtro.como_dict(),
            linhas=len(linhas),
        )
        db.commit()
        arquivo = f"{nome}-{filtro.de.isoformat()}-{filtro.ate.isoformat()}.csv"
        return Response(
            relatorios.para_csv(linhas),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{arquivo}"'},
        )
    return {"filtro": filtro.como_dict(), "resumo": resumo, "linhas": linhas}


def _rota_do_relatorio(nome: str, funcao):
    def endpoint(
        request: Request,
        db: Db,
        gestor: Gestao,
        de: date | None = None,
        ate: date | None = None,
        rota_id: ESCOLA_E_ROTA = None,
        escola_id: ESCOLA_E_ROTA = None,
        formato: Literal["json", "csv"] = "json",
    ):
        filtro = _filtro(de, ate, rota_id, escola_id)
        return _responder(nome, funcao, request, db, gestor, filtro, formato)

    endpoint.__name__ = f"relatorio_{nome}"
    router.add_api_route(f"/{nome}", endpoint, methods=["GET"], summary=f"Relatório de {nome}")


for _nome, _funcao in (
    ("viagens", relatorios.viagens),
    ("pontualidade", relatorios.pontualidade),
    ("ausencias", relatorios.ausencias),
    ("ocorrencias", relatorios.ocorrencias),
):
    _rota_do_relatorio(_nome, _funcao)
