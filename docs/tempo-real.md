# Tempo real e posições

## Posições do ônibus

- O app do motorista envia `POST /viagens/{id}/posicoes` a cada 5 a 10 s, em lote quando ficou sem sinal (até 500 por chamada). Só o motorista escalado, só com a viagem em andamento.
- Um rastreador veicular usa `POST /rastreador/posicoes` com o cabeçalho `X-Token-Rastreador`. O token é gerado pelo gestor em `POST /veiculos/{id}/token-rastreador` (aparece uma vez; o banco guarda só o hash; gerar outro revoga o anterior).
- Cada ponto é aceito, duplicado (mesmo `registrada_em`) ou rejeitado: data no futuro, anterior ao início da viagem, velocidade informada acima de 200 km/h ou salto acima de 150 km/h em relação à posição anterior.
- A última posição de cada viagem fica no Redis (some em 6 h sem atualização) e todas ficam na tabela `posicao`. Painel, WebSocket e app do responsável leem do Redis; se ele cair, `GET /viagens/{id}/posicao` lê do banco.
- Chegada e partida de cada parada são detectadas pela cerca (`raio_cerca_m`) e gravadas em `viagem_parada`. A lista do motorista muda para `modo: "desembarque"` quando o ônibus chega à escola (ida) ou sai dela (volta).
- A previsão divide a distância restante no trajeto pela velocidade média dos últimos 5 minutos; com o ônibus parado (menos de 3 km/h) ela vem vazia em vez de absurda. O desvio é a distância da posição ao trajeto previsto (`desvio_m`).

## WebSocket `/ws`

1. Abra a conexão **sem token na URL** (a URL vai para log).
2. A primeira mensagem, em até 10 s, é `{"tipo": "auth", "token": "<token de acesso>"}`. Resposta: `{"tipo": "autenticado", "expira_em": <epoch>}`. Token inválido, de refresh ou de usuário desativado fecha com código `4401`, e o mesmo acontece quando o token vence: renove e reconecte.
3. Inscreva-se com `{"tipo": "inscrever", "canal": "frota"}` ou `{"tipo": "inscrever", "canal": "viagem:12"}`. Resposta `inscrito` ou `recusado`. Cancele com `{"tipo": "cancelar", "canal": ...}`.

| Canal | Quem assina |
| --- | --- |
| `frota` | administrador e gestor |
| `viagem:{id}` | administrador, gestor, motorista e monitor escalados (no dia) e o responsável de uma criança que ainda está na viagem (esperada ou a bordo), com a viagem em andamento |

Mensagens (todas trazem `canal`): `posicao`, `chegada_parada`, `partida_parada`, `viagem_status`, `aluno` (`estudante_id` e `status`) e `alerta`. O responsável só recebe `posicao`, `viagem_status` e o `aluno` dos próprios filhos. O escopo é conferido a cada mensagem entregue: quando o filho desembarca (ou falta, ou a viagem acaba) o responsável recebe `canal_encerrado` e não recebe mais posições.

Entre processos da API, as mensagens passam pelo pub/sub do Redis e só saem **depois do commit** da requisição que as gerou.

## Worker, alertas e notificações

O processo `worker` (`python -m app.worker`, serviço `worker` no `compose.yaml`) roda as regras que dependem do tempo passar e envia as notificações. Acorda por mensagem no Redis (uma emergência, por exemplo) ou a cada 5 s; as regras rodam a cada 15 s.

| Regra | Alerta | Limite (tabela `configuracao`) |
| --- | --- | --- |
| R6 | `viagem_nao_iniciada` | `viagem_nao_iniciada_min` (10) |
| R7 | `sem_sinal` (resolve sozinho quando o sinal volta) | `sem_sinal_s` (120) |
| R8 | `desvio_de_rota` | `desvio_max_m` (300) |
| R9 | `parada_nao_prevista` | `parada_nao_prevista_min` (5), `parado_raio_m` (30) |
| R10 | `velocidade_acima_do_limite` | `velocidade_max_kmh` (80) |
| R11 | `emergencia` (crítico, `POST /viagens/{id}/emergencia`) | `emergencia_avisa_responsaveis` (0) |

Os limites mudam em `PUT /configuracao/alertas` (só administrador), sem novo deploy. Alertas: `GET /alertas`, `POST /alertas/{id}/reconhecer` e `/resolver`.

**Emergência:** a resposta é imediata (202). O alerta crítico (com a última posição conhecida) e as notificações são criados na hora, a mensagem sai no canal `frota` e o worker envia o push aos gestores. Os responsáveis só são avisados se a opção `emergencia_avisa_responsaveis` estiver ligada (decisão do grupo, ver issue #25); o texto não cita nenhuma criança.

**Push:** o app registra o token com `POST /dispositivos` e lê as mensagens em `GET /notificacoes` (e `POST /notificacoes/{id}/lida`). O worker envia as pendentes pela API HTTP v1 do Firebase, tenta de novo com espera crescente (30 s, 1 min, 2 min... até 1 h, no máximo 5 tentativas) e apaga o token que o Firebase recusa. Sem `FCM_CREDENCIAIS` e `FCM_PROJETO`, o push só é registrado em log. Os textos citam apenas o primeiro nome do próprio filho.
