from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings, settings
from app.limite import limitar_escrita
from app.routers import (
    alertas,
    auth,
    escolas,
    estudantes,
    fotos,
    inscricoes,
    motoristas,
    paradas,
    rastreamento,
    registros,
    responsaveis,
    rotas,
    usuarios,
    veiculos,
    viagens,
    ws,
)

_CAMINHOS_DOCS = ("/docs", "/redoc", "/openapi.json")
_CABECALHOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    # Respostas trazem dados de crianças: nenhum cache intermediário pode guardá-las.
    "Cache-Control": "no-store",
}


class LimiteDeCorpo:
    """Recusa com 413 corpos acima do limite, antes de a aplicação lê-los inteiros na memória.

    Confere o Content-Length declarado e também conta os bytes recebidos, porque um corpo em
    partes (chunked) não declara tamanho. Ao estourar, responde 413 na hora, encerra a leitura
    e descarta o que a aplicação tentar enviar depois.
    """

    def __init__(self, app: ASGIApp, maximo: int) -> None:
        self.app = app
        self.maximo = maximo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declarado = dict(scope["headers"]).get(b"content-length")
        if declarado is not None and (not declarado.isdigit() or int(declarado) > self.maximo):
            await _recusar(send)
            return
        recebidos = 0
        recusado = False
        resposta_iniciada = False

        async def receber() -> Message:
            nonlocal recebidos, recusado
            if recusado:
                return {"type": "http.disconnect"}
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > self.maximo:
                    recusado = True
                    if not resposta_iniciada:
                        await _recusar(send)
                    return {"type": "http.disconnect"}
            return mensagem

        async def enviar(mensagem: Message) -> None:
            nonlocal resposta_iniciada
            if recusado:
                return
            resposta_iniciada = resposta_iniciada or mensagem["type"] == "http.response.start"
            await send(mensagem)

        await self.app(scope, receber, enviar)


async def _recusar(send: Send) -> None:
    resposta = JSONResponse(
        {"detail": "Requisição grande demais"},
        status_code=413,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )
    await send({"type": "http.response.start", "status": 413, "headers": resposta.raw_headers})
    await send({"type": "http.response.body", "body": resposta.body})


def _texto_seguro(valor) -> str | int:
    if isinstance(valor, int):
        return valor
    return str(valor).encode("utf-8", "replace").decode("utf-8")


async def erro_de_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """Responde 422 sem repetir o valor enviado.

    O padrão do FastAPI devolve a entrada recebida. Isso ecoava senhas e quebrava com 500 diante
    de NaN, Infinity, JSON aninhado demais ou texto com caracteres inválidos.
    """
    detalhes = [
        {
            "loc": [_texto_seguro(parte) for parte in item.get("loc", ())],
            "msg": _texto_seguro(item.get("msg", "")),
            "type": _texto_seguro(item.get("type", "")),
        }
        for item in erro.errors()
    ]
    return JSONResponse({"detail": detalhes}, status_code=422)


def criar_app(config: Settings = settings) -> FastAPI:
    producao = config.ambiente == "producao"
    app = FastAPI(
        title="EducaMobile Smart City",
        version="0.1.0",
        docs_url=None if producao else "/docs",
        redoc_url=None if producao else "/redoc",
        openapi_url=None if producao else "/openapi.json",
    )
    app.add_exception_handler(RequestValidationError, erro_de_validacao)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, call_next):
        resposta = await call_next(request)
        for nome, valor in _CABECALHOS.items():
            resposta.headers.setdefault(nome, valor)
        # O Swagger carrega scripts de CDN; a política restrita vale para o resto da API.
        if not request.url.path.startswith(_CAMINHOS_DOCS):
            resposta.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if producao:
            resposta.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return resposta

    # Adicionado por último para ser o primeiro a receber a requisição.
    app.add_middleware(LimiteDeCorpo, maximo=config.max_corpo_bytes)

    for modulo in (
        alertas,
        auth,
        escolas,
        estudantes,
        fotos,
        inscricoes,
        motoristas,
        veiculos,
        paradas,
        rastreamento,
        registros,
        rotas,
        responsaveis,
        usuarios,
        viagens,
    ):
        app.include_router(modulo.router, dependencies=[Depends(limitar_escrita)])
    # WebSocket fica de fora: a dependência de requisição HTTP não vale para ele.
    app.include_router(ws.router)

    @app.get("/health", tags=["infra"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = criar_app()
