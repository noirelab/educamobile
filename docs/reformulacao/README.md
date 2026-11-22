# Reformulação: transporte escolar seguro

Em 21/11/2026 o escopo do EducaMobile mudou. O sistema deixa de ser um ERP da rede escolar e passa a cuidar só da segurança da criança no transporte: do embarque no ônibus até a chegada à escola.

- O responsável acompanha o ônibus do filho e é avisado do embarque, da falta e da chegada.
- O motorista recebe a lista do dia e confirma, parada por parada, quem subiu e quem faltou.
- O gestor de transporte acompanha todos os ônibus e recebe alertas.

Polos, turmas, professores, matrículas, frequência e infrequência foram descartados.

O relatório completo está em [`reformulacao-backend.pdf`](reformulacao-backend.pdf). Este README explica **por que** cada decisão foi tomada, para que o grupo possa discordar com base no mesmo raciocínio.

## Como as decisões foram tomadas

O ponto de partida foi o código no commit `cc82376` e o resumo do backend de novembro. Cada decisão passou por três perguntas, nesta ordem:

1. **Isso protege a criança?** Se uma escolha deixa uma criança sem registro, sem aviso ou exposta a quem não deveria vê-la, ela perde, mesmo que seja mais simples.
2. **Dá para fazer com o que já existe?** O que já está pronto e testado (login, PostGIS, CI) tem prioridade sobre trocar de tecnologia.
3. **Cabe no prazo da disciplina?** O que é caro ou depende de terceiros (SMS, roteamento por ruas, NFC) fica preparado no modelo e sai da primeira entrega.

### Manter a base técnica

FastAPI, PostgreSQL com PostGIS, Alembic, Argon2, JWT, Docker e CI continuam. São 185 testes passando e um pipeline que já pegou erros reais. Trocar de stack não traria nenhum ganho de segurança e custaria semanas.

### Apagar os módulos de gestão escolar

Polos, turmas, professores, matrículas e frequência somam 26 das 55 rotas. Mantê-los "por via das dúvidas" deixaria mais superfície de ataque com dados de menores e mais código para revisar. O único padrão reaproveitado é o da gravação idempotente da frequência (`INSERT ... ON CONFLICT`), que serve para os eventos de embarque.

### Recomeçar as migrações

Não há dados reais em produção. Uma migração inicial nova é mais fácil de revisar do que uma sequência que cria e depois apaga tabelas. Enquanto a etapa A não termina, a branch usa uma migração incremental para não quebrar o que existe.

### Separar o planejado do realizado

`Rota` e `Inscricao` descrevem o que deveria acontecer. `Viagem` e `ViagemAluno` registram o que aconteceu. A lista do motorista é uma cópia tirada no início da viagem. Sem isso, uma edição do gestor às 7h mudaria a lista nas mãos do motorista no meio do trajeto, e uma criança poderia sumir da lista sem ninguém perceber.

### Eventos imutáveis

Cada toque do motorista vira um registro que não se apaga; correção é um novo registro, com motivo e autor. Num incidente, a pergunta "quem marcou que essa criança desceu, e quando?" precisa ter resposta.

### Acesso por vínculo, não só por perfil

O perfil diz o que a pessoa é; o vínculo diz quais crianças ela pode ver. Um responsável só vê os filhos ligados a ele; um motorista só vê as viagens em que está escalado, no dia. Perfil sozinho é pouco: todo responsável tem o mesmo perfil.

Ao revisar o código atual, isso se confirmou na prática: as rotas de leitura aceitavam qualquer usuário logado. Com perfis novos, um pai logado conseguiria listar todos os estudantes. A preparação de segurança desta branch corrige isso antes que os perfis novos sejam usados (ver abaixo).

### Posição do ônibus só durante a viagem do filho

Mostrar o ônibus o tempo todo seria mostrar onde estão as outras crianças. A janela vai do início da viagem até o desembarque do filho.

### Responsável entra por convite

Com cadastro aberto, qualquer pessoa poderia se dizer mãe de uma criança. O gestor cadastra, a escola confere o documento e o convite fecha o vínculo.

### Conclusão da viagem bloqueada com aluno a bordo

Este é o ponto central do produto. Há casos reais de crianças esquecidas dentro de veículos escolares. A API não deixa concluir a viagem enquanto algum aluno estiver como "embarcou" e exige a confirmação de ônibus vazio.

### Redis e worker

As regras de atraso, desvio e falta de sinal dependem do tempo passar, não de uma requisição chegar, então precisam de um processo separado. O Redis resolve três problemas ao mesmo tempo: guarda a última posição de cada ônibus, distribui as mensagens entre processos da API e substitui o contador de tentativas de login, que hoje fica na memória de um processo só.

### App do motorista nativo

O navegador do celular não envia GPS de forma confiável com a tela apagada, principalmente no iOS. Isso não muda o backend, mas muda o trabalho do frontend, e por isso entrou no relatório.

### O que ficou para o grupo decidir

Viagem de volta, monitor no ônibus, forma de confirmar embarque, confirmação pela escola, pais sem smartphone, prazo de guarda dos dados e validação do responsável. Cada uma tem uma recomendação no relatório (seção 11) e uma issue própria no GitHub.

## O que esta branch já prepara

Foco em segurança. O domínio novo (viagens, embarques, posições) fica para as próximas etapas.

| Mudança | Por quê |
| --- | --- |
| Perfis `gestor`, `motorista`, `monitor` e `responsavel` | Base para o controle de acesso novo. `diretor` e `coordenador` continuam até a etapa A. |
| Rotas de leitura fechadas para os perfis novos | Corrige a falha descrita acima. Um teste percorre todas as rotas da API e confirma que responsável, motorista e monitor recebem 403 em tudo que não foi liberado para eles. |
| Gestor com o mesmo acesso do coordenador | Transição: o coordenador vira gestor de transporte. |
| Token de acesso de 15 min e refresh token | Desativar um motorista ou trocar a senha passa a derrubar as sessões. O refresh token é aleatório, guardado só como hash, e troca a cada uso. Reuso de um token já trocado revoga todas as sessões da pessoa, porque indica roubo. |
| Logout, logout de todos os aparelhos e troca de senha | Um celular perdido não pode continuar logado. |
| Vínculo responsável–estudante com consentimento | LGPD, art. 14: data e versão do termo aceito ficam registradas. O responsável só vê o filho depois de aceitar. |
| Auditoria | Login, falha de login, troca de senha, revogação de sessão e criação de usuário ficam registrados com autor, IP e hora. Senhas e tokens nunca entram no registro. |
| Limite de tentativas isolado em `app/limite.py` | A versão em memória continua; a de Redis entra sem mudar as rotas. |
| Cabeçalhos de segurança e configuração de produção | `nosniff`, `DENY` para frames, sem cache nas respostas da API, HSTS e Swagger desligado quando `AMBIENTE=producao`. |

## Próximos passos

As issues no GitHub seguem as etapas A a F do relatório.
