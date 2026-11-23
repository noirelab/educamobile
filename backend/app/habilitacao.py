"""Se o motorista pode dirigir numa data, e por quê (regra R1: habilitado e com o curso em dia)."""

from dataclasses import dataclass, field
from datetime import date

from app.models import Motorista, Usuario

# Categorias da CNH que permitem conduzir transporte escolar (ônibus e micro-ônibus).
CATEGORIAS_DE_TRANSPORTE = frozenset({"D", "E", "AD", "AE"})


@dataclass
class Situacao:
    pode_dirigir: bool
    motivos: list[str] = field(default_factory=list)


def situacao(usuario: Usuario, motorista: Motorista | None, hoje: date) -> Situacao:
    motivos: list[str] = []
    if not usuario.ativo:
        motivos.append("Conta desativada")
    if motorista is None:
        motivos.append("Motorista sem cadastro de documentos")
    else:
        if motorista.cnh_valida_ate < hoje:
            motivos.append("CNH vencida")
        if motorista.categoria_cnh not in CATEGORIAS_DE_TRANSPORTE:
            motivos.append("Categoria da CNH não permite transporte escolar")
        if motorista.curso_transporte_escolar_ate < hoje:
            motivos.append("Curso de transporte escolar vencido")
    return Situacao(pode_dirigir=not motivos, motivos=motivos)
