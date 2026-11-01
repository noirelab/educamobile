from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth,
    escolas,
    estudantes,
    frequencias,
    matriculas,
    paradas,
    polos,
    professores,
    rotas,
    turmas,
)

app = FastAPI(title="EducaMobile Smart City", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(polos.router)
app.include_router(escolas.router)
app.include_router(turmas.router)
app.include_router(estudantes.router)
app.include_router(professores.router)
app.include_router(paradas.router)
app.include_router(rotas.router)
app.include_router(matriculas.router)
app.include_router(frequencias.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}
