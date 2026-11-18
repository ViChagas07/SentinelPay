# ADR 0027: Langfuse Cloud com mascaramento antes do envio

- Status: aceito
- Data: 2026-11-18
- Relacionado: SPEC 0024

## Contexto
A analise usa LLM para interpretar evidencias de boletos e contracheques. Esses documentos podem conter CPF, CNPJ, nomes, valores, linha digitavel, codigo de barras, e-mail, telefone, chave PIX e enderecos. O Langfuse Cloud e util para diagnosticar prompts, latencia e falhas do LLM, mas nao pode receber esses dados nem o texto OCR bruto.

## Decisao
- Usar o SDK Python oficial do Langfuse, fixado em `5.2.0`.
- Expor a porta `ObservabilityTracer` no dominio e duas implementacoes: `LangfuseTracer` e `NoopTracer`.
- Ativar somente com `LANGFUSE_ENABLED=true` e as duas chaves presentes. Caso contrario, usar Noop.
- Mascarar toda entrada, saida e metadado em um unico modulo antes de chamar o SDK, com uma segunda barreira no callback `mask` do Langfuse.
- Enviar textos livres apenas como hash e tamanho; `user_id` apenas como HMAC-SHA256.
- Configurar timeout curto, envio em lote assincrono, amostragem por `LANGFUSE_SAMPLE_RATE` e `flush`/`shutdown` no encerramento.
- Tratar qualquer falha do SDK como observabilidade indisponivel, sem afetar a analise.

## Justificativa
- O SDK oficial concentra transporte, batching, retry e integracao com OpenTelemetry, evitando um cliente HTTP proprio.
- O mascaramento central e a unica barreira obrigatoria antes do envio, o que reduz o risco de um novo ponto de instrumentacao esquecer um campo sensivel.
- Hashes preservam a possibilidade de correlacionar a mesma entrada sem expor o conteudo.
- Noop por padrao mantem o comportamento atual e permite rodar testes e ambientes locais sem credenciais.

## Consequencias
- O payload no Langfuse nao mostra o texto original de prompts, justificativas ou respostas, apenas hashes, tamanho e metadados estruturados.
- Nomes nao rotulados em texto livre nao sao detectados de forma confiavel; por isso texto livre de documento nunca e enviado, e os campos estruturados de nome sao mascarados.
- O envio depende do SDK e da disponibilidade da rede; falhas sao silenciosas para o usuario e registradas apenas como evento de observabilidade indisponivel.
- O teste contra o Langfuse Cloud real depende de chaves e nao entra na suite padrao.
