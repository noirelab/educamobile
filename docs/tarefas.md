# Tarefas: EducaMobile Smart City

Extraído do [quadro no Trello](https://trello.com/b/nyeQ6Iqt/educamobile-smart-city-kanban) em 01/11/2026. O Trello continua sendo a fonte oficial do andamento.

Projeto Integrador II (UTFPR). Escopo exclui integralmente merenda/estoque/US02. Datas de entrega em branco: prazo final da disciplina não informado.

## Regras do quadro

- Definition of Done: critérios de aceite atendidos; implementação revisada; testes pertinentes executados; documentação atualizada; sem bloqueios conhecidos.
- WIP: Em Desenvolvimento até 3 cartões por pessoa; Code Review / Testes até 4 cartões no total.
- Convenção: [Área] Ação, título curto e objetivo.
- Fluxo: Backlog → A Fazer → Em Desenvolvimento → Code Review / Testes → Concluído.
- Mover de coluna somente quando a etapa anterior estiver concluída.

## Resumo

| Coluna | Tarefas |
| --- | --- |
| Backlog | 25 |
| A Fazer | 8 |
| Em Desenvolvimento | 0 |
| Code Review / Testes | 0 |
| Concluído | 0 |
| **Total** | **33** |

## Backlog (25)

### [Backend] Implementar autenticação JWT e perfis

Etiquetas: MVP, Backend, Sprint 2 (Operacional ERP e Rotas). [Abrir no Trello](https://trello.com/c/frcuSPfS)

Implementar autenticação JWT e autorização para Administrador da Secretaria, Diretor de Escola e Coordenador de Logística.

- [ ] Implementar emissão e validação de JWT
- [ ] Definir perfis e permissões
- [ ] Proteger endpoints por perfil
- [ ] Documentar fluxo de autenticação

### [Backend] Implementar CRUD de professores

Etiquetas: MVP, Backend, Sprint 2 (Operacional ERP e Rotas). [Abrir no Trello](https://trello.com/c/kcvJMjmB)

Disponibilizar operações CRUD de professores.

- [ ] Criar schema e persistência
- [ ] Implementar endpoints CRUD
- [ ] Validar dados
- [ ] Documentar endpoints

### [Backend] Implementar matrículas e transferências

Etiquetas: MVP, Backend, Sprint 2 (Operacional ERP e Rotas). [Abrir no Trello](https://trello.com/c/J8PNSrMV)

Registrar matrículas e transferências de estudantes entre turmas ou escolas.

- [ ] Modelar matrícula e histórico
- [ ] Implementar operações de matrícula
- [ ] Implementar transferência
- [ ] Validar consistência dos vínculos

### [Backend] Registrar frequência dos alunos

Etiquetas: MVP, Backend, Sprint 2 (Operacional ERP e Rotas), Contingência. [Abrir no Trello](https://trello.com/c/RjjoEENp)

Registrar frequência individual como base para indicadores e mapa de infrequência.

- [ ] Modelar registro de frequência
- [ ] Implementar gravação e consulta
- [ ] Validar período e estudante
- [ ] Disponibilizar dados para agregação

### [Backend] Cadastrar paradas e associar estudantes

Etiquetas: MVP, Backend, Sprint 2 (Operacional ERP e Rotas), Mapas/Geo. [Abrir no Trello](https://trello.com/c/ua95tRIU)

Cadastrar paradas de embarque georreferenciadas e associar estudantes.

- [ ] Modelar parada geográfica
- [ ] Implementar cadastro e consulta
- [ ] Associar estudantes às paradas
- [ ] Validar coordenadas e vínculos

### [Banco/PostGIS] Calcular geometria de rotas de ônibus

Etiquetas: MVP, Sprint 2 (Operacional ERP e Rotas), Banco/PostGIS, Mapas/Geo. [Abrir no Trello](https://trello.com/c/QqF7qXHl)

Cadastrar rotas de ônibus e calcular/consultar geometria dos pontos da rota usando PostGIS.

- [ ] Modelar rota e seus pontos
- [ ] Persistir geometria no PostGIS
- [ ] Implementar consulta espacial
- [ ] Validar geometria e sequência dos pontos

### [Frontend] Criar telas administrativas e formulários

Etiquetas: MVP, Sprint 2 (Operacional ERP e Rotas), Frontend. [Abrir no Trello](https://trello.com/c/8sc0B0RQ)

Criar telas administrativas e formulários para as operações do MVP.

- [ ] Implementar telas previstas
- [ ] Criar formulários e validação
- [ ] Exibir estados de erro e sucesso
- [ ] Verificar responsividade

### [Frontend] Integrar interface com a API

Etiquetas: MVP, Sprint 2 (Operacional ERP e Rotas), Frontend. [Abrir no Trello](https://trello.com/c/wQAivNXX)

Consumir endpoints do backend pela interface e tratar erros de comunicação e validação.

- [ ] Configurar cliente HTTP
- [ ] Conectar telas aos endpoints
- [ ] Tratar erros e carregamento
- [ ] Validar fluxos integrados

### [Documentação] Avaliar escopo e comunicar contingência

Etiquetas: MVP, Sprint 2 (Operacional ERP e Rotas), Documentação. [Abrir no Trello](https://trello.com/c/ZmmuN4fq)

Na Sprint 2, avaliar viabilidade do escopo. Se necessário, comunicar formalmente à banca a redução para Dashboard Analítico, atualizar o Trello e registrar justificativa.

- [ ] Avaliar prazo e capacidade restante
- [ ] Decidir se ativa a contingência
- [ ] Se aplicável, comunicar decisão à banca
- [ ] Atualizar quadro e registrar justificativa

### [Mapas/Geo] Exibir distribuição espacial e infrequência por polo

Etiquetas: MVP, Frontend, Mapas/Geo, Contingência, Sprint 3 (Dashboard e Homologação). [Abrir no Trello](https://trello.com/c/fuN6uEkS)

Criar mapa temático Leaflet com distribuição espacial de estudantes e taxa de infrequência por polo de ensino.

- [ ] Preparar dados agregados por polo
- [ ] Renderizar camada de estudantes no Leaflet
- [ ] Exibir taxa de infrequência por polo
- [ ] Validar legenda e interação do mapa

### [Mapas/Geo] Criar mapa de calor de infrequência (US01)

Etiquetas: MVP, Frontend, Mapas/Geo, Contingência, Sprint 3 (Dashboard e Homologação). [Abrir no Trello](https://trello.com/c/Sfc1FKLv)

Exibir mapa de calor das unidades com picos de infrequência para apoiar ações de busca ativa.

- [ ] Definir agregação da infrequência
- [ ] Renderizar mapa de calor
- [ ] Indicar unidades com maior incidência
- [ ] Validar leitura e filtros do mapa

### [Frontend] Criar gráficos agregados com Recharts

Etiquetas: MVP, Frontend, Contingência, Sprint 3 (Dashboard e Homologação). [Abrir no Trello](https://trello.com/c/H6dnoTz1)

Exibir gráficos agregados de frequência, evasão e desempenho no dashboard.

- [ ] Definir séries e agregações disponíveis
- [ ] Implementar gráficos Recharts
- [ ] Exibir rótulos e estados sem dados
- [ ] Validar consistência dos indicadores

### [Mapas/Geo] Visualizar rotas e paradas no mapa (US03)

Etiquetas: MVP, Frontend, Mapas/Geo, Sprint 3 (Dashboard e Homologação). [Abrir no Trello](https://trello.com/c/AMpB84P2)

Exibir rotas de transporte escolar e paradas de embarque no mapa, apoiando a visualização da US03.

- [ ] Carregar geometria das rotas
- [ ] Exibir paradas associadas
- [ ] Distinguir rotas e pontos visualmente
- [ ] Validar visualização no mapa

### [Frontend] Adicionar filtros e relatórios exportáveis

Etiquetas: MVP, Frontend, Sprint 3 (Dashboard e Homologação), Contingência. [Abrir no Trello](https://trello.com/c/VWJ3a1VL)

Disponibilizar filtros de análise e exportação de relatórios do dashboard.

- [ ] Definir filtros necessários
- [ ] Aplicar filtros aos indicadores e mapas
- [ ] Implementar exportação de relatório
- [ ] Validar conteúdo exportado

### [Testes] Criar testes unitários pytest

Etiquetas: MVP, Backend, Sprint 3 (Dashboard e Homologação), Testes. [Abrir no Trello](https://trello.com/c/VVozveEd)

Testar schemas Pydantic e regras de negócio do backend com pytest.

- [ ] Cobrir validação dos schemas Pydantic
- [ ] Cobrir regras de negócio
- [ ] Executar suíte pytest
- [ ] Corrigir falhas identificadas

### [Testes] Integrar com banco e consultas PostGIS

Etiquetas: MVP, Sprint 3 (Dashboard e Homologação), Banco/PostGIS, Testes. [Abrir no Trello](https://trello.com/c/sEmoN0Be)

Validar integração, integridade referencial e consultas espaciais ST_Distance e ST_Contains.

- [ ] Preparar banco de teste
- [ ] Validar integridade referencial
- [ ] Testar ST_Distance
- [ ] Testar ST_Contains

### [Testes] Validar usabilidade e responsividade

Etiquetas: MVP, Frontend, Sprint 3 (Dashboard e Homologação), Testes. [Abrir no Trello](https://trello.com/c/qTSmiTVO)

Verificar design system, responsividade, consistência dos mapas e filtros.

- [ ] Revisar consistência visual
- [ ] Validar responsividade em telas-alvo
- [ ] Verificar mapas e filtros
- [ ] Registrar ajustes necessários

### [Documentação] Revisar solução com feedback docente

Etiquetas: MVP, Sprint 3 (Dashboard e Homologação), Documentação. [Abrir no Trello](https://trello.com/c/LG75O4wR)

Aplicar revisão final do projeto com base nos feedbacks docentes.

- [ ] Consolidar feedbacks recebidos
- [ ] Priorizar ajustes finais
- [ ] Aplicar alterações acordadas
- [ ] Registrar revisão concluída

### [Documentação] Preparar documentação final e apresentação

Etiquetas: MVP, Sprint 3 (Dashboard e Homologação), Documentação. [Abrir no Trello](https://trello.com/c/PrZWnRQG)

Concluir documentação do projeto e preparar apresentação para a banca.

- [ ] Consolidar documentação técnica
- [ ] Preparar roteiro e materiais de apresentação
- [ ] Revisar conteúdo com a equipe
- [ ] Preparar demonstração do sistema

### [Mapas/Geo] Correlacionar notas/IDEB e vulnerabilidade (IBGE)

Etiquetas: Mapas/Geo, Desejável. [Abrir no Trello](https://trello.com/c/gJAYD30s)

Explorar correlação entre notas/IDEB e vulnerabilidade socioeconômica do bairro usando dados IBGE.

- [ ] Identificar dados necessários
- [ ] Definir unidade geográfica de correlação
- [ ] Preparar análise e visualização

### [Backend] Projetar déficit estrutural de vagas

Etiquetas: Backend, Desejável. [Abrir no Trello](https://trello.com/c/MJehKtbk)

Estimar projeção de déficit estrutural de vagas na rede escolar.

- [ ] Definir variáveis de projeção
- [ ] Identificar dados de entrada
- [ ] Definir forma de apresentação

### [Frontend] Criar portal de dados abertos

Etiquetas: Frontend, Desejável. [Abrir no Trello](https://trello.com/c/kmh4vBF2)

Disponibilizar portal de dados abertos para transparência pública.

- [ ] Definir dados públicos a disponibilizar
- [ ] Definir formato de consulta e acesso
- [ ] Preparar interface do portal

### [Backend] Criar canal de notificação aos responsáveis

Etiquetas: Backend, Desejável. [Abrir no Trello](https://trello.com/c/XMR7Aszk)

Criar canal de notificação aos responsáveis dos estudantes.

- [ ] Definir eventos de notificação
- [ ] Definir canal e conteúdo
- [ ] Implementar envio e registro

### [Backend] Gerir RH e patrimônio predial

Etiquetas: Backend, Desejável. [Abrir no Trello](https://trello.com/c/CTio0AAN)

Backlog de menor prioridade para escalonamento de recursos humanos e controle de patrimônio predial.

- [ ] Levantar dados e fluxos de RH
- [ ] Levantar dados de patrimônio predial
- [ ] Priorizar implementação futura

### [Mapas/Geo] Importar dados estáticos para o dashboard

Etiquetas: MVP, Backend, Mapas/Geo, Contingência. [Abrir no Trello](https://trello.com/c/0jt2Zufj)

Permitir importação manual de dados estáticos ou semiestáticos de IBGE/escolas para manter o Dashboard Analítico em caso de contingência.

- [ ] Definir formato de arquivo aceito
- [ ] Validar estrutura e campos importados
- [ ] Importar dados de escolas e IBGE
- [ ] Exibir dados carregados no dashboard

## A Fazer (8)

### [Banco/PostGIS] Modelar banco PostgreSQL com PostGIS

Etiquetas: Sprint 1 (Fundação e Modelagem), Banco/PostGIS, MVP. [Abrir no Trello](https://trello.com/c/o2zqP6hB)

Criar modelo relacional e diagrama ER para escolas georreferenciadas, turmas, estudantes, professores, matrículas e frequência.

- [ ] Definir entidades e atributos
- [ ] Definir chaves e integridade referencial
- [ ] Modelar campos geográficos e índices PostGIS
- [ ] Gerar diagrama ER e registrar decisões

### [Infra/DevOps] Configurar ambiente Docker e build

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Infra/DevOps. [Abrir no Trello](https://trello.com/c/khONmucU)

Preparar ambiente conteinerizado para Postgres/PostGIS, FastAPI e Vite, com pipeline de build.

- [ ] Criar Docker Compose dos serviços
- [ ] Configurar variáveis e volumes locais
- [ ] Configurar build do backend e frontend
- [ ] Documentar inicialização do ambiente

### [Backend] Estruturar projeto FastAPI

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Backend. [Abrir no Trello](https://trello.com/c/JLH40zMV)

Criar estrutura inicial do backend, configuração, modelos Pydantic e documentação Swagger/OpenAPI.

- [ ] Definir organização de pastas
- [ ] Configurar aplicação FastAPI
- [ ] Adicionar schemas Pydantic iniciais
- [ ] Validar documentação Swagger/OpenAPI

### [Frontend] Estruturar React, Vite e Tailwind

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Frontend. [Abrir no Trello](https://trello.com/c/TK9uaQvZ)

Preparar aplicação React com Vite e Tailwind, rotas e layout base.

- [ ] Inicializar projeto React + Vite
- [ ] Configurar Tailwind CSS
- [ ] Definir rotas iniciais
- [ ] Criar layout base responsivo

### [Backend] Implementar CRUD de escolas

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Backend. [Abrir no Trello](https://trello.com/c/SExWpyBA)

Disponibilizar operações de cadastro, consulta, atualização e remoção de escolas, incluindo localização geográfica.

- [ ] Criar schema e persistência
- [ ] Implementar endpoints CRUD
- [ ] Validar dados e respostas
- [ ] Documentar endpoints na API

### [Backend] Implementar CRUD de turmas

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Backend. [Abrir no Trello](https://trello.com/c/x3s9HSw4)

Disponibilizar operações CRUD de turmas vinculadas às escolas.

- [ ] Criar schema e persistência
- [ ] Implementar endpoints CRUD
- [ ] Validar vínculo com escola
- [ ] Documentar endpoints na API

### [Backend] Implementar CRUD de estudantes

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Backend. [Abrir no Trello](https://trello.com/c/uiUbIwVz)

Disponibilizar operações CRUD de estudantes para uso pelo ERP escolar.

- [ ] Criar schema e persistência
- [ ] Implementar endpoints CRUD
- [ ] Implementar endpoints CRUD
- [ ] Validar dados obrigatórios
- [ ] Documentar endpoints na API

### [Documentação] Refinar critérios de aceite US01 e US03

Etiquetas: Sprint 1 (Fundação e Modelagem), MVP, Documentação. [Abrir no Trello](https://trello.com/c/RHAuXV9R)

Registrar formalmente no Trello os critérios de aceite das histórias US01 e US03.

- [ ] Definir critérios observáveis para US01
- [ ] Definir critérios observáveis para US03
- [ ] Registrar dependências e exemplos de validação
- [ ] Revisar critérios com a equipe
