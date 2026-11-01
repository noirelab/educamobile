import enum
from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SRID = 4326


class Perfil(enum.StrEnum):
    ADMIN = "admin"
    DIRETOR = "diretor"
    COORDENADOR = "coordenador"


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
