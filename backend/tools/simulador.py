# ruff: noqa: E501
"""Simulador de ônibus: faz o que o celular do motorista faria, sem ninguém andar de ônibus.

    python -m tools.simulador --api http://localhost:8000 --email m@x.com --senha ... \
        [--viagem 12] [--velocidade 20] [--sem-sinal] [--desvio] [--crianca-a-bordo]

Entra como motorista, inicia a viagem do dia, anda em linha reta pelas paradas enviando posições
a cada 5 s simulados (o tempo pode ser acelerado com --velocidade), confirma os embarques em cada
parada e conclui. As opções provocam os casos que o painel precisa mostrar.
"""

import argparse
import math
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

KMH = 30.0
PASSO_S = 5


def _metros(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat, dlon = (b[0] - a[0]) * 111_320, (b[1] - a[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon)


def _trajeto(paradas: list[dict], desvio: bool) -> list[tuple[float, float, int | None]]:
    """Pontos a cada PASSO_S, com o índice da parada quando o ponto cai nela."""
    pontos: list[tuple[float, float, int | None]] = []
    por_passo = KMH / 3.6 * PASSO_S
    for i, (a, b) in enumerate(zip(paradas, paradas[1:], strict=False)):
        origem, destino = (a["latitude"], a["longitude"]), (b["latitude"], b["longitude"])
        n = max(1, round(_metros(origem, destino) / por_passo))
        for k in range(n):
            f = k / n
            lat = origem[0] + (destino[0] - origem[0]) * f
            lon = origem[1] + (destino[1] - origem[1]) * f
            if desvio and i == len(paradas) // 2 - 1:
                lon += 0.004  # cerca de 450 m para o lado: passa do limite de desvio
            pontos.append((lat, lon, i if k == 0 else None))
    ultima = paradas[-1]
    pontos.append((ultima["latitude"], ultima["longitude"], len(paradas) - 1))
    return pontos


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--email", required=True)
    p.add_argument("--senha", required=True)
    p.add_argument("--viagem", type=int)
    p.add_argument("--velocidade", type=float, default=20.0, help="fator de aceleração do tempo")
    p.add_argument(
        "--sem-sinal", action="store_true", help="para de enviar no meio e envia tudo depois"
    )
    p.add_argument("--desvio", action="store_true", help="sai do trajeto previsto num trecho")
    p.add_argument("--crianca-a-bordo", action="store_true", help="não registra um desembarque")
    a = p.parse_args()

    http = httpx.Client(base_url=a.api, timeout=15)
    token = (
        http.post("/auth/login", data={"username": a.email, "password": a.senha})
        .raise_for_status()
        .json()
    )
    http.headers["Authorization"] = f"Bearer {token['access_token']}"

    viagens = http.get("/motorista/viagens-hoje").raise_for_status().json()
    viagem = next((v for v in viagens if a.viagem in (None, v["id"])), None)
    if viagem is None:
        raise SystemExit("Nenhuma viagem de hoje para este motorista")
    vid = viagem["id"]
    if viagem["status"] == "agendada":
        http.post(f"/viagens/{vid}/iniciar").raise_for_status()
        print(f"viagem {vid} iniciada")
    lista = http.get(f"/viagens/{vid}/lista").raise_for_status().json()
    paradas, alunos = lista["paradas"], lista["alunos"]
    pontos = _trajeto(paradas, a.desvio)
    inicio = datetime.now(UTC) - timedelta(seconds=PASSO_S * len(pontos))
    pendentes: list[dict] = []
    ficou_a_bordo = None
    embarcados: list[dict] = []

    def evento(tipo: str, aluno: dict | None, quando: datetime) -> dict:
        e = {"id": str(uuid.uuid4()), "tipo": tipo, "hora_aparelho": quando.isoformat()}
        if aluno:
            e["estudante_id"] = aluno["estudante_id"]
            e["parada_id"] = aluno["parada_id"]
        return e

    for i, (lat, lon, parada_idx) in enumerate(pontos):
        quando = inicio + timedelta(seconds=PASSO_S * i)
        pendentes.append(
            {
                "registrada_em": quando.isoformat(),
                "latitude": lat,
                "longitude": lon,
                "velocidade_kmh": KMH,
            }
        )
        eventos = []
        if parada_idx is not None:
            pid = paradas[parada_idx]["parada_id"]
            for al in alunos:
                if al["parada_id"] == pid and al["status"] == "aguardando":
                    eventos.append(evento("embarque", al, quando))
                    embarcados.append(al)
        sem_sinal = a.sem_sinal and len(pontos) // 3 < i < 2 * len(pontos) // 3
        if not sem_sinal:
            http.post(f"/viagens/{vid}/posicoes", json={"posicoes": pendentes}).raise_for_status()
            pendentes = []
        if eventos:
            http.post(f"/viagens/{vid}/eventos", json={"eventos": eventos}).raise_for_status()
        time.sleep(PASSO_S / a.velocidade)

    fim = datetime.now(UTC) - timedelta(seconds=30)
    final = []
    for al in embarcados:
        if a.crianca_a_bordo and ficou_a_bordo is None:
            ficou_a_bordo = al
            continue
        final.append(evento("desembarque", al, fim))
    final.append(evento("onibus_vazio", None, fim + timedelta(seconds=5)))
    if final:
        http.post(f"/viagens/{vid}/eventos", json={"eventos": final}).raise_for_status()
    r = http.post(f"/viagens/{vid}/concluir")
    if r.status_code == 200:
        print("viagem concluída")
    else:
        print("a API recusou a conclusão (esperado com --crianca-a-bordo):", r.json()["detail"])


if __name__ == "__main__":
    main()
