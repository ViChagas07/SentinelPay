# ADR 0026: progresso por eventos persistidos, SSE e cancelamento cooperativo

## Contexto
A analise roda em Celery e pode durar minutos, principalmente OCR em CPU e rerank de cerca de 12 s. O front so recebia `status` e fazia polling sem etapa nem percentual. Nao havia cancelamento.

## Decisao
1. O pipeline grava progresso real em `analyses` a cada etapa concluida, com pesos em `domain/analysis_progress.py` e evento `progress` em `analysis_events`.
2. O PostgreSQL e a fonte de verdade. SSE le a linha e envia snapshot na conexao, o que torna reconexao e abertura tardia corretas por construcao. Nao ha percentual por timer.
3. O cancelamento combina tres camadas: transicao condicional no banco (`cancelling`), flag no Redis verificada entre etapas e dentro de OCR/LLM/RAG, e `revoke` do Celery sem `terminate` como reforco.
4. A conclusao usa `UPDATE` condicional que exclui `cancelling`. Cancelamento que chega antes ganha; conclusao que commitou antes faz o cancelamento responder 409. O relatorio parcial no S3 e removido quando o cancelamento vence a corrida.
5. `processing` permanece como alias de leitura de `running` para nao quebrar dados antigos; a migration converte as linhas.

## Alternativas descartadas
- Progresso sintetico por tempo: proibido pelo requisito e enganoso.
- WebSocket: SSE atende o fluxo unidirecional, funciona pelo proxy BFF e reconecta nativamente.
- Apenas `revoke` do Celery: nao interrompe cooperativamente um loop de OCR ou uma chamada de LLM em andamento.
- Apenas polling: mais latencia e sem subeventos; mantido como fallback.

## Consequencias
- Mais uma escrita por etapa e por pagina de OCR; volume limitado e util para auditoria.
- O SSE faz polling interno curto da linha; com uma conexao por analise o custo e aceitavel e evita acoplamento do worker ao processo da API.
- Cancelar uma analise em `persist` pode apagar um relatorio recem-escrito; e o comportamento desejado para nao deixar resultado meio salvo.
