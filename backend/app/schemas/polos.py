from typing import Annotated, Literal, Self

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
from shapely.geometry import mapping, shape

from app.cadastros import Texto


class MultiPolygonGeoJSON(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[tuple[float, float]]]]

    @model_validator(mode="after")
    def geometria_valida(self) -> Self:
        if not self.coordinates or not all(self.coordinates):
            raise ValueError("MultiPolygon sem polígonos")
        for poligono in self.coordinates:
            for anel in poligono:
                if len(anel) < 4 or anel[0] != anel[-1]:
                    raise ValueError("Cada anel precisa de 4 pontos ou mais e deve ser fechado")
                for longitude, latitude in anel:
                    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                        raise ValueError("Coordenada fora do intervalo [longitude, latitude]")
        if not shape(self.model_dump()).is_valid:
            raise ValueError("Geometria inválida, por exemplo, com autointerseção")
        return self


def _ler_area(valor):
    return mapping(to_shape(valor)) if isinstance(valor, WKBElement) else valor


class PoloCriar(BaseModel):
    nome: Texto
    area: MultiPolygonGeoJSON | None = None


class PoloLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    area: Annotated[MultiPolygonGeoJSON | None, BeforeValidator(_ler_area)]
