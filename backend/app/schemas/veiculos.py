import re
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field

from app.cadastros import Texto

# Placa antiga (ABC1234) e Mercosul (ABC1D23).
_PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


def normalizar_placa(valor: str) -> str:
    placa = re.sub(r"[\s-]", "", valor).upper()
    if not _PLACA.match(placa):
        raise ValueError("Placa inválida: use ABC1234 ou ABC1D23")
    return placa


Placa = Annotated[str, AfterValidator(normalizar_placa)]


class VeiculoCriar(BaseModel):
    placa: Placa
    capacidade: int = Field(ge=1, le=100)
    modelo: Texto
    ano: int = Field(ge=1980, le=2100)
    vistoria_valida_ate: date
    ativo: bool = True


class VeiculoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa: str
    capacidade: int
    modelo: str
    ano: int
    vistoria_valida_ate: date
    ativo: bool

    @computed_field
    @property
    def vistoria_vencida(self) -> bool:
        return self.vistoria_valida_ate < date.today()


class VeiculosPagina(BaseModel):
    total: int
    itens: list[VeiculoLer]
