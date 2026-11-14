# ADR 0018: Recibos, payables e lembretes

- Status: aceito
- Data: 2026-11-14

## Contexto
A P11/P13 analisam boleto e contracheque de forma assincrona. A P14 adiciona contas de consumo: precisa extrair linha de 48 digitos, valor, vencimento, referencia e concessionaria; pontuar com o mesmo servico; e registrar vencimentos/lembretes sem inventar dados regulatorios.

## Decisao
- **Novo tipo `receipt`** no grafo (documento, analise, relatorio e API). A analise usa um pacote de dominio proprio (`domain/receipt`) e reaproveita os parsers de linha/valor/vencimento e `mod10`/`mod11` da P07.
- **Sem lista de concessionarias**: o emissor e extraido, mas nao validado. A ausencia vira evidencia media/info, nunca fraude confirmada.
- **DV de 48 digitos**: cada bloco de 11 dados + 1 DV e aceito se casar com modulo 10 **ou** 11; se nao casar com nenhum, `receipt_dv_invalid` critico. O algoritmo oficial nao tem fonte em `knowledge/`, entao a escolha fica registrada como `receipt_dv_algorithm_not_validated`.
- **Codigo de 44 vs linha de 48**: comparacao estrutural (44 = quatro blocos de 11 sem os DVs). Divergencia e evidencia critica.
- **Valor/vencimento**: extraidos do texto; valores/datas duplicados divergentes viram evidencia. O ML nao foi treinado em recibos; as features de tipo ficam zero e o deterministico/visual domina. **NAO VALIDADO** para ML.
- **Payable na mesma transacao do resultado**: `AnalysisRepositoryPort.complete` aceita `payables` e insere junto com status, evento e notificacao. `analysis_id` unico impede duplicidade. Politica: Low `pending`, Attention `pending_confirmation`, High nenhum; guardrail de injecao forca confirmacao.
- **Payables como recurso proprio**: lista/cursor, confirmar, pagar, ajustar vencimento e descartar, sempre por dono do JWT. Transicoes com `SELECT FOR UPDATE` e idempotencia; estados finais nao regridem.
- **Preferencias de lembrete no PostgreSQL**: offsets `[3,1,0]`, horario local `09:00`, canal `in_app`; fuso do usuario. Sem contador em Redis.
- **Lembretes via outbox**: task de beat seleciona payables com `FOR UPDATE SKIP LOCKED`, calcula o horario local no fuso do usuario, converte para UTC e insere notificacoes com `ON CONFLICT DO NOTHING` na unicidade `(payable_id, reminder_due_date, reminder_offset_days, channel)`. Entrega fica para P15.
- **Overdue por tarefa**: `due_date < hoje local do usuario`; roda no beat.
- **Ajuste de vencimento** cancela lembretes pendentes antigos e permite novos pela nova data; pagar/descartar tambem cancela.

## Alternativas descartadas
- **Validar concessionaria por lista fixa**: sem fonte; violaria RULES e produziria falso positivo/negativo.
- **Implementar um algoritmo unico de DV de arrecadacao**: nao ha fonte registrada; aceitar mod10/mod11 e registrar a ressalva e mais honesto.
- **Criar payable em transacao separada**: poderia gravar analise sem vencimento ou duplicar em reentrega; a transacao unica + unique resolve.
- **Lembretes em Redis**: perde durabilidade/unicidade com o banco; a fonte e PostgreSQL.
- **Calcular lembretes em SQL com timezone**: complexo e sujeito a erro; Python `zoneinfo` por payable e testavel.
- **Criar notificacao antes do commit**: o outbox perderia eventos em falha; a insercao e na mesma transacao e a entrega depois.
- **Nova fila para lembretes**: `scheduler` ja existe e e o lugar de tarefas periodicas; `notifications` e para entrega.

## Consequencias
- Recibos legitimos geram vencimento e lembretes; adulterados de alto risco nao geram payable.
- A cobertura de DV/entidade e explicitamente limitada e registrada no relatorio.
- Reexecucao do beat e reentrega de analise nao duplicam payables/lembretes.
- O relatorio expoe score/classe/evidencias/justificativa; `fields` continua fora da API.
- **NAO VALIDADO**: layout oficial de arrecadacao, lista oficial de concessionarias, ML para recibos, fusos reais de todos os usuarios e entrega/canais (P15).
