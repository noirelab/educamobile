from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, settings
from app.routers import (
    auth,
    escolas,
    estudantes,
    frequencias,
    matriculas,
    paradas,
    polos,
    professores,
    responsaveis,
    rotas,
    turmas,
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


def criar_app(config: Settings = settings) -> FastAPI:
    producao = config.ambiente == "producao"
    app = FastAPI(
        title="EducaMobile Smart City",
        version="0.1.0",
        docs_url=None if producao else "/docs",
        redoc_url=None if producao else "/redoc",
        openapi_url=None if producao else "/openapi.json",
    )
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

    for modulo in (
        auth,
        polos,
        escolas,
        turmas,
        estudantes,
        professores,
        paradas,
        rotas,
        matriculas,
        frequencias,
        responsaveis,
    ):
        app.include_router(modulo.router)

    @app.get("/health", tags=["infra"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = criar_app()
