# Modelo de dados

Definido em `backend/app/models.py`. Geometrias usam SRID 4326 (WGS 84), com índice GiST.

```mermaid
erDiagram
    POLO ||--o{ ESCOLA : agrupa
    ESCOLA ||--o{ TURMA : oferece
    ESCOLA ||--o{ PROFESSOR : lota
    ESCOLA ||--o{ USUARIO : "diretor de"
    TURMA ||--o{ MATRICULA : recebe
    ESTUDANTE ||--o{ MATRICULA : possui
    MATRICULA ||--o{ FREQUENCIA : registra
    PARADA ||--o{ ESTUDANTE : atende
    ROTA ||--o{ ROTA_PARADA : percorre
    PARADA ||--o{ ROTA_PARADA : compoe

    POLO { int id PK
        string nome UK
        multipolygon area }
    ESCOLA { int id PK
        string nome
        string codigo_inep UK
        string endereco
        int polo_id FK
        point localizacao }
    TURMA { int id PK
        int escola_id FK
        string nome
        string serie
        enum turno
        int ano_letivo }
    ESTUDANTE { int id PK
        string nome
        date data_nascimento
        string nome_responsavel
        point localizacao
        int parada_id FK }
    PROFESSOR { int id PK
        string nome
        string email UK
        int escola_id FK }
    MATRICULA { int id PK
        int estudante_id FK
        int turma_id FK
        date data_inicio
        date data_fim
        enum status }
    FREQUENCIA { int id PK
        int matricula_id FK
        date data
        bool presente }
    PARADA { int id PK
        string nome
        point localizacao }
    ROTA { int id PK
        string nome UK
        linestring trajeto
        float distancia_m }
    ROTA_PARADA { int rota_id PK
        int parada_id PK
        int ordem }
    USUARIO { int id PK
        string nome
        string email UK
        string senha_hash
        enum perfil
        int escola_id FK
        bool ativo }
```

## Decisões

- **Matrícula guarda o histórico.** Transferir encerra o vínculo atual (`transferida`) e cria outro. Um índice único parcial impede dois vínculos ativos para o mesmo estudante.
- **Frequência é por matrícula e por dia,** com um registro único para cada par. Assim a falta fica ligada à turma e à escola em que o estudante estava naquele dia.
- **Polo tem área opcional.** O vínculo da escola é por `polo_id`; a área permite consultas espaciais como `ST_Contains`.
- **Distâncias em metros** são calculadas convertendo para `geography`, porque a geometria em SRID 4326 mede em graus.
- **Trajeto da rota** é a linha reta entre as paradas, na ordem cadastrada. Não segue as ruas: isso exigiria um serviço de roteamento, fora do escopo atual.
- **Dados pessoais mínimos.** Os estudantes são, em geral, menores de idade, por isso não há CPF, e a localização da residência é opcional.
- **Fora do escopo:** merenda, estoque e US02, conforme o quadro.
