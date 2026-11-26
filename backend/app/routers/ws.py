"""Tempo real por WebSocket.

O token de acesso vai na primeira mensagem, nunca na URL (a URL vai para log de proxy e de
servidor). Cada inscrição em canal confere o escopo; cada mensagem entregue a um responsável
confere de novo, então ele perde o canal assim que o filho deixa a viagem. Token vencido fecha a
conexão. Entre processos da API, o repasse é o pub/sub do Redis.
"""

import asyncio
import contextlib
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import consentimento, tempo_real
from app.db import get_db
from app.models import (
    Perfil,
    ResponsavelEstudante,
    StatusAluno,
    StatusViagem,
    Usuario,
    Viagem,
    ViagemAluno,
)
from app.security import autenticar_token
from app.tempo import hoje

router = APIRouter(tags=["tempo real"])

CODIGO_NAO_AUTENTICADO = 4401
CODIGO_SEM_PERMISSAO = 4403
CODIGO_MUITAS_CONEXOES = 4429
TEMPO_PARA_AUTENTICAR_S = 10
# Conexões abertas ao mesmo tempo por usuário, em cada processo da API. Painel e app abertos em
# alguns aparelhos cabem; um script abrindo centenas, não.
MAX_CONEXOES_POR_USUARIO = 5
_conexoes: dict[int, int] = {}
CANAL_FROTA = "frota"
# O que o responsável pode receber de uma viagem: a posição, a situação da viagem e o próprio filho.
TIPOS_DO_RESPONSAVEL = frozenset({"posicao", "viagem_status", "aluno"})
GESTAO = (Perfil.ADMIN, Perfil.GESTOR)


def _viagem_do_canal(canal: str) -> int | None:
    prefixo, _, resto = canal.partition(":")
    if prefixo != "viagem" or not resto.isdigit() or len(resto) > 9:
        return None
    return int(resto)


def _filhos_na_viagem(db: Session, usuario: Usuario, viagem_id: int) -> set[int]:
    """Filhos do responsável que ainda estão na viagem (esperados ou a bordo), com consentimento."""
    return set(
        db.scalars(
            select(ViagemAluno.estudante_id)
            .join(
                ResponsavelEstudante,
                ResponsavelEstudante.estudante_id == ViagemAluno.estudante_id,
            )
            .where(
                ViagemAluno.viagem_id == viagem_id,
                ViagemAluno.status.in_([StatusAluno.AGUARDANDO, StatusAluno.EMBARCOU]),
                ResponsavelEstudante.responsavel_id == usuario.id,
                consentimento.vigente(),
            )
        )
    )


def pode_assinar(db: Session, usuario: Usuario, canal: str) -> bool:
    """Escopo do canal para este usuário, conferido na inscrição e a cada mensagem."""
    try:
        if canal == CANAL_FROTA:
            return usuario.perfil in GESTAO
        viagem_id = _viagem_do_canal(canal)
        if viagem_id is None:
            return False
        viagem = db.get(Viagem, viagem_id)
        if viagem is None:
            return False
        if usuario.perfil in GESTAO:
            return True
        if usuario.perfil in (Perfil.MOTORISTA, Perfil.MONITOR):
            escalado = (
                viagem.motorista_id if usuario.perfil == Perfil.MOTORISTA else viagem.monitor_id
            ) == usuario.id
            return escalado and viagem.data == hoje()
        if usuario.perfil == Perfil.RESPONSAVEL:
            return viagem.status == StatusViagem.EM_ANDAMENTO and bool(
                _filhos_na_viagem(db, usuario, viagem_id)
            )
        return False
    finally:
        # Não deixa a sessão do WebSocket presa numa transação enquanto espera a próxima mensagem.
        db.commit()


def filtrar(
    db: Session, usuario: Usuario, canal: str, mensagem: dict, conectado_em: float = 0.0
) -> dict | str | None:
    """A mensagem como este usuário a vê; None se não é dele; "encerrar" se perdeu o canal;
    "fechar" se a conta deixou de valer (desativada, logout geral, troca de senha)."""
    db.refresh(usuario)
    db.commit()
    if not usuario.ativo or usuario.sessoes_validas_desde.timestamp() > conectado_em:
        return "fechar"
    if usuario.perfil in (Perfil.MOTORISTA, Perfil.MONITOR):
        # A escala pode mudar no meio da viagem: o motorista antigo deixa de receber.
        return mensagem if pode_assinar(db, usuario, canal) else "encerrar"
    if usuario.perfil in GESTAO:
        return mensagem
    # Responsável: reavalia o escopo a cada entrega.
    viagem_id = _viagem_do_canal(canal)
    if viagem_id is None:
        return "encerrar"
    filhos = _filhos_na_viagem(db, usuario, viagem_id)
    viagem = db.get(Viagem, viagem_id)
    db.commit()
    if viagem is None or viagem.status != StatusViagem.EM_ANDAMENTO:
        # A viagem acabou: quem estava inscrito recebe o aviso final e sai do canal.
        return (
            {"tipo": "viagem_status", "viagem_id": viagem_id, "status": mensagem.get("status")}
            if mensagem.get("tipo") == "viagem_status"
            else "encerrar"
        )
    if mensagem.get("tipo") == "aluno":
        # O desembarque do próprio filho chega a ele, e logo depois o canal se fecha.
        if mensagem["estudante_id"] in filhos:
            return mensagem
        meus = set(
            db.scalars(
                select(ResponsavelEstudante.estudante_id).where(
                    ResponsavelEstudante.responsavel_id == usuario.id, consentimento.vigente()
                )
            )
        )
        db.commit()
        return mensagem if mensagem["estudante_id"] in meus else None
    if mensagem.get("tipo") not in TIPOS_DO_RESPONSAVEL:
        return None
    if not filhos:
        return "encerrar"
    return mensagem


async def _enviar(ws: WebSocket, dados: dict) -> None:
    await ws.send_text(json.dumps(dados))


@router.websocket("/ws")
async def tempo_real_ws(websocket: WebSocket, db: Annotated[Session, Depends(get_db)]) -> None:
    await websocket.accept()
    try:
        primeira = await asyncio.wait_for(websocket.receive_json(), TEMPO_PARA_AUTENTICAR_S)
        if not isinstance(primeira, dict) or primeira.get("tipo") != "auth":
            raise ValueError
        usuario, vence_em = await run_in_threadpool(
            autenticar_token, str(primeira.get("token", "")), db
        )
        await run_in_threadpool(db.commit)
    except (TimeoutError, ValueError, WebSocketDisconnect, HTTPException, json.JSONDecodeError):
        with contextlib.suppress(RuntimeError):
            await websocket.close(CODIGO_NAO_AUTENTICADO)
        return

    if _conexoes.get(usuario.id, 0) >= MAX_CONEXOES_POR_USUARIO:
        with contextlib.suppress(RuntimeError):
            await websocket.close(CODIGO_MUITAS_CONEXOES)
        return
    _conexoes[usuario.id] = _conexoes.get(usuario.id, 0) + 1
    try:
        await _sessao(websocket, db, usuario, vence_em)
    finally:
        _conexoes[usuario.id] -= 1
        if not _conexoes[usuario.id]:
            del _conexoes[usuario.id]


async def _sessao(websocket: WebSocket, db: Session, usuario: Usuario, vence_em: float) -> None:
    redis = tempo_real.cliente_async()
    pubsub = redis.pubsub()
    await _enviar(websocket, {"tipo": "autenticado", "expira_em": vence_em})

    def canal_redis(canal: str) -> str:
        return (
            tempo_real.CANAL_FROTA
            if canal == CANAL_FROTA
            else tempo_real.canal_da_viagem(_viagem_do_canal(canal) or 0)
        )

    inscritos: set[str] = set()
    # A sessão do SQLAlchemy não é thread-safe: uma consulta por vez.
    trava = asyncio.Lock()
    conectado_em = time.time()

    async def ler_cliente() -> None:
        while True:
            pedido = await websocket.receive_json()
            tipo = pedido.get("tipo") if isinstance(pedido, dict) else None
            canal = str(pedido.get("canal", "")) if isinstance(pedido, dict) else ""
            if tipo == "inscrever":
                async with trava:
                    permitido = await run_in_threadpool(pode_assinar, db, usuario, canal)
                if not permitido:
                    await _enviar(websocket, {"tipo": "recusado", "canal": canal})
                    continue
                if canal not in inscritos:
                    await pubsub.subscribe(canal_redis(canal))
                    inscritos.add(canal)
                await _enviar(websocket, {"tipo": "inscrito", "canal": canal})
            elif tipo == "cancelar" and canal in inscritos:
                await pubsub.unsubscribe(canal_redis(canal))
                inscritos.discard(canal)
                await _enviar(websocket, {"tipo": "cancelado", "canal": canal})
            else:
                await _enviar(websocket, {"tipo": "erro", "mensagem": "Mensagem desconhecida"})

    async def repassar() -> None:
        # Sem inscrição o pubsub ainda não tem conexão; espera a primeira.
        while True:
            if not inscritos:
                await asyncio.sleep(0.05)
                continue
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg is None:
                continue
            dados = json.loads(msg["data"])
            alvos = [c for c in inscritos if canal_redis(c) == msg["channel"]]
            for canal in alvos:
                async with trava:
                    resultado = await run_in_threadpool(
                        filtrar, db, usuario, canal, dados, conectado_em
                    )
                if resultado == "fechar":
                    await websocket.close(CODIGO_NAO_AUTENTICADO)
                    return
                if resultado == "encerrar":
                    await pubsub.unsubscribe(canal_redis(canal))
                    inscritos.discard(canal)
                    await _enviar(websocket, {"tipo": "canal_encerrado", "canal": canal})
                elif isinstance(resultado, dict):
                    await _enviar(websocket, {"canal": canal, **resultado})

    async def vigiar_expiracao() -> None:
        await asyncio.sleep(max(0.0, vence_em - time.time()))
        await websocket.close(CODIGO_NAO_AUTENTICADO)

    tarefas = [
        asyncio.create_task(ler_cliente()),
        asyncio.create_task(repassar()),
        asyncio.create_task(vigiar_expiracao()),
    ]
    try:
        await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tarefas:
            t.cancel()
        for t in tarefas:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await t
        with contextlib.suppress(Exception):
            await pubsub.aclose()
            await redis.aclose()
