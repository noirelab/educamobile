# Autenticação e perfis

## Fluxo

1. `POST /auth/login` recebe `username` (e-mail) e `password` como formulário e devolve um JWT.
2. As demais rotas exigem o cabeçalho `Authorization: Bearer <token>`.
3. O token expira em 60 minutos (`JWT_EXPIRE_MINUTES`). Não há refresh token: ao expirar, é preciso entrar de novo.
4. A cada requisição o usuário é lido do banco, então desativar uma conta ou mudar seu perfil vale na hora.

O primeiro administrador é criado por `python -m app.criar_admin`. Os demais, por `POST /auth/usuarios`, só para administradores. Senhas são guardadas com Argon2.

## Permissões

| Recurso | Administrador | Diretor de Escola | Coordenador de Logística |
| --- | --- | --- | --- |
| Usuários | tudo | não | não |
| Polos e escolas | tudo | leitura | leitura |
| Turmas | tudo | tudo, na própria escola | leitura |
| Professores | tudo | tudo, na própria escola | não |
| Estudantes | tudo | criar já com matrícula na própria escola; ler e alterar os da própria escola, exceto a parada | leitura |
| Matrículas e frequência | tudo | tudo, na própria escola | não |
| Paradas e rotas | tudo | leitura | tudo |

Um estudante é da escola em que tem matrícula ativa.

## Regras do diretor

- Matricula apenas quem já passou pela própria escola. Estudante novo entra por `POST /estudantes` com o campo `matricula`, na mesma transação.
- Transfere apenas entre turmas da própria escola. Transferência entre escolas cabe ao administrador.
- Para um estudante fora do escopo, a resposta é a mesma de um id inexistente, para não revelar quais estudantes existem.

## Proteção do login

Depois de 10 falhas seguidas para o mesmo e-mail e IP, novas tentativas recebem 429 por 15 minutos. A contagem fica em memória, por processo: se a API rodar com vários workers, mover o limite para o proxy reverso.
