from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from pydantic import BaseModel, Field
from shapely.geometry import Point

from app.models import SRID


class Coordenadas(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


def para_ponto(coordenadas: Coordenadas) -> WKBElement:
    return from_shape(Point(coordenadas.longitude, coordenadas.latitude), srid=SRID)


def de_ponto(ponto: WKBElement | None) -> Coordenadas | None:
    if ponto is None:
        return None
    shape = to_shape(ponto)
    return Coordenadas(latitude=shape.y, longitude=shape.x)
