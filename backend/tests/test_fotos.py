"""Foto do estudante: upload restrito, metadados removidos, acesso só por URL assinada."""

import io
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from PIL import Image

from app.config import settings
from app.models import Perfil, ResponsavelEstudante
from app.security import ALGORITMO, criar_token
from tests.conftest import estudante_de_teste


@pytest.fixture(autouse=True)
def pasta_de_fotos(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fotos_dir", str(tmp_path / "fotos"))
    return tmp_path / "fotos"


def _imagem(formato="JPEG", tamanho=(64, 48), gps=False) -> bytes:
    imagem = Image.new("RGB", tamanho, "red")
    saida = io.BytesIO()
    if gps:
        exif = Image.Exif()
        # 0x8825 é o bloco GPS; 0x010F é o fabricante da câmera.
        exif[0x010F] = "CameraX"
        exif[0x8825] = {1: "S", 2: (25.0, 25.0, 48.0), 3: "W", 4: (49.0, 16.0, 12.0)}
        imagem.save(saida, formato, exif=exif)
    else:
        imagem.save(saida, formato)
    return saida.getvalue()


def _enviar(client, h, estudante, conteudo, nome="foto.jpg", tipo="image/jpeg"):
    return client.put(
        f"/estudantes/{estudante.id}/foto", files={"foto": (nome, conteudo, tipo)}, headers=h
    )


def test_gestor_envia_e_a_foto_sai_por_url_assinada(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    assert _enviar(client, h, estudante, _imagem()).status_code == 204

    ficha = client.get(f"/estudantes/{estudante.id}", headers=h).json()
    assert ficha["tem_foto"] is True
    assert "foto_arquivo" not in ficha
    assert ".jpg" not in str(ficha)

    url = client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).json()["url"]
    assert url.startswith("/fotos/")
    # A URL basta: quem a recebeu não precisa de login para abrir a imagem, enquanto valer.
    imagem = client.get(url)
    assert imagem.status_code == 200
    assert imagem.headers["content-type"] == "image/jpeg"
    assert "no-store" in imagem.headers["cache-control"]
    assert Image.open(io.BytesIO(imagem.content)).size == (64, 48)


def test_gps_e_demais_metadados_sao_descartados(client, db, cabecalhos, pasta_de_fotos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    original = _imagem(gps=True)
    assert len(Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825)) > 0

    assert _enviar(client, h, estudante, original).status_code == 204
    url = client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).json()["url"]
    salva = Image.open(io.BytesIO(client.get(url).content))
    assert len(salva.getexif()) == 0
    assert len(salva.getexif().get_ifd(0x8825)) == 0


def test_foto_grande_e_reduzida(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    _enviar(client, h, estudante, _imagem(tamanho=(2000, 1000)))
    url = client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).json()["url"]
    assert max(Image.open(io.BytesIO(client.get(url).content)).size) == 512


@pytest.mark.parametrize("perfil", [Perfil.MOTORISTA, Perfil.MONITOR, Perfil.RESPONSAVEL])
def test_so_gestor_envia_e_remove(client, db, cabecalhos, perfil):
    estudante = estudante_de_teste(db)
    h = cabecalhos(perfil)
    assert _enviar(client, h, estudante, _imagem()).status_code == 403
    assert client.delete(f"/estudantes/{estudante.id}/foto", headers=h).status_code == 403
    assert client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).status_code == 403


@pytest.mark.parametrize(
    ("conteudo", "nome", "tipo"),
    [
        (b"nao sou imagem", "foto.jpg", "image/jpeg"),
        (b"", "foto.jpg", "image/jpeg"),
        (
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            "a.svg",
            "image/svg+xml",
        ),
        (_imagem("GIF"), "a.gif", "image/gif"),
        (_imagem("BMP"), "a.bmp", "image/bmp"),
        (b"%PDF-1.4 falso", "a.pdf", "application/pdf"),
    ],
)
def test_so_aceita_jpeg_png_webp_de_verdade(client, db, cabecalhos, conteudo, nome, tipo):
    estudante = estudante_de_teste(db)
    resposta = _enviar(client, cabecalhos(Perfil.GESTOR), estudante, conteudo, nome, tipo)
    assert resposta.status_code == 422
    assert estudante.foto_arquivo is None


def test_png_e_webp_viram_jpeg(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    for formato in ("PNG", "WEBP"):
        assert _enviar(client, h, estudante, _imagem(formato)).status_code == 204
    url = client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).json()["url"]
    assert Image.open(io.BytesIO(client.get(url).content)).format == "JPEG"


def test_arquivo_enorme_e_recusado(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    assert _enviar(client, h, estudante, b"\xff\xd8\xff" + b"0" * 950_000).status_code == 422
    assert _enviar(client, h, estudante, b"\xff\xd8\xff" + b"0" * 2_000_000).status_code == 413


def test_trocar_e_remover_apaga_o_arquivo_antigo(client, db, cabecalhos, pasta_de_fotos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    _enviar(client, h, estudante, _imagem())
    primeiro = {p.name for p in pasta_de_fotos.iterdir()}
    _enviar(client, h, estudante, _imagem(tamanho=(10, 10)))
    segundo = {p.name for p in pasta_de_fotos.iterdir()}
    assert len(segundo) == 1
    assert segundo != primeiro

    assert client.delete(f"/estudantes/{estudante.id}/foto", headers=h).status_code == 204
    assert list(pasta_de_fotos.iterdir()) == []
    assert client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).status_code == 404


def test_remover_estudante_apaga_a_foto(client, db, cabecalhos, pasta_de_fotos):
    estudante = estudante_de_teste(db)
    _enviar(client, cabecalhos(Perfil.GESTOR), estudante, _imagem())
    assert (
        client.delete(f"/estudantes/{estudante.id}", headers=cabecalhos(Perfil.ADMIN)).status_code
        == 204
    )
    assert list(pasta_de_fotos.iterdir()) == []


def _token(estudante_id, tipo="foto", expira=None, segredo=None):
    payload = {
        "sub": str(estudante_id),
        "typ": tipo,
        "exp": expira or datetime.now(UTC) + timedelta(minutes=5),
    }
    return jwt.encode(payload, segredo or settings.jwt_secret, algorithm=ALGORITMO)


def test_urls_invalidas_dao_404(client, db, cabecalhos, criar_usuario):
    estudante = estudante_de_teste(db)
    _enviar(client, cabecalhos(Perfil.GESTOR), estudante, _imagem())
    passado = datetime.now(UTC) - timedelta(seconds=1)
    acesso = criar_token(criar_usuario(Perfil.ADMIN))
    for token in (
        "lixo",
        _token(estudante.id, expira=passado),
        _token(estudante.id, tipo="access"),
        _token(estudante.id, segredo="x" * 40),
        _token(999999),
        acesso,
    ):
        assert client.get(f"/fotos/{token}").status_code == 404
    assert client.get(f"/fotos/{_token(estudante.id)}").status_code == 200


def test_url_vale_poucos_minutos(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    h = cabecalhos(Perfil.GESTOR)
    _enviar(client, h, estudante, _imagem())
    resposta = client.get(f"/estudantes/{estudante.id}/foto-url", headers=h).json()
    expira = datetime.fromisoformat(resposta["expira_em"])
    assert timedelta(seconds=250) < expira - datetime.now(UTC) <= timedelta(seconds=300)


def test_responsavel_ve_so_a_foto_do_proprio_filho_depois_do_consentimento(
    client, db, cabecalhos, criar_usuario
):
    filho, outro = estudante_de_teste(db, "Bia"), estudante_de_teste(db, "Caio")
    gestor = cabecalhos(Perfil.GESTOR)
    for e in (filho, outro):
        _enviar(client, gestor, e, _imagem())
    mae = criar_usuario(Perfil.RESPONSAVEL)
    vinculo = ResponsavelEstudante(responsavel_id=mae.id, estudante_id=filho.id, parentesco="mãe")
    db.add(vinculo)
    db.flush()
    h = {"Authorization": f"Bearer {criar_token(mae)}"}

    assert client.get(f"/responsavel/filhos/{filho.id}/foto-url", headers=h).status_code == 403
    vinculo.consentimento_em = datetime.now(UTC)
    vinculo.consentimento_versao = settings.versao_termo_consentimento
    db.flush()
    assert client.get(f"/responsavel/filhos/{filho.id}/foto-url", headers=h).status_code == 200
    assert client.get(f"/responsavel/filhos/{outro.id}/foto-url", headers=h).status_code == 404


def test_imagem_com_pixels_demais_e_recusada_antes_de_decodificar(client, db, cabecalhos):
    estudante = estudante_de_teste(db)
    # Pequeno em bytes, enorme em pixels: o tipo de arquivo que estoura a memória ao abrir.
    enorme = _imagem("PNG", tamanho=(4000, 3500))
    assert len(enorme) < 900_000
    r = _enviar(client, cabecalhos(Perfil.GESTOR), estudante, enorme, "f.png", "image/png")
    assert r.status_code == 422
    assert estudante.foto_arquivo is None
