# O que falta no backend para o frontend

Levantado em 02/11/2026, durante o planejamento do frontend. O frontend só consome a API que já existe. Nada desta lista é simulado ou calculado no navegador. Cada item fica fora do frontend até o backend entregar a rota.

## Usuários

Hoje existe só `POST /auth/usuarios`.

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| `GET /auth/usuarios` (listar, com filtro por perfil e escola) | Tabela de usuários | A tela de usuários tem só o formulário de criação |
| `GET /auth/usuarios/{id}` | Detalhe do usuário | Nenhum |
| `PUT` ou `PATCH /auth/usuarios/{id}` (nome, perfil, escola) | Editar usuário | Nenhum |
| Desativar e reativar conta (`ativo`) | Bloquear acesso sem apagar | Nenhum |
| Trocar a própria senha | Tela de perfil | Nenhum |

## Indicadores e gráficos

Hoje existe só a infrequência agregada, em `GET /frequencias/agregada`, por turma, escola ou polo.

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Série temporal da infrequência (por dia, semana ou mês) | Gráfico de linha no dashboard | Gráficos só comparam grupos dentro de um período |
| Evasão escolar | Gráfico de evasão (card Recharts) | Não exibido |
| Desempenho, notas ou IDEB | Gráfico de desempenho | Não exibido |
| Exportação de relatório pelo servidor | Botão de exportar | Sem exportação |

## Perfil coordenador de logística

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Acesso de leitura a `GET /frequencias/agregada` | Mapa de infrequência no dashboard | O dashboard do coordenador mostra só o transporte |

## Mapas

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Trajeto que segue as ruas | Desenho real da rota | Linha reta entre as paradas, como a API entrega |
| Otimização da ordem das paradas de uma rota (US03 pede "rotas otimizadas") | Botão "otimizar ordem" no editor de rota | Ordem definida manualmente pelo coordenador |
| Distribuição espacial agregada de estudantes por polo | Camada de estudantes no mapa | Camada não exibida |

## Listagens

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Total de registros nas listagens (cabeçalho ou campo `total`) | Paginação com número de páginas | Paginação só com "anterior" e "próxima", com `limit` e `offset` |
| Busca por texto (`q` ou `nome`) em polos, escolas, turmas, professores, estudantes, paradas e rotas | Campo de busca nas tabelas | Sem campo de busca. Só os filtros que a API já aceita |

## Filtros de indicadores

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Filtro `escola_id` (e `polo_id`) em `GET /frequencias/agregada` | Infrequência por turma no detalhe da escola, para o administrador | Bloco exibido só para o diretor, que já recebe só a própria escola |

## Matrículas

| Falta | Uso no frontend | Enquanto não existir |
| --- | --- | --- |
| Nome do estudante (e da turma) em `MatriculaLer`, ou `GET /turmas/{id}/estudantes` | Lista de matriculados da turma e chamada de frequência | Uma chamada `GET /estudantes/{id}` por matrícula listada |
| Filtros `turma_id` e `escola_id` em `GET /estudantes` | Filtrar estudantes por turma ou escola | Sem esses filtros na lista de estudantes |
| Turma e escola atuais em `EstudanteLer` | Colunas turma e escola na lista de estudantes | Lista sem essas colunas; aparecem só no detalhe, pelo histórico |

Observação: `GET /matriculas` usa `limite` e `deslocamento`, e as demais listas usam `limit` e `offset`. Padronizar ajudaria.
