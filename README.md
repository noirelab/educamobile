# EducaMobile Smart City

Projeto Integrador II (UTFPR). API em FastAPI com PostgreSQL e PostGIS.

## Subir o ambiente

```sh
cp .env.example .env      # troque a senha e o JWT_SECRET
docker compose up -d --build
docker compose exec api .venv/bin/python -m app.criar_admin admin@exemplo.com "Administrador"
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Banco: `localhost:5433` (a porta muda com `DB_PORT` no `.env`)

As migrações rodam sozinhas quando a API sobe.

## Desenvolver o backend

Com o serviço `db` no ar e o [uv](https://docs.astral.sh/uv/) instalado:

```sh
cd backend
uv run uvicorn app.main:app --reload --port 8000   # pare o serviço api antes, ou troque a porta
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run alembic revision --autogenerate -m "descrição"   # após mudar app/models.py
```

Os testes precisam do banco no ar. Cada execução cria um banco próprio e o remove ao final.

## Documentação

- `docs/tarefas.md`: tarefas do quadro
- `docs/modelo-er.md`: modelo de dados e decisões
- `docs/autenticacao.md`: login, perfis e permissões
