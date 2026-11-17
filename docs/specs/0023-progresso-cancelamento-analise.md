# SPEC 0023: progresso real e cancelamento cooperativo da analise

## Objetivo
Expor o andamento real do pipeline de analise e permitir cancelamento pelo dono, sem alterar score, regras, prompts, RAG ou schemas de resultado.

## Estados persistidos
`queued`, `running`, `cancelling`, `cancelled`, `failed`, `completed` e `degraded` (variante de sucesso ja existente). `processing` vira alias de leitura de `running`; a migration converte linhas antigas.

## Etapas e pesos
Pesos em um unico modulo (`domain/analysis_progress.py`):

| Etapa | Peso |
| --- | --- |
| `validation` | 5 |
| `ocr` | 25 |
| `extraction` | 10 |
| `classification` | 10 |
| `rag` | 20 |
| `llm` | 25 |
| `persistence` | 5 |

O percentual e cumulativo e monotonico. Ao iniciar uma etapa, o percentual fica no fim da etapa anterior e o nome da etapa atual e persistido. Ao concluir, avanca o peso. O OCR emite subprogresso por pagina (pagina N de M). Etapas longas (RAG/rerank e LLM) mantem a etapa atual visivel e o cliente mostra estado indeterminado dentro dela.

Medicoes usadas para revisar os pesos: OCR real de uma pagina em cerca de 19,6 s e rerank int8 em CPU em cerca de 12 s p50 (ate 13,4 s p95). O LLM varia entre cloud e LM Studio, entao o peso dele cobre o pior caso local sem prometer tempo. Os pesos ficam em um unico modulo para recalibrar com novas medicoes.

## Persistencia
Colunas novas em `analyses`: `progress_percent` (0..100), `current_stage`, `stage_detail`, `stage_started_at`, `cancel_requested_at`, `cancelled_at`. Cada avanco grava um evento `progress` em `analysis_events` e atualiza a linha. A linha do banco e a fonte de verdade para reconexao.

## Entrega
`GET /api/v1/analyses/{id}/events` com `text/event-stream`, restrito ao dono, envia snapshot imediato e eventos `progress`; fecha com `done` em estado terminal. Cada conexao comeca pelo snapshot persistido, entao abrir a tela no meio da analise mostra o estado correto. O front usa SSE e cai automaticamente para `GET /api/v1/analyses/{id}` se o stream falhar.

## Cancelamento
`POST /api/v1/analyses/{id}/cancel`, dono do JWT, idempotente:
- `queued`: vira `cancelled` na hora e o worker nao consegue reivindicar.
- `running`: vira `cancelling`, grava flag no Redis, tenta `revoke` do Celery sem `terminate` e o worker aborta entre etapas e dentro de OCR/LLM/RAG.
- `cancelling` ou `cancelled`: resposta idempotente.
- `completed`, `degraded` ou `failed`: 409 `analysis_not_cancellable`, sem efeito.

Ao finalizar cancelamento: status `cancelled`, campos de resultado parciais limpos, evento `cancelled`, flag removida e relatorio parcial no S3 removido. A conclusao concorrente usa `UPDATE` condicional que exclui `cancelling`; se o cancelamento chegou antes, o worker apaga o relatorio recem-escrito e finaliza `cancelled`; se a conclusao commitou antes, o cancelamento recebe 409.

## Fora do escopo
Deteccao, score, classes, prompts, RAG, thresholds, schema de resultado, login, conta e menu.

## Criterios de aceite
1. Percentual monotonico e 100 apenas em conclusao.
2. Subprogresso de OCR por pagina.
3. SSE entrega snapshot inicial e reconecta sem perder estado.
4. Fallback de polling testado no front.
5. Cancelamento do dono, idempotente, 409 em terminal.
6. Corrida concluir/cancelar termina em exatamente um estado.
7. Nenhum resultado parcial permanece apos cancelar.
8. Testes unitarios e de integracao cobrem emissor, cancelamento e corrida.
