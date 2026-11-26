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
- Redis: só dentro da rede do Docker (última posição dos ônibus e tempo real)
- Banco: `localhost:5433` (a porta muda com `DB_PORT` no `.env`)

As migrações rodam sozinhas quando a API sobe.

A reformulação recomeçou as migrações do zero (migração `0001`). Quem já tinha um banco local precisa recriá-lo: `docker compose down -v` e subir de novo. Isso apaga os dados locais.

## Frontend

Com a API no ar, o serviço `web` sobe a interface em produção (nginx):

```sh
docker compose up -d --build web
```

- Interface: http://localhost:5173
- O servidor de desenvolvimento (`npm run dev` em `frontend/`) usa a mesma porta 5173: rode um ou o outro.
- A imagem chama a API em `http://localhost:8000` (argumento `VITE_API_URL` no `compose.yaml`).

Testes do frontend (com a API e o banco no ar):

```sh
cd frontend
npm run test
npm run e2e        # exige E2E_ADMIN_EMAIL e E2E_ADMIN_PASSWORD
```

## Desenvolver o backend

Com o serviço `db` no ar e o [uv](https://docs.astral.sh/uv/) instalado:

```sh
cd backend
uv run uvicorn app.main:app --reload --port 8000 --no-proxy-headers   # pare o serviço api antes, ou troque a porta
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run alembic revision --autogenerate -m "descrição"   # após mudar app/models.py
```

Os testes precisam do banco no ar. Cada execução cria um banco próprio e o remove ao final.

## Simulador e teste de carga

Dois scripts em `backend/tools/` reproduzem o que os aplicativos fariam, sem ninguém andar de ônibus. Servem para teste, para a demonstração e para o frontend trabalhar com dados vivos.

```sh
cd backend
# Um ônibus: entra como motorista, inicia a viagem do dia, anda pelas paradas, embarca e conclui.
uv run python -m tools.simulador --api http://localhost:8000 --email motorista@exemplo.com --senha ... \
    --velocidade 20 [--sem-sinal] [--desvio] [--crianca-a-bordo]

# Carga: cria N ônibus com motorista, veículo, rota e aluno, inicia as viagens e mede.
uv run python -m tools.carga --api http://localhost:8000 --admin-email admin@exemplo.com --admin-senha ... \
    --onibus 50 --paineis 5 --responsaveis 20 --duracao 60
```

- `--sem-sinal`: para de enviar no meio do trajeto e manda tudo de uma vez depois (modo offline).
- `--desvio`: sai do trajeto previsto num trecho (alerta de desvio de rota).
- `--crianca-a-bordo`: não registra um desembarque; a API recusa concluir a viagem e mostra quem falta.

**Números medidos** (uma máquina de desenvolvimento com 8 núcleos e 16 GB, API com um único processo `uvicorn`, PostgreSQL e Redis em contêiner, 60 s de teste, sem o worker rodando):

| 50 ônibus, 1 posição a cada 5 s | Resultado |
| --- | --- |
| POST de posição (600 requisições) | 0 erros; p50 12 ms, p95 21 ms, p99 40 ms |
| Mensagens entregues por WebSocket (5 painéis na frota e 20 responsáveis, 3234 mensagens) | 0 inscrições recusadas; atraso do envio até a chegada p50 11 ms, p95 20 ms, p99 38 ms |

É um teste de capacidade de uma máquina só, com clientes e servidor juntos; ele não substitui a medição no ambiente de produção.

## Documentação

- `docs/tempo-real.md`: posições, WebSocket, worker, alertas, push e relatórios
- `docs/lgpd.md`: dados guardados, prazos e consentimento
- `docs/tarefas.md` (obsoleto): tarefas do quadro anterior
- `docs/modelo-er.md`: modelo de dados e decisões
- `docs/autenticacao.md`: login, perfis e permissões
