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
