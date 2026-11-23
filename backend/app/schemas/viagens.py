import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.cadastros import IdBanco
from app.geo import Coordenadas
from app.models import Sentido, StatusAluno, StatusViagem, TipoEvento, Turno

Motivo = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=5, max_length=500, pattern=r"^[^\x00]+$"),
]


class GerarViagens(BaseModel):
    data: date | None = None
    rota_id: IdBanco | None = None


class Escala(BaseModel):
    """Só os campos enviados mudam; null limpa."""

    veiculo_id: IdBanco | None = None
    motorista_id: IdBanco | None = None
    monitor_id: IdBanco | None = None

    @model_validator(mode="after")
    def algum_campo(self) -> "Escala":
        if not self.model_fields_set:
            raise ValueError("Informe veiculo_id, motorista_id ou monitor_id")
        return self


class Totais(BaseModel):
    aguardando: int = 0
    embarcou: int = 0
    desembarcou: int = 0
    nao_embarcou: int = 0
    ausencia_avisada: int = 0


class ViagemLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rota_id: int
    data: date
    turno: Turno
    sentido: Sentido
    escola_id: int
    veiculo_id: int | None
    motorista_id: int | None
    monitor_id: int | None
    status: StatusViagem
    iniciada_em: datetime | None
    concluida_em: datetime | None
    cancelada_em: datetime | None
    motivo_cancelamento: str | None
    totais: Totais | None = None


class Cancelamento(BaseModel):
    motivo: Motivo


class CancelamentoResultado(BaseModel):
    viagem: ViagemLer
    responsaveis_avisados: int


class ItemDaLista(BaseModel):
    """O que o motorista vê. Sem data de nascimento nem endereço."""

    estudante_id: int
    nome: str
    foto_url: str | None
    parada_id: int | None
    parada_nome: str | None
    ordem: int | None
    status: StatusAluno
    fora_da_lista: bool
    ausencia_avisada_depois: bool
    observacoes_cuidado: str | None


class ParadaDaViagem(BaseModel):
    parada_id: int
    ordem: int
    nome: str
    horario_previsto: time | None
    raio_cerca_m: int


class ListaDaViagem(BaseModel):
    viagem: ViagemLer
    # "desembarque" quando o ônibus chegou à escola (ida) ou saiu dela (volta).
    modo: Literal["embarque", "desembarque"]
    paradas: list[ParadaDaViagem]
    alunos: list[ItemDaLista]


class EventoEntrada(BaseModel):
    id: uuid.UUID
    tipo: TipoEvento
    hora_aparelho: datetime
    estudante_id: IdBanco | None = None
    parada_id: IdBanco | None = None
    localizacao: Coordenadas | None = None
    justificativa: (
        Annotated[str, StringConstraints(max_length=500, pattern=r"^[^\x00]*$")] | None
    ) = None

    @model_validator(mode="after")
    def fuso_e_forma(self) -> "EventoEntrada":
        if self.hora_aparelho.tzinfo is None:
            raise ValueError(
                "hora_aparelho precisa informar o fuso (ex.: 2026-11-23T07:05:00-03:00)"
            )
        return self


class LoteDeEventos(BaseModel):
    eventos: Annotated[list[EventoEntrada], Field(min_length=1, max_length=200)]


class ResultadoDoEvento(BaseModel):
    id: uuid.UUID
    resultado: str
    motivo: str | None = None
    anomalia: str | None = None


class EventoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoEvento
    estudante_id: int | None
    parada_id: int | None
    hora_aparelho: datetime
    recebido_em: datetime
    autor_id: int | None
    justificativa: str | None
    status_corrigido: StatusAluno | None
    anomalia: str | None


class Correcao(BaseModel):
    estudante_id: IdBanco
    status: StatusAluno
    motivo: Motivo


class ConclusaoResultado(BaseModel):
    viagem: ViagemLer


class AlertaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    viagem_id: int | None
    tipo: str
    severidade: str
    mensagem: str
    criado_em: datetime
    resolvido_em: datetime | None


class AvisoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    viagem_id: int | None
    estudante_id: int | None
    tipo: str
    mensagem: str
    criado_em: datetime
    lido_em: datetime | None
