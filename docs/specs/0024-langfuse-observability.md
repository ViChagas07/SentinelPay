# SPEC 0024: Observabilidade de LLM com Langfuse (F1)

## Objetivo
Integrar o Langfuse Cloud como observabilidade de LLM sem enviar dados pessoais ou documentos brutos. O tracer fica atras de uma flag, usa Noop por padrao e nunca pode quebrar nem atrasar a analise.

## Configuracao
- `LANGFUSE_ENABLED` (padrao `false`).
- `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY` vazias por padrao.
- `LANGFUSE_HOST` opcional; vazio usa `https://cloud.langfuse.com`.
- `LANGFUSE_SAMPLE_RATE` entre 0 e 1, padrao 1.0.
- Chaves reais ficam apenas no ambiente ou no `.env` local ignorado pelo git.
- `.env.example` recebe somente placeholders vazios.

## Arquitetura
- Porta `ObservabilityTracer` em `domain/ports/observability.py`.
- `NoopTracer` em `infrastructure/observability/noop_tracer.py`.
- `LangfuseTracer` em `infrastructure/observability/langfuse_tracer.py`, com cliente injetavel para testes.
- O tracer e criado uma vez no runtime do worker e no lifespan da API, e fechado no shutdown.
- Sem flag, sem chaves ou com falha de inicializacao, o Noop e usado.

## Dados enviados
- Campos estruturados e metadados: tipo de documento, score, banda, idioma, evidencia (regra, severidade, peso, chave de mensagem), modelo, versao de prompt, resultado e latencia.
- Textos livres, excertos de OCR, justificativas e respostas do modelo sao enviados apenas como SHA-256 e tamanho.
- `user_id` e identificadores equivalentes sao enviados como HMAC-SHA256.
- Imagens, bytes, texto OCR bruto e prompts completos nunca sao enviados.

## Mascaramento
Aplicado de forma centralizada a toda entrada, saida e metadado antes do envio:
- CPF e CNPJ com e sem formatacao.
- Nomes de pessoas em campos estruturados e linhas rotuladas em pt, es e en.
- Valores monetarios em `R$` e linhas rotuladas.
- Linha digitavel (47/48 digitos) e codigo de barras (44 digitos).
- E-mail, telefone, chave PIX, CEP e enderecos.
- Segredos ja cobertos por `mask_pii`, como JWT, Bearer e chaves de API.

## Falhas e latencia
- Timeout curto no cliente, envio em lote assincrono e `flush`/`shutdown` no encerramento.
- Falha ao iniciar, atualizar, enviar ou fechar o Langfuse e registrada sem payload e nunca propaga.
- O Noop nao altera a resposta, o score, as evidencias nem o fluxo da analise.

## Testes
- Mascaramento com exemplos em portugues, espanhol e ingles.
- Cliente falso que captura todos os payloads e falha se encontrar CPF, valor, linha digitavel, e-mail, telefone ou nome em claro.
- Tracer que nao quebra o pipeline quando o cliente falso lanca erro.
- Noop transparente no pipeline.
- Configuracao e validacao de sample rate.

## Criterios de aceite
1. `langfuse` fixado no Poetry e `LANGFUSE_*` documentado no `.env.example`.
2. Tracer escolhido por flag, com Noop quando desligado ou sem chaves.
3. Mascaramento centralizado coberto por testes pt/es/en.
4. Falhas do Langfuse nao alteram a analise.
5. `docs/observability-langfuse.md` descreve o que e enviado e o que e mascarado.
6. `make check` verde.

## Fora do escopo
- Prompt management, datasets, scores e avaliacoes do Langfuse.
- Envio de imagens ou do texto OCR completo.
- Teste contra o Langfuse Cloud real sem chaves no ambiente de CI.
