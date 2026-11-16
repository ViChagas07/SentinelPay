# ADR 0008: Upload, polling e documento na Central de Verificação

- Status: aceito
- Data: 2026-11-16
- Fase: F07

## Contexto

O contrato do backend cria a análise em `POST /api/v1/analyses` e só permite acompanhar o
job por polling de `GET /api/v1/analyses/{analysis_id}`. O detalhe não devolve etapa,
percentual, documento, campos extraídos, coordenadas de evidência, versão do pipeline,
idioma detectado, relatório para download nem rota de revisão. O limite de upload do
backend é 25 MiB, apesar do pedido de produto de 300 MB. O BFF do front-end recebe o
multipart e o repassa para a API, então o progresso medido no navegador é o envio até o
BFF.

## Decisão

### Upload com XHR e progresso real

- O envio usa `XMLHttpRequest` para receber `upload.onprogress` em bytes. `fetch` não
  expõe progresso de upload no navegador.
- O cliente valida tipo e tamanho antes de enviar usando o mesmo limite configurado no
  backend (`NEXT_PUBLIC_UPLOAD_MAX_MB`, padrão 25). O 413 e o 422 do backend continuam
  traduzidos e visíveis.
- O cancelamento usa `AbortController` ligado a `xhr.abort()`. Como o job pode ter sido
  criado antes do abort, a interface informa que ele pode aparecer na lista de recentes.
- A idempotência usa `crypto.randomUUID()` no formato aceito pelo backend, sem guardar a
  chave entre recargas.

### Polling com backoff

- O detalhe e a lista usam polling porque o contrato não tem SSE, WebSocket nem endpoint
  de eventos.
- O intervalo cresce com o tempo do job: 2,5 s, 5 s, 10 s e 20 s. O polling para em
  estado terminal e volta ao foco da janela.
- O backend não informa etapa. A tela mostra progresso indeterminado e tempo decorrido, e
  lista as etapas documentadas do pipeline apenas como referência. Nenhuma etapa é
  marcada como ativa sem informação do backend.
- A demora acima de 10 minutos gera aviso, não um timeout inventado. O erro real aparece
  quando o job vira `failed`.

### Documento local em memória

- O arquivo selecionado fica em um `Map` em memória do módulo, endereçado pelo id da
  análise recém-criada, para permitir a pré-visualização na Central e no dossiê sem
  storage do navegador.
- O dossiê cria uma object URL a partir do arquivo e a revoga ao desmontar. Ao recarregar
  a página, a memória some e o visualizador mostra o estado honesto de documento não
  exposto pela API.
- Nenhum conteúdo do documento é logado no console.

### Resultado sem recálculo

- Score e classe vêm de `result.score` e `result.band`. A interface só traduz a classe
  para rótulo, cor e carimbo.
- `result_available=false` é tratado como resultado indisponível, não como risco baixo.
- Campos, coordenadas, idioma e versão do pipeline não são inventados. A ausência fica
  visível e registrada em `BACKEND_GAPS.md`.

## Consequências

- O progresso do upload termina quando o BFF recebe o arquivo; a análise em si é assíncrona
  e continua no worker.
- O dossiê aberto a partir de uma tabela não tem pré-visualização até o backend expor o
  documento na análise.
- Quando o backend adicionar etapas, documento, campos e coordenadas, os componentes
  passam a consumir esses dados sem mudar o fluxo de polling.
- O limite de 300 MB continua bloqueado pelo backend atual. O front-end não simula um
  limite que o servidor não aceita.
