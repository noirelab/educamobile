"""Limites por chave: tentativas de login, aceite de convite e uso geral da API.

Duas implementações com a mesma interface. A em memória vale por processo e serve para
desenvolvimento e testes. A de Redis vale para todos os processos da API e é a que produção usa
(`LIMITE_BACKEND=redis`); sem ela, subir mais um worker da API multiplicaria o limite.
"""

import hashlib
import time
import uuid
from typing import Protocol

import redis
from fastapi import HTTPException, Request, status

from app import auditoria, tempo_real
from app.config import settings


class LimiteTentativas(Protocol):
    def bloqueado(self, chave: str) -> bool: ...
    def registrar_falha(self, chave: str) -> None: ...
    def limpar(self, chave: str) -> None: ...


class LimiteEmMemoria:
    def __init__(self, maximo: int, janela_s: int, max_chaves: int = 10_000) -> None:
        self.maximo = maximo
        self.janela_s = janela_s
        self.max_chaves = max_chaves
        self._falhas: dict[str, list[float]] = {}

    def _podar(self) -> None:
        """Mantém a memória limitada sem soltar quem está bloqueado.

        Apagar tudo de uma vez, ou só as chaves mais antigas, permitiria zerar o bloqueio de uma
        conta inundando o login com e-mails inventados. Por isso saem primeiro as expiradas,
        depois as que ainda não chegaram ao limite (cada e-mail inventado tem uma falha só) e,
        em último caso, as bloqueadas mais antigas.
        """
        limite = time.monotonic() - self.janela_s
        for chave in [c for c, ts in self._falhas.items() if ts[-1] <= limite]:
            del self._falhas[chave]
        excesso = len(self._falhas) - self.max_chaves
        if excesso > 0:
            ordem = sorted(
                self._falhas,
                key=lambda c: (len(self._falhas[c]) >= self.maximo, self._falhas[c][-1]),
            )
            for chave in ordem[:excesso]:
                del self._falhas[chave]

    def _recentes(self, chave: str) -> list[float]:
        limite = time.monotonic() - self.janela_s
        recentes = [t for t in self._falhas.get(chave, []) if t > limite]
        if recentes:
            self._falhas[chave] = recentes
        else:
            self._falhas.pop(chave, None)
        return recentes

    def bloqueado(self, chave: str) -> bool:
        return len(self._recentes(chave)) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        falhas = self._falhas.setdefault(chave, [])
        falhas.append(time.monotonic())
        # Só as últimas `maximo` importam para decidir o bloqueio.
        del falhas[: -self.maximo]
        if len(self._falhas) > self.max_chaves:
            self._podar()

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)


class LimiteRedis:
    """Janela deslizante num conjunto ordenado do Redis, compartilhada entre processos."""

    def __init__(self, maximo: int, janela_s: int, prefixo: str = "geral") -> None:
        self.maximo = maximo
        self.janela_s = janela_s
        self.prefixo = prefixo

    def _k(self, chave: str) -> str:
        return f"limite:{self.prefixo}:{chave}"

    # Com o Redis fora do ar o limite deixa de valer em vez de derrubar o login e o resto da API.
    # É uma escolha de disponibilidade: o alerta de Redis indisponível precisa chegar a alguém.

    def bloqueado(self, chave: str) -> bool:
        k = self._k(chave)
        agora = time.time()
        try:
            pipe = tempo_real.cliente().pipeline()
            pipe.zremrangebyscore(k, 0, agora - self.janela_s)
            pipe.zcard(k)
            return pipe.execute()[1] >= self.maximo
        except redis.RedisError:
            return False

    def registrar_falha(self, chave: str) -> None:
        k = self._k(chave)
        agora = time.time()
        try:
            pipe = tempo_real.cliente().pipeline()
            pipe.zadd(k, {uuid.uuid4().hex: agora})
            # Só as últimas `maximo` importam, e a chave some sozinha quando a janela passa.
            pipe.zremrangebyrank(k, 0, -(self.maximo + 1))
            pipe.expire(k, self.janela_s + 1)
            pipe.execute()
        except redis.RedisError:
            pass

    def limpar(self, chave: str) -> None:
        try:
            tempo_real.cliente().delete(self._k(chave))
        except redis.RedisError:
            pass


def criar_limite(prefixo: str, maximo: int, janela_s: int) -> LimiteTentativas:
    """A implementação escolhida pela configuração `limite_backend`."""
    if settings.limite_backend == "redis":
        return LimiteRedis(maximo, janela_s, prefixo)
    return LimiteEmMemoria(maximo, janela_s)


# Uso geral da API: por token de acesso (ou IP, sem token), contando cada requisição.
MAX_ESCRITAS_POR_MINUTO = 300
MAX_POSICOES_POR_MINUTO = 120
limite_escrita = criar_limite("escrita", MAX_ESCRITAS_POR_MINUTO, 60)
limite_posicoes = criar_limite("posicoes", MAX_POSICOES_POR_MINUTO, 60)
# Teto por IP, que o cliente não consegue trocar: sem ele, variar o cabeçalho Authorization a
# cada requisição abriria sempre um contador novo.
MAX_REQUISICOES_POR_IP_POR_MINUTO = 1200
limite_ip = criar_limite("ip", MAX_REQUISICOES_POR_IP_POR_MINUTO, 60)


def _quem(request: Request) -> str:
    credencial = request.headers.get("authorization") or request.headers.get("x-token-rastreador")
    if credencial:
        return "t:" + hashlib.sha256(credencial.encode()).hexdigest()[:32]
    return "ip:" + (auditoria.ip_do_cliente(request) or "?")


def _consumir(limite: LimiteTentativas, quem: str) -> None:
    try:
        if limite.bloqueado(quem):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Muitas requisições. Aguarde um instante",
                headers={"Retry-After": "60"},
            )
        limite.registrar_falha(quem)
    except redis.RedisError:
        # Redis fora do ar não pode derrubar a API: sem limite por alguns instantes.
        pass


def limitar_escrita(request: Request) -> None:
    """Dependência global: só as rotas que escrevem entram na conta."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    _consumir(limite_ip, "ip:" + (auditoria.ip_do_cliente(request) or "?"))
    _consumir(limite_escrita, _quem(request))


def limitar_posicoes(request: Request) -> None:
    _consumir(limite_ip, "ip:" + (auditoria.ip_do_cliente(request) or "?"))
    _consumir(limite_posicoes, _quem(request))
