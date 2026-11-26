# Dados de crianças e LGPD

O EducaMobile guarda dados de menores de idade (LGPD, art. 14): só o necessário para o transporte, por tempo limitado e com registro de quem vê o quê.

## O que é guardado

| Dado | Para quê | Por quanto tempo | Quem vê |
| --- | --- | --- | --- |
| Nome, data de nascimento, escola e turno do estudante | Montar a lista da viagem | Enquanto o cadastro existir | Gestão. Motorista e monitor veem só nome, foto e parada, e só da própria viagem, no dia |
| Foto | Reconhecer a criança no embarque | Enquanto o cadastro existir | Gestão, equipe da viagem e a família (por URL assinada de 5 minutos). Os metadados (EXIF, GPS) são descartados no envio |
| Observações de cuidado (alergia, necessidade especial) | Segurança da criança | Enquanto o cadastro existir | Gestão e equipe da viagem. Nunca o responsável de outra criança |
| Endereço e localização da casa | **Não são guardados**: a parada basta | n/a | n/a |
| Vínculo e consentimento do responsável | Provar quem pode acompanhar a criança | Enquanto o vínculo existir | Gestão e o próprio responsável |
| Posições brutas do ônibus | Percurso, previsão e investigação de ocorrência | **90 dias** | Gestão e equipe da viagem. O responsável só vê o ônibus enquanto o filho está nele |
| Viagens, lista do motorista, eventos de embarque, alertas, avisos e ausências | Histórico do transporte e relatórios | **365 dias** (a confirmar com a secretaria) | Gestão |
| Registro de auditoria (login, consulta à posição, exportações, correções) | Responder "quem viu ou mudou isso" | **730 dias** | Só o administrador (`GET /auditoria`) |
| Sessões (aparelhos conectados) | Manter o login | Apagadas 30 dias depois de expirar ou ser revogadas | O próprio usuário (`GET /auth/sessoes`) |

Os prazos são valores da tabela `configuracao` (`retencao_posicoes_dias`, `retencao_dados_dias`, `retencao_auditoria_dias`) e podem mudar sem novo deploy. O worker apaga o que passou do prazo uma vez por hora.

## Consentimento

O responsável só enxerga o filho depois de aceitar o termo (`POST /responsavel/filhos/{id}/consentimento`), e a data e a versão aceitas ficam registradas. Quando a versão do termo muda (`VERSAO_TERMO_CONSENTIMENTO`), todo consentimento anterior deixa de valer e o responsável precisa aceitar de novo para voltar a ver o filho, receber avisos e acompanhar o ônibus.

## Quem viu o quê

Cada consulta do responsável à posição do ônibus, cada exportação de relatório, cada correção de registro da viagem, cada login e cada troca de senha entram na auditoria, com autor, IP e hora. Senhas e tokens nunca entram. Quem consulta a auditoria também deixa registro.

## O que ainda depende de decisão

- Confirmar com a secretaria o prazo de 365 dias para viagens e eventos (issue #25).
- Definir se a rotina de exclusão de um estudante (pedido do responsável) apaga também o histórico de viagens ou o anonimiza.
