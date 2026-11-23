"""Notificações: criação (nas regras de negócio) e envio por push (no worker).

Toda notificação nasce numa linha de `notificacao`, que a pessoa também lê pela API. O worker
envia as pendentes ao Firebase, tenta de novo com espera crescente se falhar e apaga o token
que o Firebase recusa. O texto só fala do próprio filho: nunca de outras crianças da viagem.
"""

import enum
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import consentimento
from app.models import Dispositivo, Estudante, Notificacao, Perfil, ResponsavelEstudante, Usuario

log = logging.getLogger(__name__)

MAX_TENTATIVAS = 5
ESPERA_BASE_S = 30
ESPERA_MAXIMA_S = 3600
LOTE = 100
FCM_ESCOPO = "https://www.googleapis.com/auth/firebase.messaging"


def nome_curto(estudante: Estudante) -> str:
    """Só o primeiro nome vai no texto da notificação."""
    return estudante.nome.split()[0] if estudante.nome.strip() else "A criança"


# Criação


def criar(
    db: Session,
    usuario_id: int,
    tipo: str,
    titulo: str,
    mensagem: str,
    *,
    viagem_id: int | None = None,
    estudante_id: int | None = None,
) -> Notificacao:
    n = Notificacao(
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        viagem_id=viagem_id,
        estudante_id=estudante_id,
    )
    db.add(n)
    # Acorda o worker depois do commit, para o push sair na hora e não no próximo ciclo.
    db.info["acordar_worker"] = True
    return n


def para_responsaveis(
    db: Session,
    estudante_id: int,
    tipo: str,
    titulo: str,
    mensagem: str,
    *,
    viagem_id: int | None = None,
) -> int:
    """Avisa quem tem vínculo e consentimento com a criança. Devolve quantos."""
    ids = db.scalars(
        select(ResponsavelEstudante.responsavel_id).where(
            ResponsavelEstudante.estudante_id == estudante_id,
            consentimento.vigente(),
        )
    ).all()
    for usuario_id in ids:
        criar(
            db, usuario_id, tipo, titulo, mensagem, viagem_id=viagem_id, estudante_id=estudante_id
        )
    return len(ids)


def para_gestores(
    db: Session, tipo: str, titulo: str, mensagem: str, *, viagem_id: int | None = None
) -> int:
    ids = db.scalars(
        select(Usuario.id).where(
            Usuario.perfil.in_([Perfil.ADMIN, Perfil.GESTOR]), Usuario.ativo.is_(True)
        )
    ).all()
    for usuario_id in ids:
        criar(db, usuario_id, tipo, titulo, mensagem, viagem_id=viagem_id)
    return len(ids)


# Envio


class Resultado(enum.Enum):
    ENVIADO = "enviado"
    TOKEN_INVALIDO = "token_invalido"
    ERRO_TEMPORARIO = "erro_temporario"


class Enviador(Protocol):
    def enviar(self, token: str, titulo: str, corpo: str, dados: dict[str, str]) -> Resultado: ...


class EnviadorDeRegistro:
    """Sem credenciais do Firebase (desenvolvimento): só registra no log."""

    def enviar(self, token: str, titulo: str, corpo: str, dados: dict[str, str]) -> Resultado:
        log.info("push (sem FCM configurado): %s | %s", titulo, corpo)
        return Resultado.ENVIADO


class EnviadorFcm:
    """Firebase Cloud Messaging pela API HTTP v1.

    `obter_token_de_acesso` e `cliente` são injetáveis para teste; em produção o token OAuth sai
    da conta de serviço (`google-auth`).
    """

    def __init__(
        self,
        projeto_id: str,
        obter_token_de_acesso: Callable[[], str],
        cliente: httpx.Client | None = None,
    ) -> None:
        self.url = f"https://fcm.googleapis.com/v1/projects/{projeto_id}/messages:send"
        self.obter_token = obter_token_de_acesso
        self.cliente = cliente or httpx.Client(timeout=10)

    @classmethod
    def da_conta_de_servico(cls, caminho_json: str, projeto_id: str) -> "EnviadorFcm":
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        credenciais = service_account.Credentials.from_service_account_file(
            caminho_json, scopes=[FCM_ESCOPO]
        )

        def token() -> str:
            if not credenciais.valid:
                credenciais.refresh(Request())
            return credenciais.token

        return cls(projeto_id, token)

    def enviar(self, token: str, titulo: str, corpo: str, dados: dict[str, str]) -> Resultado:
        mensagem = {
            "message": {
                "token": token,
                "notification": {"title": titulo, "body": corpo},
                "data": dados,
                "android": {"priority": "HIGH"},
            }
        }
        try:
            r = self.cliente.post(
                self.url, json=mensagem, headers={"Authorization": f"Bearer {self.obter_token()}"}
            )
        except Exception:  # noqa: BLE001  (rede, credencial recusada, token OAuth indisponível)
            return Resultado.ERRO_TEMPORARIO
        if r.is_success:
            return Resultado.ENVIADO
        if r.status_code in (400, 404):
            try:
                erro = r.json().get("error", {})
            except ValueError:
                return Resultado.ERRO_TEMPORARIO
            codigos = {d.get("errorCode") for d in erro.get("details", []) if isinstance(d, dict)}
            texto = str(erro.get("message", "")).lower()
            if (
                "UNREGISTERED" in codigos
                or erro.get("status") == "NOT_FOUND"
                or "registration token" in texto
            ):
                return Resultado.TOKEN_INVALIDO
        # 401/403 (credencial), 429 e 5xx: tenta de novo mais tarde.
        return Resultado.ERRO_TEMPORARIO


def obter_enviador() -> Enviador:
    from app.config import settings

    if settings.fcm_credenciais and settings.fcm_projeto:
        return EnviadorFcm.da_conta_de_servico(settings.fcm_credenciais, settings.fcm_projeto)
    return EnviadorDeRegistro()


def _espera(tentativas: int) -> timedelta:
    return timedelta(seconds=min(ESPERA_BASE_S * 2**tentativas, ESPERA_MAXIMA_S))


def enviar_pendentes(db: Session, enviador: Enviador, agora: datetime | None = None) -> int:
    """Envia as notificações pendentes. Devolve quantas saíram nesta rodada."""
    agora = agora or datetime.now(UTC)
    pendentes = db.scalars(
        select(Notificacao)
        .where(
            Notificacao.enviada_em.is_(None),
            Notificacao.tentativas < MAX_TENTATIVAS,
            (Notificacao.proxima_tentativa_em.is_(None))
            | (Notificacao.proxima_tentativa_em <= agora),
        )
        .order_by(Notificacao.id)
        .limit(LOTE)
        .with_for_update(skip_locked=True)
    ).all()
    enviadas = 0
    for n in pendentes:
        dispositivos = db.scalars(
            select(Dispositivo).where(Dispositivo.usuario_id == n.usuario_id)
        ).all()
        if not dispositivos:
            # Sem aparelho cadastrado: fica só na caixa de notificações da API.
            n.enviada_em = agora
            n.erro = "sem_dispositivo"
            continue
        ok = invalido = temporario = 0
        for d in dispositivos:
            dados = {"notificacao_id": str(n.id), "tipo": n.tipo}
            try:
                resultado = enviador.enviar(d.token, n.titulo, n.mensagem, dados)
            except Exception:  # noqa: BLE001
                # Um adaptador com defeito conta como falha temporária desta notificação, com
                # espera crescente, e não trava as demais nem repete o ciclo para sempre.
                log.exception("falha ao enviar a notificação %s", n.id)
                resultado = Resultado.ERRO_TEMPORARIO
            if resultado is Resultado.ENVIADO:
                ok += 1
            elif resultado is Resultado.TOKEN_INVALIDO:
                invalido += 1
                db.execute(delete(Dispositivo).where(Dispositivo.id == d.id))
            else:
                temporario += 1
        if ok:
            n.enviada_em = agora
            n.erro = None
            enviadas += 1
        elif temporario:
            n.tentativas += 1
            n.erro = "falha_temporaria"
            n.proxima_tentativa_em = agora + _espera(n.tentativas)
        else:
            n.enviada_em = agora
            n.erro = "tokens_invalidos"
    db.flush()
    return enviadas
