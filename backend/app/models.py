import enum
from datetime import UTC, date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SRID = 4326


class Perfil(enum.StrEnum):
    ADMIN = "admin"
    GESTOR = "gestor"
    MOTORISTA = "motorista"
    MONITOR = "monitor"
    RESPONSAVEL = "responsavel"


# Perfis da equipe da secretaria. Os demais só acessam o que for liberado por vínculo.
PERFIS_INTERNOS = frozenset({Perfil.ADMIN, Perfil.GESTOR})


def _enum(tipo: type[enum.Enum], nome: str) -> Enum:
    return Enum(tipo, name=nome, values_callable=lambda e: [m.value for m in e])


class Escola(Base):
    __tablename__ = "escola"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    codigo_inep: Mapped[str | None] = mapped_column(unique=True)
    endereco: Mapped[str | None]
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=False)


class Parada(Base):
    __tablename__ = "parada"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=False)


class Estudante(Base):
    __tablename__ = "estudante"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    data_nascimento: Mapped[date]
    nome_responsavel: Mapped[str | None]
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=True)
    parada_id: Mapped[int | None] = mapped_column(
        ForeignKey("parada.id", ondelete="SET NULL"), index=True
    )


class Rota(Base):
    __tablename__ = "rota"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True)
    # Calculados a partir das paradas, em ordem. Nulos com menos de duas paradas.
    trajeto = mapped_column(Geometry("LINESTRING", srid=SRID), nullable=True)
    distancia_m: Mapped[float | None]

    paradas: Mapped[list["RotaParada"]] = relationship(
        back_populates="rota", cascade="all, delete-orphan", order_by="RotaParada.ordem"
    )


class RotaParada(Base):
    __tablename__ = "rota_parada"
    __table_args__ = (UniqueConstraint("rota_id", "ordem"),)

    rota_id: Mapped[int] = mapped_column(
        ForeignKey("rota.id", ondelete="CASCADE"), primary_key=True
    )
    parada_id: Mapped[int] = mapped_column(
        ForeignKey("parada.id", ondelete="RESTRICT"), primary_key=True
    )
    ordem: Mapped[int]

    rota: Mapped[Rota] = relationship(back_populates="paradas")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    senha_hash: Mapped[str]
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil, "perfil"))
    ativo: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Tokens de acesso emitidos antes deste instante deixam de valer (troca de senha, logout geral).
    sessoes_validas_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class Sessao(Base):
    """Refresh token de um aparelho. Só o hash do token é guardado."""

    __tablename__ = "sessao"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Preenchido na rotação; reuso de uma sessão substituída indica token roubado.
    substituida_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessao.id", ondelete="SET NULL")
    )
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None]


class ResponsavelEstudante(Base):
    """Vínculo que libera ao responsável os dados de um estudante."""

    __tablename__ = "responsavel_estudante"

    responsavel_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True
    )
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudante.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    parentesco: Mapped[str]
    principal: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    # LGPD, art. 14: o acesso aos dados só vale depois do consentimento registrado.
    consentimento_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consentimento_versao: Mapped[str | None]


class Convite(Base):
    """Convite de uso único para o responsável. Só o hash do código é guardado."""

    __tablename__ = "convite"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_hash: Mapped[str] = mapped_column(unique=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(index=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudante.id", ondelete="CASCADE"), index=True
    )
    parentesco: Mapped[str]
    principal: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Auditoria(Base):
    """Registro só de inclusão. Nunca guarda senha nem token."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    acao: Mapped[str] = mapped_column(index=True)
    recurso: Mapped[str | None]
    recurso_id: Mapped[str | None]
    ip: Mapped[str | None] = mapped_column(INET)
    detalhes: Mapped[dict | None] = mapped_column(JSONB)
