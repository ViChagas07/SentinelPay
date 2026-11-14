# SPEC 0016 - Notificacoes (Central, e-mail, SMS e WhatsApp)

## Objetivo

Entregar a Central de Notificacoes por API e a entrega externa por e-mail, SMS e WhatsApp,
com consentimento explicito, conteudo minimo e isolamento de falhas. A Central e a fonte de
verdade do usuario; os canais externos sao derivados dela.

## Escopo

- Tabelas `notifications` (evolucao da P13/P14), `notification_preferences` e
  `notification_deliveries`.
- API de listagem com filtros e cursor, contador de nao lidas, marcar uma/todas como lidas e
  apagar, sempre filtrada pelo dono do JWT.
- Preferencias por canal e idioma (`preferred_locale`), com opt-in explicito para SMS e
  WhatsApp e telefone E.164.
- Portas `EmailPort`, `SmsPort` e `WhatsAppPort`; adaptador SMTP real (Mailpit no local) e
  adaptadores `console` para SMS/WhatsApp.
- Templates i18n em pt-BR, en, fr, ja, es, de, ar, ko e zh, com fallback para en.
- Tarefa Celery de entrega na fila `notifications`, retry com backoff, idempotencia por
  `(notificacao, canal)` e falha isolada por canal.
- Entrega de lembretes de vencimento criados na P14 e notificacao de vencido.

## Fora de escopo

- Escolher ou contratar provedor de SMS/WhatsApp, chaves reais ou templates aprovados.
- Tela/frontend, WebSocket, e-mail marketing, push.
- Alterar a fonte unica do score ou o conteudo do relatorio.

## Tipos de notificacao

| Tipo | Quando nasce |
| --- | --- |
| `analysis_completed` | analise concluida sem risco alto e sem recibo |
| `high_risk_detected` | analise concluida com banda `high` |
| `receipt_analyzed` | recibo analisado com risco baixo/atencao |
| `payable_due_soon` | lembrete de vencimento com antecedencia > 0 |
| `payable_due_today` | lembrete no dia do vencimento |
| `payable_overdue` | conta marcada como vencida pela tarefa agendada |
| `payable_due_reminder` | legado da P14 (aceito apenas para leitura) |

Uma analise gera **uma** notificacao, escolhendo o tipo por prioridade:
`high_risk_detected` > `receipt_analyzed` > `analysis_completed`.

## Regras de criacao

1. O item da Central sempre existe, independentemente de canais externos.
2. O status da notificacao nasce `pending`; a Central ignora `status` para listagem e usa
   `read_at` para lidas/nao lidas.
3. Lembretes usam `reminder_preferences` (P14) para antecedencias e horario local do usuario.
   Cada `(payable, due_date, offset)` gera **uma** notificacao `in_app`, com payload minimo:
   `payable_id`, `due_date`, `offset_days` e `type`.
4. `payable_overdue` e unico por payable (indice parcial unico); a tarefa de vencimento atualiza
   o status e cria a notificacao na mesma transacao.
5. Pagar, descartar ou reajustar o vencimento cancela lembretes pendentes antigos; a entrega
   pula notificacoes canceladas.

## Consentimento e protecao de dados

- E-mail: habilitado por padrao para o endereco da conta (transacional). O destino e o e-mail
  do usuario, nunca um e-mail arbitrario vindo do corpo.
- SMS e WhatsApp: desabilitados por padrao. So enviam com `enabled=true`, `consented_at`
  preenchido e telefone no formato E.164 (`+` e 8 a 15 digitos).
- Telefones de SMS/WhatsApp sao cifrados em repouso (AES-GCM com chave derivada de
  `SECURITY_HASH_SECRET`) e nunca aparecem em logs, erros ou respostas completas.
- Logs de adaptadores `console` registram apenas que o envio ocorreria, sem destino nem corpo.
- Conteudo externo e minimo: sem valor, nome, CPF/CNPJ, codigo de barras ou resultado
  detalhado. Exemplo SMS: "uma conta vence em 3 dias, abra o app".
- E-mail e telefone sao mascarados pelo filtro de PII existente.

## API

Todas as rotas exigem JWT e filtram `owner_id` do token.

- `GET /api/v1/notifications?type=&unread=&limit=&cursor=`
  - `type` repetivel; `unread=true|false`; ordem `created_at DESC, id DESC`.
  - cursor opaco `(created_at, id)`; limite 1..50.
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`
- `DELETE /api/v1/notifications/{id}`
- `GET /api/v1/notification-preferences`
- `PUT /api/v1/notification-preferences`
  - atualiza `enabled`, `destination` (SMS/WhatsApp), `consent` e `locale`.
  - habilidar SMS/WhatsApp sem `consent=true` ou sem E.164 retorna 422.
  - idioma fora da lista suportada retorna 422; idioma desconhecido ja armazenado cai em en
    na renderizacao.

IDOR: recurso de outro dono retorna 404 (mesmo codigo de inexistente).

## Entrega

- Portas: `EmailPort.send(to, subject, body)`, `SmsPort.send(to, body)`,
  `WhatsAppPort.send(to, body)`.
- SMTP real via `smtplib` em threadpool; Mailpit local em `SMTP_HOST=mailpit`,
  `SMTP_PORT=1025`.
- SMS/WhatsApp: adaptador `console` ate a escolha do provedor (ADR 0019).
- Fluxo da tarefa:
  1. carrega notificacao, usuario e preferencias;
  2. para cada canal externo, cria/reaproveita `notification_deliveries` unica por
     `(notification_id, channel)`;
  3. canal ja `sent`/`skipped` e ignorado (idempotencia);
  4. sem opt-in/consentimento/destino valido -> `skipped` com motivo seguro;
  5. renderiza template no `preferred_locale` do usuario;
  6. envia; sucesso -> `sent`; excecao -> `failed` com codigo seguro e `attempts += 1`;
  7. falha de um canal nao impede os demais;
  8. se restou falha e ha retry, a tarefa reagenda com backoff exponencial; na ultima
     tentativa, a notificacao vira `failed`.
- Falha na entrega nunca remove o item da Central.

## Criterios de aceite (viram testes)

1. Renderizacao nos 9 locales e fallback de locale desconhecido para en.
2. Vencimento em fuso diferente e virada de dia gera lembrete na hora local correta.
3. Tarefa executada duas vezes nao duplica entrega nem reenvia canal ja enviado.
4. Usuario B nao lista, le, apaga nem altera preferencias do usuario A (IDOR 404).
5. Risco alto nao cria payable nem lembrete de vencimento (P14) e cria apenas a notificacao
   `high_risk_detected` na Central.
6. Sem opt-in de SMS/WhatsApp, o adaptador nao e chamado e a entrega fica `skipped`.
7. Falha de SMS nao impede e-mail/WhatsApp nem a Central; retry reenvia apenas o canal falho.
8. Telefone e e-mail nao aparecem em logs; telefone e cifrado no banco.
9. Evento gera item na Central e e-mail no Mailpit; SMS/WhatsApp passam pelo console quando
   consentidos.

## Riscos e NAO VALIDADO

- Provedor real de SMS/WhatsApp, template aprovado do WhatsApp Business, cobertura, custo e
  entregabilidade real: NAO VALIDADOS (decisao pendente em ADR 0019).
- Entregabilidade real de e-mail (SPF/DKIM/bounce) e SMTP de producao: NAO VALIDADOS; o teste
  usa Mailpit.
- Politica antiabuso de envio (frequency cap por usuario) nao faz parte desta fase.
