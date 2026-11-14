# SPEC 0015: Recibos de consumo e vencimentos

## Objetivo
Analisar recibos/contas de consumo (energia, agua, gas, telefone etc.) pelo grafo da P11, extrair concessionaria, valor, vencimento, referencia e linha de 48 digitos, pontuar com as mesmas regras deterministicas/visuais/ML e, quando o risco permitir, registrar um `payable` e agendar lembretes. Sem lista de concessionarias escrita de memoria: a entidade nao e validada sem fonte.

## Escopo
- Tipo de documento `receipt` (upload, grafo, relatorio e API de analises).
- `payables` com status `pending_confirmation`, `pending`, `paid`, `overdue`, `dismissed`.
- Preferencias de lembrete por usuario e tarefas Celery de lembrete/atraso.
- Sem entrega de e-mail/SMS/WhatsApp (P15), sem frontend, sem tabela de concessionarias.

## Extracao do recibo
Campos (com confianca):
- **Linha de 48 digitos** (line) e, quando impresso, **codigo de 44 digitos** (barcode) sem os quatro DVs.
- **Concessionaria/emissor** por rotulos (`Concessionaria`, `Distribuidora`, `Prestadora`, `Companhia`, `Saneamento`, `Energia`); nao validada contra lista.
- **Valor** (R$) e **vencimento** (data), reaproveitando os parsers da P07.
- **Referencia** (mes/ano ou texto do periodo).
- Confianca baixa (<0,5) vira campo ilegivel, nao divergencia.

## Regras deterministicas (`receipt-v1`)
| Regra | Severidade | Peso | Condicao |
|---|---:|---:|---|
| `receipt_line_invalid` | critical | 60 | linha ausente, nao numerica ou != 48 digitos |
| `receipt_dv_invalid` | critical | 70 | algum bloco 11+DV nao casa com modulo 10 nem 11 |
| `receipt_barcode_mismatch` | critical | 70 | 44 digitos impressos != concatenacao dos 4 blocos da linha |
| `receipt_amount_inconsistent` | critical | 70 | dois ou mais valores impressos divergentes com confianca >= 0,8 |
| `receipt_due_date_inconsistent` | high | 30 | duas ou mais datas de vencimento divergentes ou vencimento anterior a referencia |
| `receipt_amount_missing` | high | 25 | valor nao extraido/ilegivel |
| `receipt_due_date_missing` | high | 25 | vencimento nao extraido/ilegivel |
| `receipt_issuer_missing` | medium | 10 | concessionaria nao extraida |
| `receipt_reference_missing` | low | 5 | referencia nao extraida |
| `receipt_field_illegible` | medium | 10 | algum campo obrigatorio com confianca < 0,5 |
| `receipt_dv_algorithm_not_validated` | info | 0 | DV casou com modulo 10 ou 11, mas o layout nao tem fonte |
| `receipt_issuer_not_validated` | info | 0 | nao ha lista/registro de concessionarias |

- Fonte de todas as regras: `knowledge/febraban/manual_febraban_v1.pdf` e `knowledge/faq/antifraud_faq.pdf` (48 digitos), com a ressalva de layout de arrecadacao **NAO VERIFICAVEL**.
- **NAO VALIDADO**: algoritmo oficial de DV de arrecadacao/48 digitos e validade da entidade concessionaria. O DV so e marcado invalido quando nao casa com nenhum dos dois algoritmos documentados para DAC (modulo 10/11), sem afirmar qual e o correto.
- O score usa o mesmo `FraudScoringService` (deterministico + ML + visao). O ML nao foi treinado com recibos; `is_boleto`/`is_payslip` ficam 0 e isso e **NAO VALIDADO**.

## Payables
- Criado apenas para `receipt` com valor > 0, vencimento e score terminal concluido.
- Politica: **Low -> `pending`**; **Attention -> `pending_confirmation`**; **High -> nao cria**.
- Injecao/guardrail de entrada detectada forca `pending_confirmation` (nunca `pending` automatico); risco High continua sem payable.
- `description` minima: concessionaria + referencia (truncada, sem PII); fallback `Conta de consumo`.
- Um payable por analise (`analysis_id` unico). Reentrega/duplicidade nao duplica.
- Valor em centavos e `due_date` em data civil; timestamps UTC.

## API (autenticada; dono do JWT)
### Payables
- `GET /api/v1/payables?status=&due_from=&due_to=&limit=&cursor=` — filtros opcionais, ordem por `due_date,id`, cursor opaco, uma query.
- `POST /api/v1/payables/{id}/confirm` — `pending_confirmation -> pending`; idempotente se ja `pending`.
- `POST /api/v1/payables/{id}/pay` — `pending|pending_confirmation|overdue -> paid`; idempotente se ja `paid`.
- `PATCH /api/v1/payables/{id}/due-date` — `{due_date}` em status nao final; cancela lembretes pendentes antigos.
- `POST /api/v1/payables/{id}/dismiss` — `pending|pending_confirmation|overdue -> dismissed`; idempotente se ja `dismissed`.
- IDOR/inexistente -> 404; transicao invalida -> 409.
- Resposta minima: id, analysis_id, description, amount (decimal string), due_date, status, timestamps.

### Preferencias
- `GET /api/v1/payables/reminder-preferences` — cria/retorna default: antecedencias `[3,1,0]`, horario local `09:00`, canal `in_app`, fuso do usuario.
- `PUT /api/v1/payables/reminder-preferences` — antecedencias 0..30 (sem duplicatas), horario local, canais (`in_app` nesta fase).
- Fuso vem de `users.timezone` (IANA); invalido cai em UTC com log sem PII.

## Lembretes e atraso
- `notifications` ganha `channel`, `payable_id`, `reminder_due_date`, `reminder_offset_days`, tipo `payable_due_reminder` e status `cancelled`.
- Unicidade `(payable_id, reminder_due_date, reminder_offset_days, channel)` impede duplicacao em reexecucao concorrente.
- `payables.dispatch_reminders` (beat, default 120s):
  - seleciona payables ativos com `due_date` na janela (lookback 7 dias .. maior antecedencia), com `SELECT ... FOR UPDATE SKIP LOCKED`;
  - calcula `(due_date - offset) as local_time` no fuso do usuario e converte para UTC;
  - cria uma notificacao por offset/canal cujo horario ja venceu, com payload minimo (`payable_id`, `due_date`, `offset_days`, `channel`);
  - usa `ON CONFLICT DO NOTHING` na unicidade.
- `payables.mark_overdue` (beat, default 600s): `pending|pending_confirmation` com `due_date < hoje local do usuario` -> `overdue`.
- Cancelar/ajustar/pagar/descartar marca lembretes pendentes antigos como `cancelled`.
- Entrega real e P15; aqui apenas registros de notificacao.

## Criterios de aceite (viram testes)
1. Recibo sintetico legitimo (linha 48 com DVs mod10/11, 44 coerente, valor/vencimento/referencia) pontua 0 e gera `pending`.
2. Recibo adulterado com DV/linha/barra/valor divergente pontua alto (piso critico) e NAO gera payable.
3. Risk Attention (sem critico) gera `pending_confirmation`.
4. Extrai concessionaria, valor, vencimento, referencia e linha; entidade nao e validada sem fonte.
5. Payable e notificacao de conclusao sao gravados na mesma transacao da analise; reentrega nao duplica.
6. API lista com filtros/cursor e sem N+1; IDOR 404; transicoes idempotentes/409.
7. Lembretes: fuso diferente e virada de dia calculam o horario UTC certo; rodar a tarefa duas vezes cria uma notificacao por `(payable, vencimento, antecedencia, canal)`.
8. `overdue` atualizado pela tarefa; ajuste de vencimento cancela lembretes antigos e permite novos.
9. Usuario B nao ve/nao altera payable de A.
10. Risco Alto nao cria payable.

## Configuracao
`PAYABLES_REMINDER_INTERVAL_SECONDS` (120), `PAYABLES_OVERDUE_INTERVAL_SECONDS` (600), `PAYABLES_REMINDER_LOOKBACK_DAYS` (7).

## Riscos e NAO VALIDADO
- Layout/DV oficial de arrecadacao (48 digitos) e algoritmo unico de DAC nao tem fonte; a validacao aceita mod10 ou mod11 e registra a ressalva.
- Nenhuma lista/registro de concessionarias foi usado; `receipt_issuer_missing` e uma pista, nao prova de fraude.
- ML nao treinado em recibos; score deterministico/visual domina.
- Entrega de notificacao, canais reais, push/email/SMS e confirmacao do usuario no frontend ficam para P15.
- Fuso depende de `users.timezone` correto; `ZoneInfo` invalido cai em UTC.
- Nao ha garantia de que o valor/vencimento impressos sejam os oficiais da concessionaria sem consulta externa.
