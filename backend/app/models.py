import enum
from datetime import UTC, date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
    # Perfis do escopo antigo, removidos na etapa A da reformulação.
    DIRETOR = "diretor"
    COORDENADOR = "coordenador"


# Perfis da equipe da secretaria. Os demais só acessam o que for liberado por vínculo.
PERFIS_INTERNOS = frozenset({Perfil.ADMIN, Perfil.GESTOR, Perfil.DIRETOR, Perfil.COORDENADOR})


class Turno(enum.StrEnum):
    MANHA = "manha"
    TARDE = "tarde"
    NOITE = "noite"
    INTEGRAL = "integral"


class StatusMatricula(enum.StrEnum):
    ATIVA = "ativa"
    TRANSFERIDA = "transferida"
    ENCERRADA = "encerrada"


def _enum(tipo: type[enum.Enum], nome: str) -> Enum:
    return Enum(tipo, name=nome, values_callable=lambda e: [m.value for m in e])


class Polo(Base):
    __tablename__ = "polo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True)
    area = mapped_column(Geometry("MULTIPOLYGON", srid=SRID), nullable=True)


class Escola(Base):
    __tablename__ = "escola"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    codigo_inep: Mapped[str | None] = mapped_column(unique=True)
    endereco: Mapped[str | None]
    polo_id: Mapped[int | None] = mapped_column(ForeignKey("polo.id", ondelete="SET NULL"))
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=False)


class Turma(Base):
    __tablename__ = "turma"
    __table_args__ = (UniqueConstraint("escola_id", "nome", "ano_letivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escola_id: Mapped[int] = mapped_column(ForeignKey("escola.id", ondelete="RESTRICT"), index=True)
    nome: Mapped[str]
    serie: Mapped[str]
    turno: Mapped[Turno] = mapped_column(_enum(Turno, "turno"))
    ano_letivo: Mapped[int]


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


class Professor(Base):
    __tablename__ = "professor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    escola_id: Mapped[int | None] = mapped_column(
        ForeignKey("escola.id", ondelete="SET NULL"), index=True
    )


class Matricula(Base):
    __tablename__ = "matricula"
    __table_args__ = (
        CheckConstraint("data_fim IS NULL OR data_fim >= data_inicio", name="ck_matricula_periodo"),
        # O histórico fica na tabela; só pode haver um vínculo ativo por estudante.
        Index(
            "uq_matricula_ativa_por_estudante",
            "estudante_id",
            unique=True,
            postgresql_where=text("status = 'ativa'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudante.id", ondelete="RESTRICT"), index=True
    )
    turma_id: Mapped[int] = mapped_column(ForeignKey("turma.id", ondelete="RESTRICT"), index=True)
    data_inicio: Mapped[date]
    data_fim: Mapped[date | None]
    status: Mapped[StatusMatricula] = mapped_column(
        _enum(StatusMatricula, "status_matricula"), default=StatusMatricula.ATIVA
    )


class Frequencia(Base):
    __tablename__ = "frequencia"
    __table_args__ = (UniqueConstraint("matricula_id", "data"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(
        ForeignKey("matricula.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[date] = mapped_column(index=True)
    presente: Mapped[bool]


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
    __table_args__ = (
        CheckConstraint(
            "perfil <> 'diretor' OR escola_id IS NOT NULL", name="ck_usuario_diretor_tem_escola"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    senha_hash: Mapped[str]
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil, "perfil"))
    escola_id: Mapped[int | None] = mapped_column(ForeignKey("escola.id", ondelete="RESTRICT"))
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
