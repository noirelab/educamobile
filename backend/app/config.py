from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de exemplo publicados no repositório. Quem os usa assina tokens com uma chave pública.
_SEGREDOS_DE_EXEMPLO = {"troque-por-um-segredo-com-pelo-menos-32-caracteres"}
_SENHA_DE_BANCO_DE_EXEMPLO = "troque-esta-senha"
MIN_CARACTERES_DISTINTOS = 12


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    ambiente: Literal["desenvolvimento", "producao"] = "desenvolvimento"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    # Curto de propósito: o refresh token renova o acesso sem pedir a senha de novo.
    jwt_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_expire_days: int = Field(default=7, ge=1, le=30)
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5500"]
    # Atrás de um proxy reverso, o IP do cliente vem do cabeçalho X-Forwarded-For.
    confiar_proxy: bool = False
    versao_termo_consentimento: str = "2026-11"
    # Corpo maior que isso recebe 413 antes de ser lido.
    max_corpo_bytes: int = Field(default=1_000_000, ge=10_000)
    # Onde ficam as fotos dos estudantes. Em produção, um volume fora da imagem.
    # "redis" compartilha os limites entre processos da API; produção exige.
    limite_backend: Literal["memoria", "redis"] = "memoria"
    redis_url: str = "redis://localhost:6379/0"
    # Os horários previstos das paradas são hora do relógio local.
    fuso_horario: str = "America/Sao_Paulo"
    # Conta de serviço do Firebase (arquivo JSON) e id do projeto; sem elas o push vai ao log.
    fcm_credenciais: str | None = None
    fcm_projeto: str | None = None
    fotos_dir: str = "fotos"
    foto_url_validade_s: int = Field(default=300, ge=30, le=3600)

    @field_validator("jwt_secret")
    @classmethod
    def segredo_forte(cls, valor: str) -> str:
        if valor in _SEGREDOS_DE_EXEMPLO:
            raise ValueError("JWT_SECRET ainda é o valor de exemplo do .env.example; gere outro")
        if len(set(valor)) < MIN_CARACTERES_DISTINTOS:
            raise ValueError("JWT_SECRET previsível demais; gere com secrets.token_urlsafe(48)")
        return valor

    @model_validator(mode="after")
    def producao_segura(self) -> Self:
        if self.ambiente == "producao":
            if _SENHA_DE_BANCO_DE_EXEMPLO in self.database_url:
                raise ValueError("A senha do banco ainda é a do .env.example")
            if self.limite_backend != "redis":
                raise ValueError("Em produção, LIMITE_BACKEND precisa ser redis")
            inseguras = [o for o in self.cors_origins if not o.startswith("https://")]
            if inseguras:
                raise ValueError(f"Em produção, CORS só aceita origens https: {inseguras}")
        return self


settings = Settings()
