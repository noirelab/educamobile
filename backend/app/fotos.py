"""Fotos dos estudantes.

A imagem é reconstruída com Pillow: isso confirma que é uma imagem de verdade e descarta os
metadados (EXIF costuma trazer o GPS de onde a foto foi tirada). O arquivo fica no disco com nome
aleatório e só sai por URL assinada de curta duração, nunca dentro do JSON do estudante.
"""

import io
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.security import ALGORITMO

TIPO_FOTO = "foto"
# Abaixo do limite global de corpo (1 MB), que barra a requisição antes de ela chegar aqui.
MAX_BYTES = 900_000
MAX_LADO = 512
# Barra imagens que explodem na memória ao abrir (bomba de descompressão).
Image.MAX_IMAGE_PIXELS = 25_000_000


def _pasta() -> Path:
    pasta = Path(settings.fotos_dir)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _recusar(detalhe: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detalhe)


def salvar(conteudo: bytes) -> str:
    """Valida, reencoda em JPEG sem metadados e devolve o nome do arquivo."""
    if not conteudo or len(conteudo) > MAX_BYTES:
        raise _recusar("Foto vazia ou maior que 900 KB")
    try:
        with Image.open(io.BytesIO(conteudo)) as original:
            if original.format not in {"JPEG", "PNG", "WEBP"}:
                raise _recusar("Use uma foto JPEG, PNG ou WEBP")
            imagem = ImageOps.exif_transpose(original).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise _recusar("Arquivo não é uma imagem válida") from erro
    imagem.thumbnail((MAX_LADO, MAX_LADO))
    nome = f"{secrets.token_urlsafe(24)}.jpg"
    imagem.save(_pasta() / nome, "JPEG", quality=85)
    return nome


def apagar(nome: str | None) -> None:
    if nome:
        (_pasta() / Path(nome).name).unlink(missing_ok=True)


def caminho(nome: str) -> Path:
    return _pasta() / Path(nome).name


def assinar(estudante_id: int) -> tuple[str, datetime]:
    expira = datetime.now(UTC) + timedelta(seconds=settings.foto_url_validade_s)
    token = jwt.encode(
        {"sub": str(estudante_id), "typ": TIPO_FOTO, "exp": expira},
        settings.jwt_secret,
        algorithm=ALGORITMO,
    )
    return token, expira


def verificar(token: str) -> int:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[ALGORITMO], options={"require": ["exp", "sub"]}
        )
        if payload.get("typ") != TIPO_FOTO:
            raise ValueError
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError) as erro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada") from erro
