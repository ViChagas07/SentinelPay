# MEMORY (memoria duravel do projeto)

Registre aqui apenas o que ajuda sessoes futuras: decisoes que valem sempre, armadilhas ja encontradas (com a causa), convencoes. Nada de segredos, nada de diario de tarefas (isso fica no PROGRESS.md).

## Decisoes duraveis
- Stack e fronteiras em ADR-0001; score deterministico em ADR-0002; `graphify-out/` fora do git em ADR-0003; MinIO local em ADR-0004.
- `.env` local guarda as credenciais e nunca e versionado; somente `.env.example` (placeholders) entra no git.
- A raiz do projeto e `SentinelPay/`. A antiga pasta `repo/` era uma duplicata dos arquivos de raiz e nao deve ser recriada.
- Codigo e identificadores em ingles; documentacao em pt-BR (RULES).
- O Compose local usa `--env-file .env.example` (nunca o `.env` de producao); o Makefile e o unico ponto de entrada dos comandos.
- O Makefile usa `poetry -C backend`; rode os alvos a partir da raiz.
- `make migrate` sempre executa `make backup` antes de `alembic upgrade head`; nao rode migration direto no ambiente de desenvolvimento.
- `make test-docker` executa `up` + `migrate` (com backup) antes dos testes; a imagem da API precisa ser rebuildada quando migrations novas forem adicionadas.
- Os testes forcam `APP_ENV=local` e URLs locais no `backend/conftest.py`, mesmo que exista configuracao de producao no ambiente.
- `httpx` e dependencia de runtime (usada pela guarda SSRF), nao apenas de teste; nao mover para o grupo dev.
- Fora de local, `SECURITY_HASH_SECRET` e obrigatorio para pseudonimizar chaves de rate limit/forca bruta; o `.env` de producao atual ainda precisa receber esse valor.
- O `instance` do problem+json usa o template da rota quando existe, para nao refletir payload/PII do path.
- Docs Swagger/Redoc/OpenAPI ficam desativados fora de `APP_ENV=local`.
- Auth: Google OIDC com PKCE/state/nonce; access JWT HS256; refresh opaco rotativo com apenas hash no banco e familia revogada em reuso; `require_role` usa a role do banco, nao apenas a claim.
- Authlib 1.9.5: `authlib.jose` esta depreciado; use joserfc. A integracao `httpx` do Authlib ainda funciona, mas avisa que sera trocada por `httpx2`.
- `JWT_SECRET` e `JWT_SECRET_KEY` sao aceitos como alias; fora de local tambem sao obrigatorios `SECURITY_HASH_SECRET`, `FRONTEND_URL` e as credenciais Google.
- Cookies: refresh `Path=/api/v1/auth`, CSRF `Path=/`, state OIDC `Path=/api/v1/auth/google`; `COOKIE_DOMAIN` e necessario se frontend e API estiverem em subdominios diferentes.
- Storage: boto3 sincrono via `asyncio.to_thread`; chaves geradas pelo sistema e nome original apenas sanitizado como metadado. Bucket privado com `AES256` e presign curto; MinIO local usa `MINIO_KMS_SECRET_KEY` (chave de desenvolvimento no `.env.example`).
- Upload: o path `/api/v1/documents/upload` e ignorado pelo `MaxBodySizeMiddleware` e tem `UploadSizeLimitMiddleware` proprio; nao remover os dois limites.
- Antivirus e lifecycle/versionamento do bucket sao portas/pendencias, nao implementacoes; nao declarar malware scanning como validado.
- OCR: PaddleOCR 3.7/PaddlePaddle 3.3.1 no Windows CPU precisa de `enable_mkldnn=False`; com PP-OCRv6 o oneDNN falha com `NotImplemented`. Modelos ficam em `~/.paddlex/official_models`, fora do repositorio.
- OpenCV GUI e headless nao devem coexistir: o PaddleOCR declara `opencv-contrib-python`; instalar headless junto deixa o pacote `cv2` quebrado. Use `pip install --force-reinstall --no-deps opencv-contrib-python==4.10.0.84` para reparar.
- Texto de OCR e dado nao confiavel e nunca deve virar instrucao; nao logar o texto completo.
- PaddleOCR 3.7 instala `httpx2`, e o Authlib passa a preferi-lo. `GoogleOIDCClient` aceita `oauth_transport` separado; testes OIDC usam `httpx2.MockTransport` para token e `httpx.MockTransport` para JWKS.
- O teste de OCR real e opt-in (`RUN_REAL_OCR=1` + `--run-docker`); `make test-docker` o pula. Modelos pt/es reais e OCR dentro do container ainda NAO VALIDADOS.
- P07: fontes de boleto sao `knowledge/febraban/manual_febraban_v1.pdf` e `knowledge/layouts/*.pdf`; `knowledge/` nao e versionado e nao deve ser alterado. O manual fixa fator 0=sem vencimento e 1..9999=07/10/1997+dias; nao ha reinicio de ciclo documentado. A tabela de exemplo do manual para 1000/4000/7000 conflita com a formula; vale a formula.
- P07: a lista de bancos vem de `febraban_banks_v1.json` com fonte por banco; nao escrever codigos de memoria. Bradesco usa modulo 11 no campo 3 da linha; os demais usam modulo 10. Linha de 48 digitos e NAO VERIFICAVEL alem do comprimento.
- P07: o `BarcodeDetector` do OpenCV 4.10 no Windows esta disponivel, mas nao decodificou um ITF sintetico gerado no host; leitura real de codigo de barras segue NAO VALIDADA. O adaptador retorna `not_found`/`not_validated` e a analise usa a linha digitavel.
- P07: o motor de regras so aceita fonte em `knowledge/febraban/` ou `knowledge/layouts/`; regra sem fonte e descartada. O subscore e risco (0 seguro, 100 maximo), com piso 80 para qualquer regra critica.

## Armadilhas conhecidas
- O `.env` atual aponta para servicos de producao. Nao rodar testes ou scripts locais contra ele; o Compose usa `.env.example`.
- MinIO sem KMS responde `NotImplemented` ao `ServerSideEncryption=AES256`; configurar `MINIO_KMS_SECRET_KEY` e recriar o container.
- `test_document_api` le `JWT_SECRET` do `.env.example` para assinar tokens aceitos pela API do Compose; se o segredo mudar, container e teste precisam ser atualizados juntos.
- AWS S3/IAM/SSE-KMS real, lifecycle/versionamento e antivirus continuam NAO VALIDADOS; o teste cobre MinIO local.
- A porta 5432 do host esta ocupada por um PostgreSQL local; o Compose mapeia o Postgres em `${POSTGRES_PORT}` (55432 no exemplo).
- Healthcheck do Mailpit: usar `/mailpit readyz`, pois o binario nao esta no PATH (senao falha com "executable file not found").
- `make test-docker` usa `API_BASE_URL` com default `http://localhost:8000`; se `API_PORT` mudar, exporte `API_BASE_URL` antes do alvo.
- As imagens oficiais do MinIO sairam do Docker Hub (404) e o Quay exige autenticacao (401); a imagem local e comunitaria e fixada (ADR-0004).
- O access log do uvicorn foi desativado (`--no-access-log`); ele nao passa pelo filtro de PII e poderia imprimir query string. Os logs da aplicacao continuam em JSON.
- A regex de telefone exige DDD; sem isso ela mascara segmentos de UUID `0000-0000` e corrompe `request_id`/paths nos logs.
- Ao adicionar migration, rebuild da imagem da API (`docker compose --env-file .env.example build api` + `make up`) antes de `make migrate`; o comando roda dentro do container.
- Graphify: use `graphify update .` para mudancas de codigo; a extracao semantica de docs pode recusar shrink e manter nos antigos, sem bloquear o grafo de codigo.
- Graphify com backend Gemini exige o extra `graphifyy[gemini]` (pacote `openai`); sem ele o chunk semantico falha com "the 'openai' package is required".
- `pip-audit --local` avisa que o venv pode nao ser auditado integralmente; para cobertura total, definir `PIPAPI_PYTHON_LOCATION` para o Python do `.venv`.
- Bandit B105 da falso positivo em nomes de variavel com `token`/`secret`; o segredo local e gerado em runtime e o script Lua foi renomeado para evitar o alerta.
- O transporte pinado da guarda SSRF substitui o pool privado `_pool` do httpx/httpcore; revalidar em upgrade dessas libs.
- O `GOOGLE_REDIRECT_URI` do `.env` de producao atual aponta para `/api/auth/google/callback`; a P04 usa `/api/v1/auth/google/callback` e o valor precisa ser corrigido antes de um deploy real.
- O fluxo real com Google nao foi executado (sem credenciais); testes usam token/JWKS mockados. Nao declarar login Google validado em producao.
- PowerShell 5.1 nao aceita `&&`; encadear comandos com `;` ou `if ($?)`.
- O Graphify ignora `.env` por seguranca e por `.gitignore`; o caminho aparece como ignorado na saida, o que e esperado.
