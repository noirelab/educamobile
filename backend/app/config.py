from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @model_validator(mode="after")
    def producao_segura(self) -> Self:
        if self.ambiente == "producao":
            inseguras = [o for o in self.cors_origins if not o.startswith("https://")]
            if inseguras:
                raise ValueError(f"Em produção, CORS só aceita origens https: {inseguras}")
        return self


settings = Settings()
