"""Novo na reformulação: confirmação de recebimento das crianças pela equipe da escola."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.cadastros import IdBanco


class AlunoChegando(BaseModel):
    """Só o nome: a equipe da escola não precisa de foto, saúde nem parada para conferir."""

    estudante_id: int
    nome: str
    # a_caminho: embarcou e ainda não desceu; aguardando: desceu e falta confirmar; recebido.
    situacao: Literal["a_caminho", "aguardando", "recebido"]
    desembarcou_em: datetime | None
    recebido_em: datetime | None


class ChegadaDaViagem(BaseModel):
    viagem_id: int
    rota: str
    placa: str | None
    status: str
    alunos: list[AlunoChegando]


class Recebimento(BaseModel):
    estudante_ids: list[IdBanco] = Field(min_length=1, max_length=100)


class RecebimentoResultado(BaseModel):
    recebidos: int
    ja_recebidos: int
