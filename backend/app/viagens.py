"""Regras da viagem do dia: geração, início, eventos, status da lista e conclusão.

O status de cada aluno nunca é gravado à mão: é o resultado dos eventos, ordenados pela hora do
aparelho. Assim um evento que chega atrasado (modo offline) termina no mesmo estado que teria se
tivesse chegado na hora.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import consentimento, habilitacao, notificacoes, tempo_real
from app.geo import Coordenadas, para_ponto
from app.models import (
    STATUS_FINAIS,
    Alerta,
    Ausencia,
    Estudante,
    EventoViagem,
    Inscricao,
    Motorista,
    Parada,
    ResponsavelEstudante,
    Rota,
    RotaParada,
    Severidade,
    StatusAluno,
    StatusViagem,
    TipoEvento,
    Usuario,
    Veiculo,
    Viagem,
    ViagemAluno,
    ViagemParada,
)

# Eventos que mudam o status do aluno (onibus_vazio não pertence a nenhum aluno).
TIPOS_DE_ALUNO = frozenset(
    {
        TipoEvento.EMBARQUE,
        TipoEvento.NAO_EMBARCOU,
        TipoEvento.DESEMBARQUE,
        TipoEvento.EMBARQUE_FORA_DA_LISTA,
        TipoEvento.CORRECAO,
    }
)
_STATUS_DO_TIPO = {
    TipoEvento.EMBARQUE: StatusAluno.EMBARCOU,
    TipoEvento.EMBARQUE_FORA_DA_LISTA: StatusAluno.EMBARCOU,
    TipoEvento.NAO_EMBARCOU: StatusAluno.NAO_EMBARCOU,
    TipoEvento.DESEMBARQUE: StatusAluno.DESEMBARCOU,
}
# Quanto a hora do aparelho pode estar adiantada em relação ao servidor (relógio desregulado).
TOLERANCIA_RELOGIO_S = 300


def agora() -> datetime:
    return datetime.now(UTC)


def erro(codigo: int, mensagem: str, **extra) -> HTTPException:
    detalhe = {"mensagem": mensagem, **extra} if extra else mensagem
    return HTTPException(codigo, detalhe)


# Geração


def inscricoes_do_dia(db: Session, rota_id: int, dia: date) -> list[Inscricao]:
    consulta = select(Inscricao).where(
        Inscricao.rota_id == rota_id,
        Inscricao.ativa.is_(True),
        Inscricao.vigencia_inicio <= dia,
        (Inscricao.vigencia_fim.is_(None)) | (Inscricao.vigencia_fim >= dia),
    )
    return [i for i in db.scalars(consulta) if dia.weekday() in i.dias_semana]


def gerar(db: Session, dia: date, rota_id: int | None = None) -> list[Viagem]:
    """Cria a viagem do dia das rotas que têm alguém inscrito. Repetir a chamada não duplica."""
    consulta = select(Rota).order_by(Rota.id)
    if rota_id is not None:
        consulta = consulta.where(Rota.id == rota_id)
    viagens: list[Viagem] = []
    for rota in db.scalars(consulta):
        existente = db.scalar(select(Viagem).where(Viagem.rota_id == rota.id, Viagem.data == dia))
        if existente is not None:
            viagens.append(existente)
            continue
        if not inscricoes_do_dia(db, rota.id, dia):
            continue
        viagem = Viagem(
            rota_id=rota.id,
            data=dia,
            turno=rota.turno,
            sentido=rota.sentido,
            escola_id=rota.escola_id,
            veiculo_id=rota.veiculo_id,
            motorista_id=rota.motorista_id,
        )
        db.add(viagem)
        viagens.append(viagem)
    db.flush()
    return viagens


# Início (regra R1)


def motivos_para_iniciar(db: Session, viagem: Viagem, hoje: date) -> list[str]:
    motivos: list[str] = []
    if viagem.motorista_id is None:
        motivos.append("Sem motorista escalado")
    else:
        usuario = db.get(Usuario, viagem.motorista_id)
        motorista = db.get(Motorista, viagem.motorista_id)
        if usuario is not None:
            motivos += habilitacao.situacao(usuario, motorista, hoje).motivos
    if viagem.veiculo_id is None:
        motivos.append("Sem veículo escalado")
    else:
        veiculo = db.get(Veiculo, viagem.veiculo_id)
        if veiculo is None or not veiculo.ativo:
            motivos.append("Veículo inativo")
        elif veiculo.vistoria_valida_ate < hoje:
            motivos.append("Vistoria do veículo vencida")
    return motivos


def _ausentes(db: Session, estudante_ids: list[int], viagem: Viagem) -> set[int]:
    if not estudante_ids:
        return set()
    return set(
        db.scalars(
            select(Ausencia.estudante_id).where(
                Ausencia.estudante_id.in_(estudante_ids),
                Ausencia.data == viagem.data,
                (Ausencia.sentido.is_(None)) | (Ausencia.sentido == viagem.sentido),
            )
        )
    )


def iniciar(db: Session, viagem: Viagem, hoje: date) -> None:
    if viagem.status != StatusViagem.AGENDADA:
        raise erro(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    if viagem.data != hoje:
        raise erro(status.HTTP_409_CONFLICT, "A viagem só pode ser iniciada no próprio dia")
    motivos = motivos_para_iniciar(db, viagem, hoje)
    if motivos:
        raise erro(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A viagem não pode começar",
            motivos=motivos,
        )

    # Cópia: depois daqui, editar rota ou inscrição não mexe na lista que o motorista tem.
    paradas = db.execute(
        select(RotaParada, Parada)
        .join(Parada, Parada.id == RotaParada.parada_id)
        .where(RotaParada.rota_id == viagem.rota_id)
        .order_by(RotaParada.ordem)
    ).all()
    for rp, parada in paradas:
        db.add(
            ViagemParada(
                viagem_id=viagem.id,
                parada_id=parada.id,
                ordem=rp.ordem,
                nome=parada.nome,
                localizacao=parada.localizacao,
                horario_previsto=rp.horario_previsto,
                raio_cerca_m=rp.raio_cerca_m,
            )
        )
    db.flush()
    inscricoes = inscricoes_do_dia(db, viagem.rota_id, viagem.data)
    ausentes = _ausentes(db, [i.estudante_id for i in inscricoes], viagem)
    for i in inscricoes:
        inicial = (
            StatusAluno.AUSENCIA_AVISADA if i.estudante_id in ausentes else StatusAluno.AGUARDANDO
        )
        db.add(
            ViagemAluno(
                viagem_id=viagem.id,
                estudante_id=i.estudante_id,
                parada_id=i.parada_id,
                status=inicial,
                status_inicial=inicial,
            )
        )
    viagem.status = StatusViagem.EM_ANDAMENTO
    viagem.iniciada_em = agora()
    db.flush()
    _avisar_status(db, viagem)
    for i in inscricoes:
        if i.estudante_id not in ausentes:
            nome = notificacoes.nome_curto(db.get(Estudante, i.estudante_id))
            notificacoes.para_responsaveis(
                db,
                i.estudante_id,
                "onibus_saiu",
                "Ônibus a caminho",
                f"O ônibus de {nome} saiu e está a caminho.",
                viagem_id=viagem.id,
            )


def _avisar_status(db: Session, viagem: Viagem) -> None:
    tempo_real.enfileirar(
        db,
        viagem.id,
        {"tipo": "viagem_status", "viagem_id": viagem.id, "status": viagem.status.value},
    )


# Eventos


@dataclass
class EventoEntrada:
    id: uuid.UUID
    tipo: TipoEvento
    hora_aparelho: datetime
    estudante_id: int | None = None
    parada_id: int | None = None
    localizacao: Coordenadas | None = None
    justificativa: str | None = None


@dataclass
class Resultado:
    id: uuid.UUID
    resultado: str  # aceito | duplicado | rejeitado
    motivo: str | None = None
    anomalia: str | None = None


@dataclass
class _Aplicacao:
    resultados: list[Resultado] = field(default_factory=list)
    afetados: set[int] = field(default_factory=set)


def _longe_da_parada(db: Session, viagem_id: int, parada_id: int, ponto: Coordenadas) -> bool:
    longe = db.scalar(
        text(
            """
            SELECT NOT ST_DWithin(
                vp.localizacao::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                vp.raio_cerca_m
            )
            FROM viagem_parada vp WHERE vp.viagem_id = :v AND vp.parada_id = :p
            """
        ),
        {"lon": ponto.longitude, "lat": ponto.latitude, "v": viagem_id, "p": parada_id},
    )
    return bool(longe)


def _avaliar(
    db: Session, viagem: Viagem, evento: EventoEntrada, alunos: dict[int, ViagemAluno]
) -> tuple[str | None, str | None]:
    """Devolve (motivo de rejeição, anomalia). Anomalia aceita o evento mas o sinaliza."""
    tipo = evento.tipo
    if tipo == TipoEvento.ONIBUS_VAZIO:
        return None, None
    if tipo == TipoEvento.CORRECAO:
        return "Correção só pelo gestor, em /viagens/{id}/correcoes", None
    if evento.estudante_id is None:
        return "Informe o estudante", None
    if tipo == TipoEvento.EMBARQUE_FORA_DA_LISTA:
        if not (evento.justificativa and len(evento.justificativa.strip()) >= 5):
            return "Embarque fora da lista exige justificativa", None
        return None, "fora_da_lista"
    aluno = alunos.get(evento.estudante_id)
    if aluno is None:
        # R3: quem não está na lista não embarca por um toque comum.
        return "Aluno fora da lista: registre como embarque fora da lista, com justificativa", None
    anomalias: list[str] = []
    if tipo == TipoEvento.EMBARQUE and evento.parada_id not in (None, aluno.parada_id):
        anomalias.append("parada_errada")  # R4
    parada_ref = evento.parada_id or aluno.parada_id
    if evento.localizacao is not None and parada_ref is not None:
        if _longe_da_parada(db, viagem.id, parada_ref, evento.localizacao):
            anomalias.append("longe_da_parada")  # R5
    return None, ",".join(anomalias) or None


def aplicar_eventos(
    db: Session, viagem: Viagem, autor: Usuario, eventos: list[EventoEntrada]
) -> list[Resultado]:
    """Grava o lote de forma idempotente e recalcula só os alunos tocados."""
    ap = _Aplicacao()
    alunos = {
        a.estudante_id: a
        for a in db.scalars(select(ViagemAluno).where(ViagemAluno.viagem_id == viagem.id))
    }
    limite = agora().timestamp() + TOLERANCIA_RELOGIO_S
    for ev in eventos:
        if ev.hora_aparelho.timestamp() > limite:
            ap.resultados.append(Resultado(ev.id, "rejeitado", "Hora do aparelho no futuro"))
            continue
        motivo, anomalia = _avaliar(db, viagem, ev, alunos)
        if motivo:
            ap.resultados.append(Resultado(ev.id, "rejeitado", motivo))
            continue
        gravado = db.scalar(
            insert(EventoViagem)
            .values(
                id=ev.id,
                viagem_id=viagem.id,
                tipo=ev.tipo,
                estudante_id=ev.estudante_id,
                parada_id=ev.parada_id,
                hora_aparelho=ev.hora_aparelho,
                localizacao=para_ponto(ev.localizacao) if ev.localizacao else None,
                autor_id=autor.id,
                justificativa=ev.justificativa,
                anomalia=anomalia,
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(EventoViagem.id)
        )
        if gravado is None:
            ap.resultados.append(Resultado(ev.id, "duplicado"))
            continue
        ap.resultados.append(Resultado(ev.id, "aceito", anomalia=anomalia))
        if ev.tipo == TipoEvento.EMBARQUE_FORA_DA_LISTA and ev.estudante_id not in alunos:
            na_viagem = db.scalar(
                select(ViagemParada.parada_id).where(
                    ViagemParada.viagem_id == viagem.id, ViagemParada.parada_id == ev.parada_id
                )
            )
            novo = ViagemAluno(
                viagem_id=viagem.id,
                estudante_id=ev.estudante_id,
                parada_id=na_viagem,
                status=StatusAluno.AGUARDANDO,
                status_inicial=StatusAluno.AGUARDANDO,
                fora_da_lista=True,
            )
            db.add(novo)
            alunos[ev.estudante_id] = novo
            alertar(
                db,
                viagem,
                "aluno_fora_da_lista",
                Severidade.AVISO,
                f"Aluno {ev.estudante_id} embarcou fora da lista: {ev.justificativa}",
            )
        elif anomalia and ev.tipo != TipoEvento.EMBARQUE_FORA_DA_LISTA:
            alertar(
                db,
                viagem,
                "registro_anomalo",
                Severidade.AVISO,
                f"Registro do aluno {ev.estudante_id} sinalizado: {anomalia}",
            )
        if ev.estudante_id is not None and ev.tipo in TIPOS_DE_ALUNO:
            ap.afetados.add(ev.estudante_id)
    db.flush()
    recalcular(db, viagem.id, ap.afetados)
    return ap.resultados


def alertar(
    db: Session, viagem: Viagem, tipo: str, severidade: Severidade, mensagem: str
) -> Alerta:
    alerta = Alerta(viagem_id=viagem.id, tipo=tipo, severidade=severidade, mensagem=mensagem)
    db.add(alerta)
    tempo_real.enfileirar(
        db,
        viagem.id,
        {
            "tipo": "alerta",
            "viagem_id": viagem.id,
            "alerta": tipo,
            "severidade": severidade.value,
            "mensagem": mensagem,
        },
    )
    return alerta


_TEXTOS = {
    StatusAluno.EMBARCOU: ("embarcou", "Embarque confirmado", "{nome} embarcou no ônibus."),
    StatusAluno.NAO_EMBARCOU: (
        "nao_embarcou",
        "Não embarcou",
        "{nome} não embarcou no ônibus. Se não era esperado, fale com a escola.",
    ),
    StatusAluno.DESEMBARCOU: ("desembarcou", "Chegada confirmada", "{nome} desembarcou."),
}


def _notificar_status(db: Session, viagem_id: int, estudante_id: int, novo: StatusAluno) -> None:
    modelo = _TEXTOS.get(novo)
    if modelo is None:
        return
    tipo, titulo, texto = modelo
    viagem = db.get(Viagem, viagem_id)
    if novo == StatusAluno.DESEMBARCOU and viagem is not None and viagem.sentido.value == "ida":
        titulo, texto = "Chegou à escola", "{nome} chegou à escola."
    nome = notificacoes.nome_curto(db.get(Estudante, estudante_id))
    notificacoes.para_responsaveis(
        db, estudante_id, tipo, titulo, texto.format(nome=nome), viagem_id=viagem_id
    )


def recalcular(db: Session, viagem_id: int, estudante_ids: set[int]) -> None:
    """Status = efeito dos eventos do aluno, na ordem da hora do aparelho."""
    if not estudante_ids:
        return
    eventos = db.scalars(
        select(EventoViagem)
        .where(
            EventoViagem.viagem_id == viagem_id,
            EventoViagem.estudante_id.in_(estudante_ids),
            EventoViagem.tipo.in_(TIPOS_DE_ALUNO),
        )
        .order_by(EventoViagem.hora_aparelho, EventoViagem.recebido_em, EventoViagem.id)
    ).all()
    por_aluno: dict[int, list[EventoViagem]] = {i: [] for i in estudante_ids}
    for e in eventos:
        por_aluno[e.estudante_id].append(e)
    for estudante_id, lista in por_aluno.items():
        aluno = db.get(ViagemAluno, (viagem_id, estudante_id))
        if aluno is None:
            continue
        atual = aluno.status_inicial
        for e in lista:
            if e.tipo == TipoEvento.CORRECAO:
                atual = e.status_corrigido or atual
            else:
                atual = _STATUS_DO_TIPO[e.tipo]
        if aluno.status != atual:
            aluno.status = atual
            _notificar_status(db, viagem_id, estudante_id, atual)
            # Só o responsável desse aluno recebe: o repasse filtra por estudante_id.
            tempo_real.enfileirar(
                db,
                viagem_id,
                {
                    "tipo": "aluno",
                    "viagem_id": viagem_id,
                    "estudante_id": estudante_id,
                    "status": atual.value,
                },
            )
    db.flush()


def corrigir(
    db: Session,
    viagem: Viagem,
    gestor: Usuario,
    estudante_id: int,
    novo_status: StatusAluno,
    motivo: str,
) -> None:
    """R13: correção é um evento novo, com autor e motivo; nada é reescrito."""
    if db.get(ViagemAluno, (viagem.id, estudante_id)) is None:
        raise erro(status.HTTP_404_NOT_FOUND, "Aluno não está na lista desta viagem")
    db.add(
        EventoViagem(
            id=uuid.uuid4(),
            viagem_id=viagem.id,
            tipo=TipoEvento.CORRECAO,
            estudante_id=estudante_id,
            hora_aparelho=agora(),
            autor_id=gestor.id,
            justificativa=motivo,
            status_corrigido=novo_status,
        )
    )
    db.flush()
    recalcular(db, viagem.id, {estudante_id})


# Conclusão (regra R2)


def pendencias_para_concluir(db: Session, viagem: Viagem) -> list[str]:
    pendentes: list[str] = []
    linhas = list(db.scalars(select(ViagemAluno).where(ViagemAluno.viagem_id == viagem.id)))
    nomes = {
        id_: nome
        for id_, nome in db.execute(
            select(Estudante.id, Estudante.nome).where(
                Estudante.id.in_([a.estudante_id for a in linhas])
            )
        )
    }
    for aluno in linhas:
        if aluno.status not in STATUS_FINAIS:
            nome = nomes.get(aluno.estudante_id, str(aluno.estudante_id))
            situacao = (
                "ainda está a bordo" if aluno.status == StatusAluno.EMBARCOU else "sem registro"
            )
            pendentes.append(f"{nome}: {situacao}")
    ultimo_vazio = db.scalar(
        select(func.max(EventoViagem.hora_aparelho)).where(
            EventoViagem.viagem_id == viagem.id, EventoViagem.tipo == TipoEvento.ONIBUS_VAZIO
        )
    )
    if ultimo_vazio is None:
        pendentes.append("Falta confirmar que o ônibus foi percorrido e está vazio")
    else:
        ultimo_movimento = db.scalar(
            select(func.max(EventoViagem.hora_aparelho)).where(
                EventoViagem.viagem_id == viagem.id,
                EventoViagem.tipo.in_(TIPOS_DE_ALUNO - {TipoEvento.CORRECAO}),
            )
        )
        if ultimo_movimento is not None and ultimo_movimento > ultimo_vazio:
            pendentes.append("Houve embarque ou desembarque depois da confirmação de ônibus vazio")
    return pendentes


def concluir(db: Session, viagem: Viagem) -> None:
    if viagem.status != StatusViagem.EM_ANDAMENTO:
        raise erro(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    pendencias = pendencias_para_concluir(db, viagem)
    if pendencias:
        raise erro(
            status.HTTP_409_CONFLICT,
            "A viagem não pode ser concluída: há crianças sem destino confirmado",
            pendencias=pendencias,
        )
    viagem.status = StatusViagem.CONCLUIDA
    viagem.concluida_em = agora()
    db.flush()
    _avisar_status(db, viagem)


# Cerca da escola (chamado pela posição do ônibus)


def verificar_saida_da_cerca(db: Session, viagem: Viagem, ponto: Coordenadas) -> Alerta | None:
    """Na ida, sair da cerca da escola com criança a bordo abre alerta crítico para o gestor.

    Só vale depois de o ônibus ter estado dentro da cerca; a flag `dentro_da_cerca_escola` guarda
    a última posição conhecida. Não depende de o motorista tentar concluir.
    """
    dentro = bool(
        db.scalar(
            text(
                """
                SELECT ST_DWithin(
                    e.localizacao::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    e.raio_cerca_m
                ) FROM escola e WHERE e.id = :escola
                """
            ),
            {"lon": ponto.longitude, "lat": ponto.latitude, "escola": viagem.escola_id},
        )
    )
    alerta = None
    saiu = viagem.dentro_da_cerca_escola and not dentro
    if saiu and viagem.status == StatusViagem.EM_ANDAMENTO and viagem.sentido.value == "ida":
        a_bordo = db.scalars(
            select(ViagemAluno.estudante_id).where(
                ViagemAluno.viagem_id == viagem.id, ViagemAluno.status == StatusAluno.EMBARCOU
            )
        ).all()
        aberto = db.scalar(
            select(Alerta.id).where(
                Alerta.viagem_id == viagem.id,
                Alerta.tipo == "crianca_a_bordo_fora_da_escola",
                Alerta.resolvido_em.is_(None),
            )
        )
        if a_bordo and aberto is None:
            alerta = alertar(
                db,
                viagem,
                "crianca_a_bordo_fora_da_escola",
                Severidade.CRITICO,
                f"O ônibus saiu da escola com {len(a_bordo)} criança(s) ainda a bordo",
            )
    viagem.dentro_da_cerca_escola = dentro
    db.flush()
    return alerta


# Cancelamento e avisos


def responsaveis_da_viagem(db: Session, viagem: Viagem) -> list[tuple[int, int]]:
    """(responsável, estudante) com consentimento, para quem está na lista ou inscrito."""
    if viagem.status == StatusViagem.AGENDADA:
        estudantes = [i.estudante_id for i in inscricoes_do_dia(db, viagem.rota_id, viagem.data)]
    else:
        estudantes = list(
            db.scalars(select(ViagemAluno.estudante_id).where(ViagemAluno.viagem_id == viagem.id))
        )
    if not estudantes:
        return []
    return [
        (r.responsavel_id, r.estudante_id)
        for r in db.scalars(
            select(ResponsavelEstudante).where(
                ResponsavelEstudante.estudante_id.in_(estudantes),
                consentimento.vigente(),
            )
        )
    ]


def cancelar(db: Session, viagem: Viagem, gestor: Usuario, motivo: str) -> int:
    if viagem.status not in (StatusViagem.AGENDADA, StatusViagem.EM_ANDAMENTO):
        raise erro(status.HTTP_409_CONFLICT, f"A viagem está {viagem.status.value}")
    if viagem.status == StatusViagem.EM_ANDAMENTO:
        a_bordo = db.scalar(
            select(func.count())
            .select_from(ViagemAluno)
            .where(ViagemAluno.viagem_id == viagem.id, ViagemAluno.status == StatusAluno.EMBARCOU)
        )
        if a_bordo:
            raise erro(
                status.HTTP_409_CONFLICT,
                "Há criança a bordo: desembarque ou corrija os registros antes de cancelar",
            )
    destinatarios = responsaveis_da_viagem(db, viagem)
    viagem.status = StatusViagem.CANCELADA
    viagem.cancelada_em = agora()
    viagem.cancelada_por_id = gestor.id
    viagem.motivo_cancelamento = motivo
    for responsavel_id, estudante_id in destinatarios:
        notificacoes.criar(
            db,
            responsavel_id,
            "viagem_cancelada",
            "Viagem cancelada",
            f"A viagem de {viagem.data:%d/%m} foi cancelada: {motivo}",
            viagem_id=viagem.id,
            estudante_id=estudante_id,
        )
    db.flush()
    _avisar_status(db, viagem)
    return len(destinatarios)


def aviso_de_ausencia_tardia(db: Session, estudante_id: int, dia: date, sentido) -> None:
    """R12: ausência avisada com a viagem em andamento vira aviso na lista do motorista."""
    consulta = (
        select(ViagemAluno)
        .join(Viagem, Viagem.id == ViagemAluno.viagem_id)
        .where(
            ViagemAluno.estudante_id == estudante_id,
            Viagem.data == dia,
            Viagem.status == StatusViagem.EM_ANDAMENTO,
        )
    )
    if sentido is not None:
        consulta = consulta.where(Viagem.sentido == sentido)
    for aluno in db.scalars(consulta):
        aluno.ausencia_avisada_em = agora()
        if aluno.status == StatusAluno.AGUARDANDO:
            aluno.status = StatusAluno.AUSENCIA_AVISADA
            aluno.status_inicial = StatusAluno.AUSENCIA_AVISADA
