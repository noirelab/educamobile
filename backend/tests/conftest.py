"""Cada execução usa um banco PostGIS próprio, criado e removido aqui.

Cada teste roda em uma transação desfeita ao final, então os testes não interferem entre si.
"""

import uuid
from collections.abc import Callable, Iterator
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
from app.models import Escola, Perfil, Usuario  # noqa: E402
from app.security import criar_token, gerar_hash  # noqa: E402

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
    def criar(
        perfil: Perfil = Perfil.ADMIN, escola_id: int | None = None, senha: str = "senha-forte-1"
    ):
        usuario = Usuario(
            nome=f"Usuário {perfil.value}",
            email=f"{uuid.uuid4().hex[:10]}@exemplo.com",
            senha_hash=gerar_hash(senha),
            perfil=perfil,
            escola_id=escola_id,
        )
        db.add(usuario)
        db.flush()
        return usuario

    return criar


@pytest.fixture
def cabecalhos(criar_usuario, criar_escola) -> Callable[..., dict[str, str]]:
    """Cabeçalho Authorization de um usuário do perfil pedido. Diretor sem escola ganha uma."""

    def criar(perfil: Perfil = Perfil.ADMIN, escola_id: int | None = None) -> dict[str, str]:
        if perfil == Perfil.DIRETOR and escola_id is None:
            escola_id = criar_escola().id
        usuario = criar_usuario(perfil, escola_id)
        return {"Authorization": f"Bearer {criar_token(usuario)}"}

    return criar
