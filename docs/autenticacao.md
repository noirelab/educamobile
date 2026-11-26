# Autenticação e perfis

## Fluxo

1. `POST /auth/login` recebe `username` (e-mail) e `password` como formulário e devolve `access_token`, `refresh_token` e `expires_in` (segundos).
2. As demais rotas exigem o cabeçalho `Authorization: Bearer <access_token>`.
3. O token de acesso dura 15 minutos (`JWT_EXPIRE_MINUTES`, no máximo 60). Antes de expirar, o app chama `POST /auth/refresh` com `{"refresh_token": "..."}` e recebe um par novo.
4. O refresh token dura 7 dias (`REFRESH_EXPIRE_DAYS`) e **troca a cada uso**. O token antigo deixa de valer. Se um token já trocado for usado de novo, a API entende que ele foi copiado: revoga todas as sessões da pessoa e registra `sessao.reuso` na auditoria.
5. A cada requisição o usuário é lido do banco, então desativar uma conta ou mudar seu perfil vale na hora.

O banco guarda só o HMAC do refresh token, nunca o token.

| Rota | Efeito |
| --- | --- |
| `POST /auth/logout` | Encerra a sessão deste aparelho (pelo refresh token). O token de acesso já emitido vale até expirar. |
| `POST /auth/logout-todos` | Encerra todas as sessões e invalida na hora todos os tokens de acesso. |
| `PUT /auth/senha` | Pede a senha atual; troca a senha e encerra todas as sessões. Cinco erros seguidos bloqueiam por 15 minutos. |

O primeiro administrador é criado por `python -m app.criar_admin`. Os demais entram por `POST /usuarios`: o administrador cria qualquer perfil menos responsável, e o gestor cria motorista e monitor. Senhas são guardadas com Argon2.

## Perfis

A reformulação (ver `docs/reformulacao/`) introduz os perfis do transporte. Durante a transição, os antigos convivem com os novos.

| Perfil | Situação | Acesso |
| --- | --- | --- |
| `admin` | fica | tudo |
| `gestor` | novo | o mesmo do coordenador, mais o vínculo de responsáveis |
| `motorista`, `monitor` | novos | só as rotas de conta, por enquanto; as viagens chegam na etapa C |
| `responsavel` | novo | só as rotas de conta e `/responsavel/*`, filtradas pelo vínculo |
| `diretor`, `coordenador` | saem na etapa A | como antes |

Responsável, motorista e monitor **não** acessam nenhuma rota de cadastro. Um teste (`test_perfis_externos_barrados_em_todas_as_rotas_de_cadastro`) percorre todas as rotas da API e falha se alguma responder diferente de 403 para esses perfis. Uma rota nova para eles precisa ser liberada de propósito, no teste e no código.

## Permissões das rotas de cadastro

| Recurso | Administrador | Gestor | Diretor de Escola | Coordenador de Logística |
| --- | --- | --- | --- | --- |
| Usuários | tudo | não | não | não |
| Polos e escolas | tudo | leitura | leitura | leitura |
| Turmas | tudo | leitura | tudo, na própria escola | leitura |
| Professores | tudo | não | tudo, na própria escola | não |
| Estudantes | tudo | leitura | criar já com matrícula na própria escola; ler e alterar os da própria escola, exceto a parada | leitura |
| Matrículas e frequência | tudo | não | tudo, na própria escola | não |
| Paradas e rotas | tudo | tudo | leitura | tudo |
| Vínculo responsável–estudante | tudo | tudo | não | não |

Um estudante é da escola em que tem matrícula ativa.

## Vínculo com o responsável

- O gestor liga um usuário de perfil `responsavel` a um estudante: `POST /estudantes/{id}/responsaveis`.
- O responsável vê a lista dos filhos (`GET /responsavel/filhos`) só com nome e parentesco.
- Para ver qualquer outro dado, ele aceita o termo: `POST /responsavel/filhos/{id}/consentimento` com a versão atual (`VERSAO_TERMO_CONSENTIMENTO`). Data e versão ficam guardadas (LGPD, art. 14).
- Sem vínculo, a resposta é 404, igual à de um estudante inexistente.

## Regras do diretor

- Matricula apenas quem já passou pela própria escola. Estudante novo entra por `POST /estudantes` com o campo `matricula`, na mesma transação.
- Transfere apenas entre turmas da própria escola. Transferência entre escolas cabe ao administrador.
- Para um estudante fora do escopo, a resposta é a mesma de um id inexistente, para não revelar quais estudantes existem.

## Proteção do login

Três contadores, todos com janela de 15 minutos (`app/limite.py`):

| Contador | Limite | Contra o quê |
| --- | --- | --- |
| mesmo IP e mesmo e-mail | 10 falhas | adivinhar a senha de uma conta |
| mesmo IP, qualquer e-mail | 30 falhas | testar uma senha comum em muitas contas |
| mesmo e-mail, qualquer IP | 50 falhas | ataque à mesma conta vindo de muitos IPs |

Passado o limite, a resposta é 429, inclusive com a senha certa. Login bem-sucedido zera os contadores da conta, mas não o do IP: senão um atacante com uma conta válida intercalaria logins próprios para continuar tentando senhas alheias. O contador por conta tem um custo conhecido: quem souber o e-mail de alguém consegue bloquear o login dessa pessoa por 15 minutos. Fica registrado na auditoria.

Quando a memória enche, saem primeiro os contadores expirados e os que ainda não bloquearam; inundar o login com e-mails inventados não libera uma conta bloqueada.

A contagem é por processo. Com vários workers, troque pela implementação em Redis, que tem a mesma interface.

### IP do cliente

- Rode o uvicorn com `--no-proxy-headers` (já está no Dockerfile). Sem isso, o uvicorn aceita `X-Forwarded-For` de conexões locais e qualquer um troca de IP só mudando o cabeçalho.
- Atrás de um proxy reverso, defina `CONFIAR_PROXY=true`. A API usa o **último** IP de `X-Forwarded-For`, que é o que o proxy acrescentou; os anteriores vêm do cliente.

## Limites de entrada

- Corpo da requisição até 1 MB (`MAX_CORPO_BYTES`); acima disso, 413 antes de ler o corpo.
- Erros 422 trazem só `loc`, `msg` e `type`. O valor enviado não volta na resposta (antes, uma senha fora do padrão voltava no corpo do erro).
- `JWT_SECRET` com o valor do `.env.example`, ou com menos de 12 caracteres diferentes, impede a API de subir. Em produção, a senha de banco do exemplo também.

## Auditoria

A tabela `auditoria` registra login (sucesso e falha), troca de senha, logout, reuso de refresh token, criação de usuário, vínculo e consentimento, com autor, IP e hora. Senha e token nunca entram, mesmo que sejam passados por engano.

## Produção

Com `AMBIENTE=producao`:

- `/docs`, `/redoc` e `/openapi.json` ficam desligados;
- a resposta leva `Strict-Transport-Security`;
- a API não sobe se `CORS_ORIGINS` tiver origem sem `https://`.

Em qualquer ambiente, as respostas levam `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` e uma CSP restrita fora do Swagger.

## Convite de responsável

Responsável não tem cadastro aberto. O gestor chama `POST /convites` com nome, e-mail, estudante e parentesco; a resposta traz o `codigo` uma única vez (o banco guarda só o hash, válido por 72 h). O responsável abre o link e chama `POST /auth/convites/aceitar` com o código e a senha que escolheu, os dois no corpo (no caminho da URL, o código iria para o log do nginx e do proxy). O convite cria a conta e o vínculo com o estudante e devolve os tokens. Depois do primeiro uso ele deixa de valer, e tentativas com código errado são limitadas por IP. O consentimento (LGPD, art. 14) continua pendente até o responsável aceitá-lo.

## Sessões e limites

- No máximo 10 aparelhos conectados por conta; ao passar disso, a sessão mais antiga é revogada. `GET /auth/sessoes` lista os aparelhos (sem token) e `DELETE /auth/sessoes/{id}` derruba um. O worker apaga sessões expiradas ou revogadas há mais de 30 dias.
- O limite de tentativas (login, troca de senha, aceite de convite) e o limite geral de escritas (300 por minuto por token) e de posições (120 por minuto) usam o Redis quando `LIMITE_BACKEND=redis`, o que a produção exige: assim o bloqueio vale para todos os processos da API.
- O logout derruba o refresh token na hora; o token de acesso do aparelho continua valendo até vencer (15 minutos). Uma lista de `jti` revogados no Redis fecharia essa janela, mas cada requisição passaria a consultá-la; para o risco atual (token de curta duração e `logout-todos` que invalida todos) a decisão é não adotá-la agora, e a avaliação fica registrada aqui.

## Guarda do token no navegador (CSP)

O token de acesso e o refresh token ficam em `sessionStorage`, legíveis por qualquer script da página. A segunda barreira é a política de conteúdo (CSP) servida pelo nginx do frontend (`frontend/nginx.conf.template`): `script-src 'self'` (sem script inline nem `eval`), `connect-src` só com a API (HTTP e WebSocket, vindos de `API_ORIGIN` e `WS_ORIGIN`), `img-src` com os tiles do OpenStreetMap, `frame-ancestors 'none'`.

- **Leaflet:** não exige `style-src 'unsafe-inline'` (usa `element.style`). Quem exige é o Sonner, que injeta um `<style>`; por isso `style-src` mantém `'unsafe-inline'`, que é o risco menor (estilo, não script).
- **Verificado:** o build não tem script inline, nem `eval` nem `new Function`; o cabeçalho sai em `/` e nos arquivos estáticos; a tela de login carrega com a CSP ligada no Chrome, sem violação. **Não verificado:** os testes e2e do Playwright e as telas com mapa com a CSP ligada (precisam da API e de um usuário semeados).
- **Cookie `HttpOnly` + `SameSite=Strict` para o refresh token (avaliado, não adotado):** tira o refresh token do alcance de um XSS, mas exige que a API leia e grave o cookie, proteção contra CSRF nas rotas de renovação e logout, e o app nativo do motorista e o do responsável continuam enviando o token no corpo. Fica como evolução se a banca ou a secretaria exigir; a CSP e o refresh que gira a cada uso cobrem o risco atual.
