from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models import Sentido, StatusAluno, StatusViagem, Turno


class PosicaoEntrada(BaseModel):
    registrada_em: datetime
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    velocidade_kmh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    precisao_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def com_fuso(self) -> "PosicaoEntrada":
        if self.registrada_em.tzinfo is None:
            raise ValueError(
                "registrada_em precisa informar o fuso (ex.: 2026-11-23T07:05:00-03:00)"
            )
        return self


class LotePosicoes(BaseModel):
    posicoes: Annotated[list[PosicaoEntrada], Field(min_length=1, max_length=500)]


class ResultadoPosicao(BaseModel):
    registrada_em: datetime
    resultado: str
    motivo: str | None = None


class PosicaoAtual(BaseModel):
    viagem_id: int
    latitude: float
    longitude: float
    registrada_em: datetime
    velocidade_kmh: float | None
    desvio_m: float | None = None


class Previsao(BaseModel):
    parada_id: int
    distancia_restante_m: int
    eta_segundos: int | None


class ProximaParada(BaseModel):
    parada_id: int
    nome: str
    horario_previsto: str | None
    previsao: Previsao | None


class EstadoAoVivo(BaseModel):
    posicao: PosicaoAtual | None
    proxima_parada: ProximaParada | None


class PontoDoPercurso(BaseModel):
    registrada_em: datetime
    latitude: float
    longitude: float
    velocidade_kmh: float | None


class TokenRastreador(BaseModel):
    token: str


# Acompanhamento do responsável. Nada aqui identifica outras crianças da viagem.


class PosicaoDoOnibus(BaseModel):
    latitude: float
    longitude: float
    registrada_em: datetime
    velocidade_kmh: float | None


class OnibusDoFilho(BaseModel):
    placa: str | None
    motorista_nome: str | None


class ViagemDoFilho(BaseModel):
    viagem_id: int
    sentido: Sentido
    turno: Turno
    status_viagem: StatusViagem
    situacao_do_filho: StatusAluno
    parada_nome: str | None
    onibus: OnibusDoFilho
    posicao: PosicaoDoOnibus | None
    previsao: Previsao | None


class FilhoHoje(BaseModel):
    estudante_id: int
    nome: str
    data: date
    viagens: list[ViagemDoFilho]


# Painel da frota


class ItemDaFrota(BaseModel):
    viagem_id: int
    rota_id: int
    rota_nome: str
    escola_id: int
    turno: Turno
    sentido: Sentido
    status: StatusViagem
    placa: str | None
    motorista_nome: str | None
    posicao: PosicaoAtual | None
    atraso_min: int | None
    alunos_a_bordo: int
    alertas_abertos: int
