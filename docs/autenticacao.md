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

O primeiro administrador é criado por `python -m app.criar_admin`. Os demais, por `POST /auth/usuarios`, só para administradores. Senhas são guardadas com Argon2.

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

Depois de 10 falhas seguidas para o mesmo e-mail e IP, novas tentativas recebem 429 por 15 minutos. A contagem fica em memória, por processo (`app/limite.py`). Com vários workers, troque pela implementação em Redis, que tem a mesma interface.

Atrás de um proxy reverso, defina `CONFIAR_PROXY=true` para o IP vir de `X-Forwarded-For`. Sem proxy, deixe `false`: senão qualquer cliente escolhe o próprio IP.

## Auditoria

A tabela `auditoria` registra login (sucesso e falha), troca de senha, logout, reuso de refresh token, criação de usuário, vínculo e consentimento, com autor, IP e hora. Senha e token nunca entram, mesmo que sejam passados por engano.

## Produção

Com `AMBIENTE=producao`:

- `/docs`, `/redoc` e `/openapi.json` ficam desligados;
- a resposta leva `Strict-Transport-Security`;
- a API não sobe se `CORS_ORIGINS` tiver origem sem `https://`.

Em qualquer ambiente, as respostas levam `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` e uma CSP restrita fora do Swagger.
