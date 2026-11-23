"""Cada execução usa um banco PostGIS próprio, criado e removido aqui.

Cada teste roda em uma transação desfeita ao final, então os testes não interferem entre si.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings

_url_base = make_url(settings.database_url)
_nome_banco = f"educamobile_test_{uuid.uuid4().hex[:8]}"
settings.database_url = _url_base.set(database=_nome_banco).render_as_string(hide_password=False)

from app import db as app_db  # noqa: E402
from app.geo import Coordenadas, para_ponto  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Escola, Estudante, Perfil, Rota, Sentido, Turno, Usuario  # noqa: E402
from app.security import criar_token, gerar_hash  # noqa: E402


def estudante_de_teste(db: Session, nome: str = "Ana", **campos) -> Estudante:
    """Estudante válido; cria uma escola própria quando `escola_id` não é informado."""
    if "escola_id" not in campos:
        escola = Escola(
            nome=f"Escola de {nome}",
            localizacao=para_ponto(Coordenadas(latitude=-25.4, longitude=-49.2)),
        )
        db.add(escola)
        db.flush()
        campos["escola_id"] = escola.id
    campos.setdefault("data_nascimento", date(2015, 1, 1))
    campos.setdefault("turno", Turno.MANHA)
    estudante = Estudante(nome=nome, **campos)
    db.add(estudante)
    db.flush()
    return estudante


def escola_de_teste(
    db: Session,
    nome: str = "Escola",
    latitude: float = -25.4,
    longitude: float = -49.2,
    raio_cerca_m: int = 10_000_000,
) -> Escola:
    """Escola com cerca enorme por padrão: testes de geometria não esbarram na regra da escola."""
    escola = Escola(
        nome=nome,
        localizacao=para_ponto(Coordenadas(latitude=latitude, longitude=longitude)),
        raio_cerca_m=raio_cerca_m,
    )
    db.add(escola)
    db.flush()
    return escola


def rota_de_teste(db: Session, nome: str = "Linha 1", **campos) -> Rota:
    """Rota válida no banco; cria uma escola própria quando `escola_id` não é informado."""
    if "escola_id" not in campos:
        campos["escola_id"] = escola_de_teste(db, f"Escola da {nome}").id
    campos.setdefault("turno", Turno.MANHA)
    campos.setdefault("sentido", Sentido.IDA)
    rota = Rota(nome=nome, **campos)
    db.add(rota)
    db.flush()
    return rota


def corpo_de_rota(db: Session, nome: str = "Linha 1", **campos) -> dict:
    """Corpo válido de POST /rotas, com uma escola criada no banco."""
    if "escola_id" not in campos:
        campos["escola_id"] = escola_de_teste(db, f"Escola da {nome}").id
    return {"nome": nome, "turno": "manha", "sentido": "ida", **campos}


BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def banco_de_teste() -> Iterator[None]:
    admin = create_engine(_url_base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        conexao.execute(text(f'CREATE DATABASE "{_nome_banco}"'))
    try:
        config = Config(BACKEND / "alembic.ini")
        config.set_main_option("script_location", str(BACKEND / "migrations"))
        command.upgrade(config, "head")
        yield
    finally:
        app_db.engine.dispose()
        with admin.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{_nome_banco}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(autouse=True)
def redis_limpo() -> None:
    """Última posição e pub/sub vivem no Redis: cada teste começa sem nada dos anteriores."""
    from app import tempo_real

    tempo_real.cliente().flushdb()


@pytest.fixture(autouse=True)
def limites_zerados(monkeypatch) -> None:
    """Todos os testes vêm do mesmo cliente; sem isso, o limite por IP vazaria entre eles."""
    from app.limite import LimiteEmMemoria
    from app.routers import auth

    for nome in (
        "limite_login",
        "limite_login_ip",
        "limite_login_conta",
        "limite_troca_senha",
        "limite_convite",
    ):
        atual = getattr(auth, nome)
        monkeypatch.setattr(auth, nome, LimiteEmMemoria(atual.maximo, atual.janela_s))
    from app import limite

    for nome in ("limite_escrita", "limite_posicoes"):
        atual = getattr(limite, nome)
        monkeypatch.setattr(limite, nome, LimiteEmMemoria(atual.maximo, atual.janela_s))


@pytest.fixture
def db() -> Iterator[Session]:
    with app_db.engine.connect() as conexao:
        transacao = conexao.begin()
        sessao = Session(
            bind=conexao, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield sessao
        finally:
            sessao.close()
            transacao.rollback()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[app_db.get_db] = lambda: db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def criar_escola(db: Session) -> Callable[..., Escola]:
    def criar(nome: str = "Escola Teste", latitude: float = -25.43, longitude: float = -49.27):
        escola = Escola(
            nome=nome,
            localizacao=para_ponto(Coordenadas(latitude=latitude, longitude=longitude)),
        )
        db.add(escola)
        db.flush()
        return escola

    return criar


@pytest.fixture
def criar_usuario(db: Session) -> Callable[..., Usuario]:
    def criar(perfil: Perfil = Perfil.ADMIN, senha: str = "senha-forte-1"):
        usuario = Usuario(
            nome=f"Usuário {perfil.value}",
            email=f"{uuid.uuid4().hex[:10]}@exemplo.com",
            senha_hash=gerar_hash(senha),
            perfil=perfil,
        )
        db.add(usuario)
        db.flush()
        return usuario

    return criar


@pytest.fixture
def cabecalhos(criar_usuario) -> Callable[..., dict[str, str]]:
    """Cabeçalho Authorization de um usuário do perfil pedido."""

    def criar(perfil: Perfil = Perfil.ADMIN) -> dict[str, str]:
        usuario = criar_usuario(perfil)
        return {"Authorization": f"Bearer {criar_token(usuario)}"}

    return criar
