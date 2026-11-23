"""Redis: última posição de cada ônibus e pub/sub entre os processos da API.

As posições são gravadas no banco e a mais recente também aqui, para o painel e o app do
responsável lerem sem pesar no PostgreSQL. A mensagem vai pelo pub/sub; cada processo repassa aos
WebSockets que estão nele.
"""

import json
from functools import lru_cache

import redis
import redis.asyncio as redis_async
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import settings

# A posição some sozinha se o ônibus parar de enviar: dado velho não pode parecer atual.
TTL_POSICAO_S = 6 * 3600
CANAL_FROTA = "canal:frota"


def canal_da_viagem(viagem_id: int) -> str:
    return f"canal:viagem:{viagem_id}"


@lru_cache(maxsize=1)
def cliente() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def cliente_async() -> redis_async.Redis:
    # Um por conexão de WebSocket: o pub/sub assíncrono não é compartilhável entre laços de evento.
    return redis_async.Redis.from_url(settings.redis_url, decode_responses=True)


def _chave(viagem_id: int) -> str:
    return f"posicao:{viagem_id}"


def guardar_posicao(viagem_id: int, dados: dict) -> bool:
    """Grava só se for mais recente que a guardada (lote offline chega fora de ordem)."""
    atual = ler_posicao(viagem_id)
    if atual is not None and atual["registrada_em"] >= dados["registrada_em"]:
        return False
    cliente().set(_chave(viagem_id), json.dumps(dados), ex=TTL_POSICAO_S)
    return True


def ler_posicao(viagem_id: int) -> dict | None:
    bruto = cliente().get(_chave(viagem_id))
    return json.loads(bruto) if bruto else None


def ler_posicoes(viagem_ids: list[int]) -> dict[int, dict]:
    if not viagem_ids:
        return {}
    valores = cliente().mget([_chave(i) for i in viagem_ids])
    return {i: json.loads(v) for i, v in zip(viagem_ids, valores, strict=True) if v}


def apagar_posicao(viagem_id: int) -> None:
    cliente().delete(_chave(viagem_id))


def publicar(canal: str, mensagem: dict) -> None:
    cliente().publish(canal, json.dumps(mensagem))


def _publicar_na_viagem_e_na_frota(viagem_id: int, mensagem: dict) -> None:
    """Falha do Redis não pode derrubar quem registrou o evento."""
    try:
        publicar(canal_da_viagem(viagem_id), mensagem)
        publicar(CANAL_FROTA, mensagem)
    except redis.RedisError:
        pass


def enfileirar(db: Session, viagem_id: int, mensagem: dict) -> None:
    """Guarda a mensagem na sessão; ela só sai depois do commit (e some se houver rollback).

    Publicar antes do commit deixaria o WebSocket decidir com um estado que o banco ainda não tem.
    """
    db.info.setdefault("mensagens", []).append((viagem_id, mensagem))


@event.listens_for(Session, "after_commit")
def _descarregar(session: Session) -> None:
    for viagem_id, mensagem in session.info.pop("mensagens", []):
        _publicar_na_viagem_e_na_frota(viagem_id, mensagem)


@event.listens_for(Session, "after_rollback")
def _descartar(session: Session) -> None:
    session.info.pop("mensagens", None)
