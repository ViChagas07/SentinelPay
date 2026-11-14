# ADR 0010: Analise deterministica de boletos FEBRABAN

- Status: aceito
- Data: 2026-11-14

## Contexto
A P07 precisa validar boletos sem ML, LLM, endpoint ou consulta externa. A base designada pelo dono esta em `knowledge/febraban/manual_febraban_v1.pdf` e `knowledge/layouts/boleto_{bb,bradesco,caixa,itau,santander}.pdf`; `docs/normas/` nao contem os manuais. O manual cobre a linha de 47 digitos, o codigo de barras de 44 digitos, DVs, fator de vencimento e uma lista de bancos "principais". Ele nao cobre o layout da linha de 48 digitos nem o algoritmo de DV de CPF/CNPJ.

## Decisao
- Dominio puro em `paysentineliq.domain.boleto`, sem FastAPI, SQLAlchemy, HTTP ou OpenCV. O adaptador OpenCV fica em infraestrutura e a orquestracao em aplicacao.
- Conjunto de regras versionado como `febraban-v1`. Dados de bancos versionados como `febraban-banks-v1` em `backend/src/paysentineliq/domain/boleto/data/febraban_banks_v1.json`, com `source` por banco. Nenhuma lista de bancos e escrita de memoria no codigo.
- Cada `RuleDefinition` tem `source` obrigatorio. O motor descarta regras sem fonte. Toda fonte ativa aponta para `knowledge/febraban/...` ou `knowledge/layouts/...`.
- Subscore de risco 0..100: `raw = min(100, soma dos pesos das regras disparadas)`; se qualquer regra `CRITICAL` disparar, `subscore = max(raw, 80)`. Regras `INFO` tem peso 0. Evidencias sao ordenadas por `rule_id` e depois por detalhe para reprodutibilidade.
- O texto OCR e tratado como dado nao confiavel. CPF/CNPJ e nomes nao sao logados; detalhes de evidencia usam identificadores mascarados.
- Nenhuma consulta externa: BACEN, CIP, Receita Federal e APIs de CNPJ ficam fora. O que depender delas e marcado NAO VALIDADO.

## Fontes por regra
| Regra | Fonte |
| --- | --- |
| `line_invalid` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.2, 2 e 3 |
| `dv_invalid` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.5, 2 e 3; `knowledge/layouts/boleto_bradesco.pdf` sec. 2 (campo 3 modulo 11) |
| `line_barcode_mismatch` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.2, 1.3, 2 e 3 |
| `amount_mismatch` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.3, 1.4, 2 e 3 |
| `due_date_mismatch` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.4, 2 e 3 |
| `bank_header_mismatch` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.6, 2 e 3; `knowledge/layouts/boleto_{bb,bradesco,caixa,itau,santander}.pdf` sec. 1 e 2.1 |
| `bank_code_unknown` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.6, 2 e 3 (com ressalva de consulta BACEN) |
| `currency_unsupported` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.2 e 1.3 |
| `tax_id_invalid` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 3 (CNPJ zerado/invalido); algoritmo de DV de CPF/CNPJ NAO consta nas fontes |
| `field_illegible` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.1 e 3 |
| `barcode_unreadable` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.1 e 3 |
| `utility_line_not_verifiable` | `knowledge/febraban/manual_febraban_v1.pdf` sec. 1.2 e 2 (apenas o comprimento de 48 digitos) |

## Linha digitavel e codigo de barras
- Linha bancaria de 47 digitos conforme o manual: `AAABC.CCCCX DDDDD.DDDDDY EEEEE.EEEEEZ K FFFFFFFFFFFFFFFFF`. O campo livre tem 25 digitos (5+10+10); o manual descreve o primeiro grupo como "CCCC+X", mas a propria mascara tem 5 digitos antes do DAC. A conversao usa 5+10+10.
- Codigo de barras de 44 digitos: banco (3), moeda (1), DAC geral (1), fator (4), valor (10) e campo livre (25). Valor em centavos, sem virgula.
- DVs dos campos 1..3: modulo 10, exceto o campo 3 do Bradesco (237), que o layout define como modulo 11. O algoritmo de modulo 11 e o do manual sec. 1.5. DAC geral: modulo 11.
- Linha de 48 digitos: aceita somente validacao estrutural (48 digitos). O layout, os DVs, a conversao e a decodificacao nao constam nas fontes; `to_barcode()` levanta `NotVerifiableLayoutError` e a analise registra NAO VALIDADO.

## Fator de vencimento
- Base: 07/10/1997. `0000` significa sem vencimento. `1..9999` significa `base + factor dias`.
- O manual afirma que o fator maximo 9999 foi atingido em 21/02/2025 e que, apos essa data, o campo deve conter `0000`. A formula confirma o marco 9999=21/02/2025. A tabela de exemplos do manual para 1000, 4000 e 7000 e internamente inconsistente com a formula; prevalece a formula explicita.
- O manual nao documenta o reinicio de ciclo para 1000 usado fora da fonte. Nao implementamos reinicio. Fatores nao zero continuam decodificados pela formula; um fator pos-2025 so e aceitavel se a data impressa coincidir, e a ausencia de reinicio fica NAO VALIDADA.

## CPF/CNPJ
- A regra de CNPJ invalido/zerado tem fonte no manual. O algoritmo de digitos verificadores de CPF/CNPJ nao consta em `knowledge/febraban` nem em `knowledge/layouts`; implementamos o algoritmo padrao deterministico, registrado aqui como lacuna da base. A regra permanece ativa porque o manual lista CNPJ invalido como indicador, mas o algoritmo em si e NAO VERIFICAVEL na base designada.

## Bancos
- O arquivo de dados reproduz os codigos e nomes da secao 1.6 do manual. Os layouts acrescentam os nomes usados nos cabecalhos e a excecao do Bradesco. Aliases sao derivados dos nomes oficiais (remocao de sufixos societarios e parenteses), nao de uma lista externa.
- Codigo fora da lista gera evidencia HIGH `bank_code_unknown`, mas a mensagem ressalva que a autorizacao BACEN nao foi consultada (NAO VALIDADO). Nao tratamos codigo desconhecido como fraude confirmada.

## Score
- Pesos iniciais: `line_invalid` 60 (critico), `dv_invalid` 70 (critico), `line_barcode_mismatch` 70 (critico), `amount_mismatch` 70 (critico), `due_date_mismatch` 30, `bank_header_mismatch` 30, `bank_code_unknown` 20, `currency_unsupported` 15, `tax_id_invalid` 25, `field_illegible` 10, `barcode_unreadable` 10, `utility_line_not_verifiable` 0 (INFO).
- Piso critico: 80. Boleto sintetico valido sem imagem de codigo de barras: 0.
- Limiar de campo ilegivel: confianca < 0.5 ou campo obrigatorio ausente. O conjunto minimo verificado e linha, valor, vencimento (quando o fator nao for 0000), beneficiario, CPF/CNPJ do beneficiario e banco do cabecalho.

## Alternativas consideradas
- Copiar a lista de bancos no codigo: descartado; a lista deve ter fonte e versao.
- Consultar BACEN/CIP/Receita: descartado por privacidade, SSRF e escopo.
- Implementar o layout de 48 digitos de memoria: descartado; nao consta nas fontes.
- Usar o reinicio de ciclo do fator de 22/02/2025: descartado; nao consta nas fontes designadas.
- Deixar a regra de CPF/CNPJ desligada: descartado porque a validacao foi pedida explicitamente; a lacuna do algoritmo fica documentada.
- Usar ML/LLM para extrair campos: descartado; parsers deterministicos e confianca explicita.

## Consequencias
- A base tem lacunas que viram NAO VALIDADO em vez de regras inventadas: linha de 48 digitos, reinicio do fator, DV de CPF/CNPJ, BACEN/CIP/Receita e leitura real de codigo de barras.
- A lista de bancos pode gerar falso positivo para instituicoes legitimas fora dos 25 codigos "principais"; a severidade HIGH e a ressalva BACEN deixam isso explicito.
- Pesos e limiar de confianca sao versionados; mudar a formula exige novo ADR e nova versao do conjunto de regras.
- A analise nao persiste dados e nao faz consulta externa; a P10 podera indexar a base, mas nao altera o contrato do dominio.
