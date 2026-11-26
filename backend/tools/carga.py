# ruff: noqa: E501
"""Teste de carga: N ônibus enviando posição a cada 5 s, com painéis e responsáveis no WebSocket.

    python -m tools.carga --api http://localhost:8000 --admin-email a@x.com --admin-senha ... \
        --onibus 50 --paineis 5 --responsaveis 20 --duracao 60

Cria os dados com a API (prefixo único, não mexe no que já existe), inicia as viagens e mede:
latência do POST de posições e atraso entre o envio e a chegada da mensagem nos WebSockets.
"""

import argparse
import asyncio
import json
import statistics
import string
import time
from datetime import UTC, datetime

import httpx
import websockets

LAT0 = -25.40
SENHA = "senha-de-carga-123"


def _placa(i: int) -> str:
    a, b, c = (
        string.ascii_uppercase[i // 676 % 26],
        string.ascii_uppercase[i // 26 % 26],
        string.ascii_uppercase[i % 26],
    )
    return f"{a}{b}{c}{i % 10}{string.ascii_uppercase[(i // 10) % 26]}{(i * 7) % 10}{(i * 3) % 10}"


def _pct(valores: list[float], p: float) -> float:
    if not valores:
        return float("nan")
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * p))]


class _Cliente(httpx.Client):
    """Espera e repete quando o limite de escritas da API responde 429 (a semeadura é intensa)."""

    def send(self, request, **kw):
        while True:
            resposta = super().send(request, **kw)
            if resposta.status_code != 429:
                return resposta
            time.sleep(float(resposta.headers.get("Retry-After", "5")) / 4)


def semear(api: str, email: str, senha: str, n: int, responsaveis: int) -> dict:
    http = _Cliente(base_url=api, timeout=30)
    tok = (
        http.post("/auth/login", data={"username": email, "password": senha})
        .raise_for_status()
        .json()
    )
    http.headers["Authorization"] = f"Bearer {tok['access_token']}"
    marca = str(int(time.time()))
    escola = (
        http.post(
            "/escolas",
            json={"nome": f"Carga {marca}", "localizacao": {"latitude": LAT0, "longitude": -49.2}},
        )
        .raise_for_status()
        .json()
    )
    na_escola = (
        http.post(
            "/paradas",
            json={"nome": f"Escola {marca}", "localizacao": {"latitude": LAT0, "longitude": -49.2}},
        )
        .raise_for_status()
        .json()
    )
    onibus = []
    for i in range(n):
        lat = LAT0 - 0.03 - i * 0.0002
        a = (
            http.post(
                "/paradas",
                json={
                    "nome": f"A{i}-{marca}",
                    "localizacao": {"latitude": lat, "longitude": -49.2},
                },
            )
            .raise_for_status()
            .json()
        )
        veic = (
            http.post(
                "/veiculos",
                json={
                    "placa": _placa(i),
                    "capacidade": 40,
                    "modelo": "Carga",
                    "ano": 2022,
                    "vistoria_valida_ate": "2030-01-01",
                },
            )
            .raise_for_status()
            .json()
        )
        email_m = f"carga{marca}-{i}@exemplo.com"
        m = (
            http.post(
                "/usuarios",
                json={
                    "nome": f"Motorista {i}",
                    "email": email_m,
                    "senha": SENHA,
                    "perfil": "motorista",
                },
            )
            .raise_for_status()
            .json()
        )
        http.post(
            "/motoristas",
            json={
                "usuario_id": m["id"],
                "cnh": f"{int(marca) % 10**8:08d}{i:03d}",
                "categoria_cnh": "D",
                "cnh_valida_ate": "2030-01-01",
                "curso_transporte_escolar_ate": "2030-01-01",
            },
        ).raise_for_status()
        rota = (
            http.post(
                "/rotas",
                json={
                    "nome": f"Rota carga {marca}-{i}",
                    "escola_id": escola["id"],
                    "turno": "manha",
                    "sentido": "ida",
                    "veiculo_id": veic["id"],
                    "motorista_id": m["id"],
                },
            )
            .raise_for_status()
            .json()
        )
        http.put(
            f"/rotas/{rota['id']}/paradas", json={"parada_ids": [a["id"], na_escola["id"]]}
        ).raise_for_status()
        est = (
            http.post(
                "/estudantes",
                json={
                    "nome": f"Aluno {i}",
                    "data_nascimento": "2015-01-01",
                    "escola_id": escola["id"],
                    "turno": "manha",
                },
            )
            .raise_for_status()
            .json()
        )
        http.put(
            f"/rotas/{rota['id']}/inscricoes",
            json={
                "inscricoes": [
                    {
                        "estudante_id": est["id"],
                        "parada_id": a["id"],
                        "dias_semana": [0, 1, 2, 3, 4, 5, 6],
                        "vigencia_inicio": datetime.now(UTC).date().isoformat(),
                    }
                ]
            },
        ).raise_for_status()
        onibus.append(
            {"i": i, "rota": rota["id"], "email": email_m, "lat": lat, "estudante": est["id"]}
        )
    gestor_email = f"cargagestor{marca}@exemplo.com"
    http.post(
        "/usuarios",
        json={"nome": "Gestor carga", "email": gestor_email, "senha": SENHA, "perfil": "gestor"},
    ).raise_for_status()
    viagens = http.post("/viagens/gerar", json={}).raise_for_status().json()
    por_rota = {v["rota_id"]: v["id"] for v in viagens}
    pais = []
    for o in onibus[:responsaveis]:
        o["viagem"] = por_rota[o["rota"]]
    for o in onibus:
        o["viagem"] = por_rota[o["rota"]]
    for o in onibus[:responsaveis]:
        conv = (
            http.post(
                "/convites",
                json={
                    "nome": f"Pai {o['i']}",
                    "email": f"paicarga{marca}-{o['i']}@exemplo.com",
                    "estudante_id": o["estudante"],
                    "parentesco": "pai",
                },
            )
            .raise_for_status()
            .json()
        )
        t = (
            httpx.post(
                f"{api}/auth/convites/aceitar",
                json={"codigo": conv["codigo"], "senha": SENHA},
                timeout=30,
            )
            .raise_for_status()
            .json()
        )
        h = {"Authorization": f"Bearer {t['access_token']}"}
        httpx.post(
            f"{api}/responsavel/filhos/{o['estudante']}/consentimento",
            json={"versao_termo": "2026-11"},
            headers=h,
            timeout=30,
        ).raise_for_status()
        pais.append({"token": t["access_token"], "viagem": o["viagem"]})
    return {"onibus": onibus, "gestor": gestor_email, "pais": pais}


async def _login(c: httpx.AsyncClient, email: str) -> str:
    r = await c.post("/auth/login", data={"username": email, "password": SENHA})
    r.raise_for_status()
    return r.json()["access_token"]


async def carga(api: str, dados: dict, paineis: int, duracao: int) -> None:
    ws_url = api.replace("http", "ws", 1) + "/ws"
    lat_post: list[float] = []
    lat_ws: list[float] = []
    erros = {"post": 0, "ws": 0}
    recebidas = 0
    parar = asyncio.Event()

    async with httpx.AsyncClient(
        base_url=api, timeout=30, limits=httpx.Limits(max_connections=200)
    ) as c:
        tokens = await asyncio.gather(*[_login(c, o["email"]) for o in dados["onibus"]])
        for o, t in zip(dados["onibus"], tokens, strict=True):
            o["h"] = {"Authorization": f"Bearer {t}"}
            r = await c.post(f"/viagens/{o['viagem']}/iniciar", headers=o["h"])
            r.raise_for_status()
        gestor_token = await _login(c, dados["gestor"])

        async def cliente_ws(token: str, canal: str) -> None:
            nonlocal recebidas
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({"tipo": "auth", "token": token}))
                await ws.recv()
                await ws.send(json.dumps({"tipo": "inscrever", "canal": canal}))
                resposta = json.loads(await ws.recv())
                if resposta.get("tipo") != "inscrito":
                    erros["ws"] += 1
                    return
                while not parar.is_set():
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 1))
                    except TimeoutError:
                        continue
                    if msg.get("tipo") == "posicao":
                        recebidas += 1
                        enviada = datetime.fromisoformat(msg["registrada_em"]).timestamp()
                        lat_ws.append((time.time() - enviada) * 1000)

        async def onibus(o: dict) -> None:
            passo = 0
            await asyncio.sleep((o["i"] % 50) / 10)  # espalha o início dentro dos 5 s
            while not parar.is_set():
                inicio = time.perf_counter()
                lat = o["lat"] + passo * 0.00005
                corpo = {
                    "posicoes": [
                        {
                            "registrada_em": datetime.now(UTC).isoformat(),
                            "latitude": lat,
                            "longitude": -49.2,
                            "velocidade_kmh": 20,
                        }
                    ]
                }
                r = await c.post(f"/viagens/{o['viagem']}/posicoes", json=corpo, headers=o["h"])
                lat_post.append((time.perf_counter() - inicio) * 1000)
                if r.status_code != 200 or r.json()[0]["resultado"] != "aceita":
                    erros["post"] += 1
                passo += 1
                await asyncio.sleep(max(0, 5 - (time.perf_counter() - inicio)))

        tarefas = [asyncio.create_task(onibus(o)) for o in dados["onibus"]]
        tarefas += [asyncio.create_task(cliente_ws(gestor_token, "frota")) for _ in range(paineis)]
        tarefas += [
            asyncio.create_task(cliente_ws(p["token"], f"viagem:{p['viagem']}"))
            for p in dados["pais"]
        ]
        await asyncio.sleep(duracao)
        parar.set()
        await asyncio.gather(*tarefas, return_exceptions=True)

    print(
        f"\n=== Resultado: {len(dados['onibus'])} ônibus, {paineis} painéis, {len(dados['pais'])} responsáveis, {duracao} s ==="
    )
    print(
        f"POST de posição: {len(lat_post)} requisições, {erros['post']} erros, "
        f"p50 {statistics.median(lat_post):.0f} ms, p95 {_pct(lat_post, 0.95):.0f} ms, p99 {_pct(lat_post, 0.99):.0f} ms"
    )
    print(
        f"WebSocket: {recebidas} mensagens de posição entregues, {erros['ws']} inscrições recusadas, "
        f"atraso p50 {statistics.median(lat_ws):.0f} ms, p95 {_pct(lat_ws, 0.95):.0f} ms, p99 {_pct(lat_ws, 0.99):.0f} ms"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--admin-email", required=True)
    p.add_argument("--admin-senha", required=True)
    p.add_argument("--onibus", type=int, default=50)
    p.add_argument("--paineis", type=int, default=5)
    p.add_argument("--responsaveis", type=int, default=20)
    p.add_argument("--duracao", type=int, default=60)
    a = p.parse_args()
    dados = semear(a.api, a.admin_email, a.admin_senha, a.onibus, a.responsaveis)
    asyncio.run(carga(a.api, dados, a.paineis, a.duracao))


if __name__ == "__main__":
    main()
