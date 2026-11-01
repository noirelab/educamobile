from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.cadastros import IdBanco, Texto


class ProfessorCriar(BaseModel):
    nome: Texto
    email: EmailStr
    escola_id: IdBanco | None = None

    @field_validator("email")
    @classmethod
    def email_minusculo(cls, valor: str) -> str:
        return valor.lower()


class ProfessorLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    escola_id: int | None
