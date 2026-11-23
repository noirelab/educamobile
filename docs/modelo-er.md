# Modelo de dados

Definido em `backend/app/models.py`. Geometrias usam SRID 4326 (WGS 84), com índice GiST. Este é o estado depois da etapa A da reformulação (ver `docs/reformulacao/README.md`); as tabelas de viagem, embarque e posição entram nas etapas B a D.

```mermaid
erDiagram
    PARADA ||--o{ ESTUDANTE : atende
    ROTA ||--o{ ROTA_PARADA : percorre
    PARADA ||--o{ ROTA_PARADA : compoe
    USUARIO ||--o{ SESSAO : "tem aparelhos"
    USUARIO ||--o{ RESPONSAVEL_ESTUDANTE : "responsavel por"
    ESTUDANTE ||--o{ RESPONSAVEL_ESTUDANTE : "tem responsavel"
    USUARIO ||--o{ AUDITORIA : "autor de"

    ESCOLA { int id PK
        string nome
        string codigo_inep UK
        string endereco
        point localizacao }
    ESTUDANTE { int id PK
        string nome
        date data_nascimento
        string nome_responsavel
        point localizacao
        int parada_id FK }
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
        bool ativo
        timestamptz sessoes_validas_desde }
    SESSAO { int id PK
        int usuario_id FK
        string token_hash UK
        timestamptz expira_em
        timestamptz revogada_em
        int substituida_por_id FK }
    RESPONSAVEL_ESTUDANTE { int responsavel_id PK
        int estudante_id PK
        string parentesco
        bool principal
        timestamptz consentimento_em
        string consentimento_versao }
    AUDITORIA { int id PK
        timestamptz em
        int usuario_id FK
        string acao
        string recurso
        jsonb detalhes }
```

## Perfis

`admin`, `gestor`, `motorista`, `monitor` e `responsavel`. Só `admin` e `gestor` são internos (`PERFIS_INTERNOS`) e enxergam os cadastros. Os demais acessam apenas o que um vínculo libera (filho, viagem escalada).

## Decisões

- **Distâncias em metros** são calculadas convertendo para `geography`, porque a geometria em SRID 4326 mede em graus.
- **Trajeto da rota** é a linha reta entre as paradas, na ordem cadastrada. Não segue as ruas: isso exigiria um serviço de roteamento.
- **Acesso por vínculo.** O perfil diz o que a pessoa é; o vínculo diz quais crianças ela pode ver. O responsável só vê o filho depois de registrar o consentimento (LGPD, art. 14).
- **Sessões por aparelho.** O refresh token é guardado só como hash e troca a cada uso; reuso de um token já trocado revoga todas as sessões da pessoa.
- **Auditoria só de inclusão,** sem senha nem token.
- **Dados pessoais mínimos.** Os estudantes são menores de idade: não há CPF, e a localização da residência é opcional.
- **Removidos na etapa A:** polos, turmas, professores, matrículas, transferências e frequência, e os perfis `diretor` e `coordenador`.
