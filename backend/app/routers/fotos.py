from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app import fotos
from app.cadastros import Db
from app.models import Estudante

router = APIRouter(tags=["fotos"])


@router.get("/fotos/{token}", response_class=FileResponse)
def servir_foto(token: str, db: Db) -> FileResponse:
    """A autorização está na assinatura da URL, que vence em poucos minutos."""
    estudante = db.get(Estudante, fotos.verificar(token))
    if estudante is None or estudante.foto_arquivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada")
    arquivo = fotos.caminho(estudante.foto_arquivo)
    if not arquivo.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada")
    return FileResponse(
        arquivo, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
    )
