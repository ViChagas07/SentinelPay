# SPEC 0006: Ingestao de documentos (OCR e sinais visuais)

## Objetivo
Converter PDF nativo, PDF escaneado e imagem em texto estruturado e sinais heurísticos de anomalia visual, sem interpretar campos de negocio e sem LLM.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: `OcrPort` com `recognize(image_bytes, language=None) -> OcrResult`; `OcrResult` contem blocos (`text`, `bbox`, `confidence`), idioma e metadados do motor.
- RF2: adaptador PaddleOCR com carga preguiçosa (uma vez por processo), CPU por padrao, idiomas de `OCR_LANGS` limitados a pt, es e en.
- RF3: PDF nativo: se a camada de texto for utilizavel, usa-la; senao renderizar paginas em DPI configuravel e rodar OCR. Imagem usa OCR direto.
- RF4: respeitar `OCR_MAX_PAGES`, `OCR_RENDER_DPI`, `OCR_TIMEOUT_SECONDS` e `OCR_MAX_IMAGE_PIXELS`; processar uma pagina por vez e falhar de forma controlada.
- RF5: `VisualAnomalyService` com sinais, cada um com nome, valor 0..1, explicacao curta, pagina e regiao quando aplicavel: qualidade (desfoque/resolucao/ruido), ELA, variancia de ruido por blocos, copia-e-cola interna (ORB) e metadados de PDF.
- RF6: toda saida de sinal deve deixar claro que e heuristica, nao prova; nenhum sinal decide fraude.
- RF7: fixtures sinteticas geradas por script (imagem limpa, imagem com trecho colado, PDF com texto, PDF escaneado), nunca documentos reais.
- RF8: OCR fake nos testes unitarios; teste de integracao opcional com PaddleOCR real, tempo e memoria registrados no PROGRESS.
- RNF1: sem interpretacao de campos, sem LLM, sem Celery/async processing.
- RNF2: texto OCR e dado nao confiavel; nao vira instrucao e nao e logado integralmente.
- RNF3: limites de tempo/memoria/page count; falha controlada para arquivo ilegivel.

## Fora do escopo
Extracao de campos (valor, CNPJ, nome), score de risco, LLM, processamento assincrono, armazenamento de texto/resultado no banco e interface de usuario.

## Contrato (modelos e servicos)
- `OcrPort.recognize(image: bytes, *, language: str | None = None) -> OcrResult` (async).
- `OcrBlock`: `text`, `bbox` opcional `(x0,y0,x1,y1)`, `confidence` 0..1.
- `OcrResult`: `blocks`, `language`, `engine`.
- `IngestionResult`: `blocks` com pagina, `signals`, `page_count`, `used_ocr`, `source_type` (`pdf_native`, `pdf_ocr`, `image`), `language`.
- `VisualSignal`: `name`, `value` 0..1, `explanation` (contem "heuristic; signal, not proof"), `page` opcional, `region` opcional.
- `DocumentIngestionService.ingest(data: bytes) -> IngestionResult`; arquivo ilegivel -> problem+json/erro de aplicacao controlado.
- Sinais esperados: `image_blur`, `image_resolution`, `image_noise`, `ela_recompression`, `noise_variance_blocks`, `copy_move_orb`, `pdf_producer`, `pdf_dates`, `pdf_incremental_updates`, `pdf_overlaid_layers`.

## Criterios de aceite (cada um vira pelo menos um teste)
1. PDF com texto usa camada nativa, nao chama OCR fake, retorna blocos com pagina/bbox e `used_ocr=False`.
2. PDF escaneado renderiza paginas e usa OCR fake, retornando `used_ocr=True`, `source_type=pdf_ocr`, blocos com pagina.
3. Imagem usa OCR fake, `source_type=image`, pagina 1.
4. Arquivo ilegivel/bytes invalidos -> erro controlado; PDF acima de `OCR_MAX_PAGES` -> erro; pagina renderizada acima do teto de pixels -> erro.
5. OCR fake lento excede `OCR_TIMEOUT_SECONDS` -> erro de timeout.
6. Sinais de imagem limpa, borrada e com trecho colado sao calculados com valores 0..1, explicacao heuristica, pagina/regiao; blur e/ou copy-move/ELA/noise mudam entre fixtures.
7. Meta de PDF: produtor/datas, incrementais e camadas detectados nos fixtures sinteticos.
8. Todos os sinais sem fixture exercitada sao registrados como NAO VALIDADO.
9. Teste opcional real do PaddleOCR (marcador docker/ocr) em imagem sintetica, com tempo/RSS registrados.
10. Checklist OWASP atualizado com OCR/upload/visao.

## Casos de borda e de abuso
- PDF sem texto, PDF misto, PDF com muitas paginas, pagina gigante, PDF corrompido, imagem truncada, imagem com dimensoes enormes.
- Imagem com texto minusculo/baixa resolucao; OCR vazio; confianca baixa; idioma fora da allowlist.
- Imagem com copia-move, recompressao JPEG, ruido nao uniforme, regiao colada; falsos positivos e falsos negativos.
- Metadados ausentes, datas invertidas, incremental update, camadas OCG.
- PaddleOCR indisponivel/modelo nao baixado: falha controlada e NAO VALIDADO.

## Plano de testes (TDD: teste falho primeiro)
1. Fixtures sinteticas e helpers.
2. Sinais visuais com fixtures limpa/borrada/colada e PDFs.
3. OcrPort/adapter com fake; optional real.
4. DocumentIngestionService: nativo, escaneado, imagem, limites, timeout e ilegivel.
5. Rodar `make check`, `make test-docker`, `make bandit`, `make audit`; registrar tempo/memoria do OCR real.

## Riscos e NAO VALIDADO
- PaddleOCR real pode exigir download de modelos e rede; sem execucao, fica NAO VALIDADO com motivo.
- OCR em CPU e lento; timeout de thread nao interrompe uma inferencia ja em andamento.
- Sinais visuais sao heuristicas, sujeitos a falso positivo/negativo; nao sao prova.
- OpenCV GUI e dependencia transitiva do PaddleOCR; a imagem Docker precisa de libs de sistema (libGL etc.).
- Sem OCR de multiplos idiomas simultaneos: o idioma primario de `OCR_LANGS` e usado por passada.
- Sem antivirus; arquivo validado ainda pode conter malware (herdado da P05).
