# SPEC 0007: Analise deterministica de boletos (FEBRABAN)

## Objetivo
Extrair e validar boletos de cobranca (linha digitavel de 47 digitos) e de arrecadacao/convenio (48 digitos) de forma deterministica, sem ML/LLM/endpoint, produzindo campos com confianca, evidencias rastreaveis e um subscore de risco 0 a 100.

## Fontes e versao
- Fontes designadas pelo dono: `knowledge/febraban/manual_febraban_v1.pdf` e `knowledge/layouts/boleto_{bb,bradesco,caixa,itau,santander}.pdf`.
- `docs/normas/` nao contem os manuais; a base acima e a fonte efetiva da P07.
- Conjunto de regras: `febraban-v1`; dados de bancos: `febraban-banks-v1`.
- Cada regra tem arquivo/secao de origem no ADR-0010. Regra sem fonte registrada nao entra no motor.
- A indexacao vetorial da base e da P10 e nao faz parte desta fase.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: value objects para linha digitavel bancaria (47 digitos), linha de arrecadacao/convenio (48 digitos) e codigo de barras (44 digitos).
- RF2: conversao linha digitavel bancaria <-> codigo de barras; a conversao de 48 digitos nao e implementada porque o layout nao consta nas fontes.
- RF3: validacao de DAC/DV por campo (modulo 10) e geral (modulo 11) conforme o manual; no Bradesco, campo 3 por modulo 11 conforme o layout.
- RF4: decodificacao de banco, moeda, fator de vencimento, valor e campo livre.
- RF5: fator de vencimento exatamente como o manual: base 07/10/1997; 0000 = sem vencimento; 1..9999 = base + dias; o manual nao documenta reinicio de ciclo, entao ele nao e implementado.
- RF6: validacao de digitos verificadores de CPF e CNPJ extraidos do beneficiario e do pagador.
- RF7: extracao de linha digitavel, codigo de barras textual, valor, vencimento, beneficiario, pagador, CNPJ/CPF e banco a partir de texto OCR, tolerando confusoes 0/O, 1/l/I, espacos e pontuacao, com confianca por campo.
- RF8: leitura opcional do codigo de barras da imagem via OpenCV; indisponibilidade vira NAO VALIDADO e a linha digitavel e usada.
- RF9: motor de regras com id, versao, severidade, peso, fonte e evidencia; regras iniciais: linha invalida, DV invalido, linha x codigo de barras, valor divergente, vencimento divergente, banco do cabecalho incoerente, banco fora da lista com fonte, moeda nao suportada, CPF/CNPJ invalido, campos ilegiveis, codigo de barras ilegivel.
- RF10: saida `BoletoAnalysis` com campos extraidos e confianca, evidencias com chave i18n, subscore deterministico, versao das regras e itens NAO VALIDADOS.
- RNF1: sem consulta externa (BACEN, CIP, Receita, APIs de CNPJ); privacidade e prevencao de SSRF.
- RNF2: sem logs de CPF/CNPJ/nome; evidencias mascaram identificadores.
- RNF3: texto OCR e dado nao confiavel; nao vira instrucao.
- RNF4: dominio puro (sem FastAPI, SQLAlchemy, HTTP, OpenCV); OpenCV fica na infraestrutura.

## Fora do escopo
- ML, LLM, endpoint, persistencia, fila e interface.
- Indexacao vetorial (P10).
- Consulta a BACEN/CIP/Receita para confirmar banco, beneficiario ou registro do titulo.
- Layout completo, DVs e conversao da linha de 48 digitos (nao constam nas fontes).
- Leitura garantida de codigo de barras em qualquer imagem.
- Regras de multa/juros, nosso numero, agencia/conta, logotipo e QR Code PIX.

## Contrato (modelos e servicos)
- `BankDigitableLine(digits: str)`: 47 digitos; `bank_code`, `currency`, `free_field`, `due_factor`, `amount_cents`, `general_dv`; `to_barcode()`; `dv_errors(directory)`.
- `UtilityDigitableLine(digits: str)`: 48 digitos; somente validacao estrutural; `to_barcode()` levanta `NotVerifiableLayoutError`.
- `Barcode(digits: str)`: 44 digitos; `bank_code`, `currency`, `general_dv`, `due_factor`, `amount_cents`, `free_field`; `to_line(directory)`; `general_dv_is_valid()`.
- `Money(cents: int)`: valor monetario inteiro em centavos; `as_decimal`.
- `due_date_from_factor(factor: int) -> date | None`; `factor_from_due_date(value: date | None) -> int`.
- `Cpf`, `Cnpj`: digitos estruturais e `is_valid` por DV; `parse_tax_id(text) -> TaxId | None`.
- `BankDirectory`: bancos da fonte, aliases e algoritmo de DV por campo; `find_by_code`, `find_by_name`.
- `ExtractedField[T]`: `value`, `confidence` (0..1), `raw`.
- `BoletoFields`: linha, codigo de barras textual, valor, vencimento, beneficiario, pagador, CPF/CNPJ e banco do cabecalho, todos opcionais e com confianca.
- `RuleDefinition`: `id`, `version`, `severity`, `weight`, `source`, `message_key`.
- `Evidence`: `rule_id`, `rule_version`, `severity`, `weight`, `message_key`, `source`, `details` (sem PII).
- `BoletoAnalysis`: `fields`, `decoded`, `evidence`, `subscore`, `rule_set_version`, `sources`, `not_validated`.
- `BoletoAnalysisService.analyze(text, barcode_image=None) -> BoletoAnalysis`.
- `BarcodeReaderPort.read(image: bytes) -> BarcodeRead`; `BarcodeRead(status, digits, reason)`.

## Criterios de aceite (cada um vira pelo menos um teste)
1. Linha bancaria sintetica valida converte para o codigo de barras esperado e volta para a mesma linha; DVs por campo e geral conferem.
2. Linha de 48 digitos e aceita estruturalmente; conversao/decodificacao retornam NAO VERIFICAVEL com motivo, sem inventar layout.
3. Fator 0000 retorna sem vencimento; fator 9999 retorna 21/02/2025 (marco do manual); fator fora de 0..9999 e rejeitado.
4. Bradesco valida campo 3 por modulo 11 e os demais campos por modulo 10; os outros bancos usam modulo 10 nos tres campos.
5. CPF/CNPJ sinteticos validos passam; DV adulterado, todos os digitos iguais e CNPJ zerado falham.
6. Texto OCR sintetico extrai todos os campos com confianca; confusoes 0/O e 1/l sao corrigidas e reduzem a confianca de forma deterministica.
7. Boleto sintetico valido tem subscore baixo (0) e nenhuma evidencia critica.
8. Cada adulteracao isolada dispara a regra esperada: DV, linha x codigo de barras, valor, vencimento, banco do cabecalho, banco desconhecido, moeda, CPF/CNPJ, campo ilegivel e codigo de barras ilegivel.
9. Regra critica impoe piso 80 ao subscore; soma de pesos e limitada a 100; ordem das evidencias e deterministica.
10. Regra sem fonte nao entra no motor; toda regra ativa tem fonte em `knowledge/febraban/` ou `knowledge/layouts/`.
11. Leitura de codigo de barras indisponivel ou sem resultado vira NAO VALIDADO/sem penalidade quando a imagem nao foi fornecida; quando a imagem foi fornecida e falhou, ha evidencia de codigo de barras ilegivel.
12. Nenhuma consulta externa e feita pelo dominio, aplicacao ou adaptador.

## Casos de borda e de abuso
- Linha com 46/49 digitos, caracteres nao numericos, letras confundiveis, pontuacao e espacos.
- Linha dividida em duas linhas de OCR; multiplos candidatos; falso codigo de barras de 44 digitos.
- DAC de campo e geral adulterados; codigo de barras divergente; codigo de barras textual de 44 digitos.
- Fator 0, fator 9999, fator pos-2025 nao reiniciado; data impressa divergente; valor com e sem `R$`.
- Banco desconhecido/inexistente; cabecalho com nome de um banco e codigo de outro; moeda diferente de 9.
- CPF/CNPJ ausente, zerado, com DV invalido, formatado ou sem formatacao.
- Texto OCR com baixa confianca, campos ausentes, ruido e caracteres especiais.
- Imagem invalida, sem codigo de barras, codigo de barras nao-ITF ou detector OpenCV indisponivel.
- Linha de 48 digitos de arrecadacao/convenio sem layout nas fontes.

## Plano de testes (TDD: teste falho primeiro)
1. DVs, linha, codigo de barras, conversao e fator de vencimento.
2. CPF/CNPJ e diretorio de bancos com fontes.
3. Parsers de OCR com texto sintetico e confusoes.
4. Motor de regras com boletos sinteticos validos e uma adulteracao por caso.
5. Servico de aplicacao e adaptador OpenCV com detector fake; leitura real marcada NAO VALIDADA.
6. `make lint`, `make format-check`, `make typecheck`, `make arch`, `make test`; cobertura do dominio.

## Riscos e NAO VALIDADO
- O manual tem tabela de exemplo internamente inconsistente com a formula do fator (1000, 4000, 7000); prevalece a formula explicita e o marco 9999=21/02/2025. Registrado no ADR-0010.
- O manual nao documenta o reinicio do ciclo do fator usado pelo mercado apos 22/02/2025; nao implementado e marcado NAO VERIFICAVEL.
- O layout de 48 digitos, seus DVs e a conversao para 44 digitos nao constam nas fontes; NAO VERIFICAVEL.
- O algoritmo de DV de CPF/CNPJ nao consta nas fontes; a regra usa algoritmo padrao deterministico e o ADR registra a lacuna.
- A lista de bancos e "principais"; codigo fora dela nao prova fraude sem consulta ao BACEN, que e proibida nesta fase; a regra e HIGH com ressalva e o BACEN fica NAO VALIDADO.
- Leitura real de codigo de barras com OpenCV em imagem sintetica nao foi confirmada; se falhar, fica NAO VALIDADO.
- Registro do titulo na CIP e CNPJ na Receita nao sao verificados (sem consulta externa).
