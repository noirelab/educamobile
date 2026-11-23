import enum
from datetime import UTC, date, datetime, time

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
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


class Turno(enum.StrEnum):
    MANHA = "manha"
    TARDE = "tarde"
    INTEGRAL = "integral"


class Sentido(enum.StrEnum):
    IDA = "ida"
    VOLTA = "volta"


def _enum(tipo: type[enum.Enum], nome: str) -> Enum:
    return Enum(tipo, name=nome, values_callable=lambda e: [m.value for m in e])


class Escola(Base):
    __tablename__ = "escola"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    codigo_inep: Mapped[str | None] = mapped_column(unique=True)
    endereco: Mapped[str | None]
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=False)
    # Raio da cerca virtual da escola: chegar dentro dele conta como chegada.
    raio_cerca_m: Mapped[int] = mapped_column(default=150, server_default=text("150"))


class Parada(Base):
    __tablename__ = "parada"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    localizacao = mapped_column(Geometry("POINT", srid=SRID), nullable=False)


class Estudante(Base):
    """Só o necessário para o transporte. Sem endereço nem localização da casa: a parada basta."""

    __tablename__ = "estudante"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    data_nascimento: Mapped[date]
    escola_id: Mapped[int] = mapped_column(ForeignKey("escola.id", ondelete="RESTRICT"), index=True)
    turno: Mapped[Turno] = mapped_column(_enum(Turno, "turno"))
    parada_id: Mapped[int | None] = mapped_column(
        ForeignKey("parada.id", ondelete="SET NULL"), index=True
    )
    # Alergia, necessidade especial. Só gestor e a equipe da viagem leem.
    observacoes_cuidado: Mapped[str | None]
    # Nome do arquivo no disco, nunca devolvido pela API.
    foto_arquivo: Mapped[str | None]


class Veiculo(Base):
    __tablename__ = "veiculo"
    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_veiculo_capacidade"),
        CheckConstraint("ano BETWEEN 1980 AND 2100", name="ck_veiculo_ano"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    placa: Mapped[str] = mapped_column(unique=True)
    capacidade: Mapped[int]
    modelo: Mapped[str]
    ano: Mapped[int]
    vistoria_valida_ate: Mapped[date]
    ativo: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Motorista(Base):
    """Cadastro do motorista, ligado à conta de usuário com perfil motorista."""

    __tablename__ = "motorista"

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True
    )
    cnh: Mapped[str] = mapped_column(unique=True)
    categoria_cnh: Mapped[str]
    cnh_valida_ate: Mapped[date]
    curso_transporte_escolar_ate: Mapped[date]


class Rota(Base):
    __tablename__ = "rota"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True)
    escola_id: Mapped[int] = mapped_column(ForeignKey("escola.id", ondelete="RESTRICT"), index=True)
    turno: Mapped[Turno] = mapped_column(_enum(Turno, "turno"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido, "sentido"))
    # Veículo e motorista padrão; a viagem do dia pode trocá-los.
    veiculo_id: Mapped[int | None] = mapped_column(ForeignKey("veiculo.id", ondelete="SET NULL"))
    motorista_id: Mapped[int | None] = mapped_column(
        ForeignKey("motorista.usuario_id", ondelete="SET NULL")
    )
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
    horario_previsto: Mapped[time | None]
    # Raio da cerca virtual da parada, em metros.
    raio_cerca_m: Mapped[int] = mapped_column(default=50, server_default=text("50"))

    rota: Mapped[Rota] = relationship(back_populates="paradas")


class Inscricao(Base):
    """Onde a criança deve embarcar: rota, parada, dias da semana e vigência."""

    __tablename__ = "inscricao"
    __table_args__ = (
        CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio", name="ck_insc_periodo"
        ),
        CheckConstraint("cardinality(dias_semana) BETWEEN 1 AND 7", name="ck_insc_dias"),
        # Turno e sentido são copiados da rota para o banco impedir duas inscrições ativas iguais.
        Index(
            "uq_inscricao_ativa_por_turno_e_sentido",
            "estudante_id",
            "turno",
            "sentido",
            unique=True,
            postgresql_where=text("ativa"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudante.id", ondelete="CASCADE"), index=True
    )
    rota_id: Mapped[int] = mapped_column(ForeignKey("rota.id", ondelete="CASCADE"), index=True)
    parada_id: Mapped[int] = mapped_column(ForeignKey("parada.id", ondelete="RESTRICT"))
    turno: Mapped[Turno] = mapped_column(_enum(Turno, "turno"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido, "sentido"))
    # 0 = segunda ... 6 = domingo (date.weekday()).
    dias_semana: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    vigencia_inicio: Mapped[date]
    vigencia_fim: Mapped[date | None]
    ativa: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Ausencia(Base):
    """Aviso do responsável de que a criança não vai embarcar naquele dia."""

    __tablename__ = "ausencia"
    __table_args__ = (UniqueConstraint("estudante_id", "data", "sentido"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    estudante_id: Mapped[int] = mapped_column(
        ForeignKey("estudante.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[date] = mapped_column(index=True)
    # Nulo vale para ida e volta.
    sentido: Mapped[Sentido | None] = mapped_column(_enum(Sentido, "sentido"))
    criada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
