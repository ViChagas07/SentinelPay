# ADR 0009: OCR, leitura de PDF e sinais visuais

- Status: aceito
- Data: 2026-11-14

## Contexto
A P06 precisa extrair texto de PDF nativo, PDF escaneado e imagem e calcular sinais visuais para fases futuras. A maquina de desenvolvimento nao tem GPU PaddlePaddle compativel, o ambiente Python e 3.11 e o processamento ainda e sincrono. Nenhum documento real pode ser usado em testes.

## Decisao
- OCR: PaddleOCR 3.7.0 com PaddlePaddle 3.3.1/PaddleX 3.7.2 em CPU. O motor e criado na primeira chamada, em thread, com cache por idioma de modelo e lock de inferencia; `OcrPort` isola a aplicacao do framework. `pt`/`es` usam o modelo Latin; `en` usa o modelo ingles. `OCR_LANGS` define a allowlist e o primeiro idioma e o primario por passada. `OcrResult` carrega blocos/bbox/confianca/idioma.
- PDF: PyMuPDF 2.1 (`import pymupdf`) extrai texto/bbox e metadados e renderiza paginas. Se a pagina tiver camada de texto utilizavel, ela e usada; paginas sem texto utilizavel sao renderizadas e enviadas ao OCR. Paginas sao processadas uma por vez para limitar memoria. `OCR_MAX_PAGES`, `OCR_RENDER_DPI`, `OCR_MAX_IMAGE_PIXELS` e `OCR_TIMEOUT_SECONDS` limitam abuso; timeout e best-effort porque uma inferencia C++ em thread nao pode ser interrompida com seguranca.
- Visao: OpenCV 4.10 (contrib, dependencia do PaddleOCR), NumPy e Pillow. `VisualAnomalyService` calcula desfoque (variancia do Laplaciano), resolucao, ruido, ELA por blocos, variancia de ruido por blocos, ORB copy-move e metadados de PDF (produtor/datas/incremental/layers). Cada sinal e 0..1, tem explicacao "heuristic; signal, not proof" e pagina/regiao quando aplicavel. Nenhum sinal decide negocio.
- Fixtures: 100% sinteticas, geradas por `scripts/generate_fixtures.py` e pelos helpers de teste; imagens/PDFs gerados nao sao documentos reais.
- Testes: OCR fake nos unitarios; teste real opcional do PaddleOCR (marcador docker/ocr) e registro de tempo/RSS no PROGRESS.

## Alternativas consideradas
- Tesseract/outro OCR: descartado por requisito de PaddleOCR e por idiomas/qualidade desejados.
- `pdf2image`/Poppler: descartado; PyMuPDF renderiza e le metadata sem binario externo.
- OCR assincrono/Celery agora: descartado; fica para P13.
- Rodar todos os idiomas de `OCR_LANGS` em toda imagem: descartado por custo CPU; o primario e usado e os demais ficam disponiveis para selecao.
- Sinais como veredito de fraude: descartado; sao evidencias heurísticas.

## Consequencias
O primeiro OCR real pode baixar modelos e demorar; a imagem Docker cresce e precisa de libs de sistema para OpenCV GUI. O PP-OCRv6 no Windows/Paddle 3.3.1 falha no oneDNN com `NotImplemented`; o engine e criado com `enable_mkldnn=False` e roda em CPU, custando cerca de 19,6s e +444 MB RSS na fixture sintetica inicial. OCR e visao sao CPU-bound e podem estourar tempo; o limite e aplicado por pagina/documento, mas um thread de inferencia pode sobreviver ao timeout. Sinais visuais tem falsos positivos/negativos e devem ser combinados com o score deterministico em fases futuras. O uso de OpenCV GUI em vez de headless e necessario porque o PaddleOCR declara `opencv-contrib-python`; a alternativa seria um ambiente de dependencias customizado, adiado.
