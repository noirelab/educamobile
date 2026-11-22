"""Limite de tentativas por chave (por exemplo, IP e e-mail no login).

A implementação em memória vale por processo. Com mais de um worker da API, troque por uma
implementação em Redis com a mesma interface; as rotas não mudam.
"""

import time
from typing import Protocol


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

    def _recentes(self, chave: str) -> list[float]:
        limite = time.monotonic() - self.janela_s
        if len(self._falhas) > self.max_chaves:
            # Evita que chaves inventadas esgotem a memória.
            self._falhas.clear()
        recentes = [t for t in self._falhas.get(chave, []) if t > limite]
        if recentes:
            self._falhas[chave] = recentes
        else:
            self._falhas.pop(chave, None)
        return recentes

    def bloqueado(self, chave: str) -> bool:
        return len(self._recentes(chave)) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        self._falhas.setdefault(chave, []).append(time.monotonic())

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)
