# OWASP Top 10 (2021)

Ultima revisao: 2026-11-14 (P03). Cada item aponta o controle implementado e o teste/evidencia; o que nao pode ser validado esta marcado como NAO VALIDADO.

## A01:2021 - Broken Access Control

- **Status: PARCIALMENTE VALIDADO.** Login Google OIDC/JWT, `get_current_user` por `sub` do token, `require_role` (`user`/`admin`) e rotas protegidas implementados. O `user_id` nunca vem de body/URL.
- A role de autorizacao vem do usuario carregado do banco; uma claim `role` divergente nao eleva privilegio.
- Testes: `backend/tests/unit/test_auth_routes.py` (anonimo 401, user 200, user em admin 403, token com role admin e banco user 403), `backend/tests/unit/test_jwt.py`.
- **Pendencia:** testes de IDOR por recurso de negocio e gestao administrativa de papeis ainda **NAO VALIDADOS** (fases futuras).

## A02:2021 - Cryptographic Failures

- HSTS habilitado fora de `APP_ENV=local`; TLS/terminacao na borda continua **NAO VALIDADO**.
- Segredos ficam em `.env` ignorado; `.env.example` contem apenas placeholders. `SECURITY_HASH_SECRET`, `JWT_SECRET` e credenciais Google sao obrigatorios fora de local.
- Access JWT HS256 com algoritmo fixo; refresh e opaco e somente o hash SHA-256 e persistido; cookies de refresh sao `HttpOnly`, `Secure` fora de local e `SameSite=Lax`.
- Chaves de rate limit/forca bruta sao pseudonimizadas com HMAC-SHA-256 no Redis; o valor bruto de IP/identificador nao e gravado.
- Evidencia: `backend/tests/unit/test_security_headers.py`, `backend/tests/unit/test_config.py`, `backend/tests/unit/test_jwt.py`, `backend/tests/unit/test_auth_routes.py`, `backend/tests/integration/test_auth_service_db.py`.
- Pendencia: rotacao de segredos, TLS na CDN/proxy e `COOKIE_DOMAIN` por ambiente.

## A03:2021 - Injection

- SQL apenas por SQLAlchemy/parametros vinculados; a unica query da fase usa `CAST(:item_id AS uuid)` com bind.
- Teste de abuso com payloads classicos (`OR 1=1`, `DROP TABLE`, `UNION`) e XSS na rota de exemplo retorna 422, sem refletir a entrada e sem alterar `alembic_version`.
- Textos de usuario usam `PlainText` (sem `<`/`>`, sem controles, max 10k); API responde JSON/problem+json.
- Evidencia: `backend/tests/integration/test_injection_docker.py`, `backend/tests/unit/test_text_validation.py`, `backend/tests/unit/test_limits.py`.
- Upload: nome original sanitizado nunca compoe a chave; tipo/extensao vem de magic bytes, nao de extensao/Content-Type. Evidencia: `backend/tests/unit/test_storage_keys.py`, `backend/tests/unit/test_document_inspector.py`, `backend/tests/integration/test_document_api.py`.
- OCR: texto reconhecido e dado nao confiavel, nao vira instrucao e nao e interpretado como campo. Evidencia: `backend/tests/unit/test_ingestion_service.py`.
- Pendencia: repetir o teste em cada filtro novo de negocio.

## A04:2021 - Insecure Design

- Rate limit Token Bucket atomico, cache SWR anti-stampede, forca bruta com backoff e guarda SSRF foram desenhados e testados; decisoes no ADR-0006.
- Testes de concorrencia: `backend/tests/integration/test_rate_limit_concurrency.py`, `backend/tests/integration/test_swr_cache.py`.
- Evidencia adicional: `backend/tests/unit/test_rate_limit_middleware.py`, `backend/tests/integration/test_bruteforce.py`, `backend/tests/unit/test_ssrf_guard.py`.
- Upload: tamanho e paginas limitados, PDF ativo/criptografado recusado, falha do banco compensa o objeto e nao deixa metadado orfao. Evidencia: `backend/tests/unit/test_document_service.py`, `backend/tests/unit/test_upload_limit.py`, `backend/tests/integration/test_document_upload.py`.
- OCR/visao: `OCR_MAX_PAGES`, DPI, timeout e teto de pixels limitam abuso; sinais visuais sao heuristicas e nao veredito. Evidencia: `backend/tests/unit/test_ingestion_service.py`, `backend/tests/unit/test_visual_anomalies.py`.

## A05:2021 - Security Misconfiguration

- Headers `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e CSP restritiva em todas as respostas; HSTS fora de local.
- TrustedHost e CORS com allowlist explicita; wildcard e rejeitado na configuracao. Swagger/Redoc/OpenAPI desativados fora de local.
- Evidencia: `backend/tests/unit/test_security_headers.py`, `backend/tests/unit/test_config.py`.
- Bucket S3 privado, sem ACL publica, com `AES256` por objeto e URL pre-assinada curta; MinIO local usa KMS de desenvolvimento. AWS/IAM/SSE-KMS real: **NAO VALIDADO**.
- Modelos PaddleOCR ficam em cache fora do repositorio; download/provenance dos modelos **NAO VALIDADO**.
- Pendencia: revisar configuracao de proxy/CDN e exposicao de portas do Compose em producao.

## A06:2021 - Vulnerable and Outdated Components

- `pip-audit --local`: **nenhuma vulnerabilidade conhecida** em 2026-11-14; o comando avisa que o ambiente virtual local pode nao ser auditado integralmente (`PIPAPI_PYTHON_LOCATION`), entao a cobertura e **parcial**.
- `bandit -q -r src`: **0 achados** em 2026-11-14.
- Dependencias travadas em `backend/poetry.lock`; `paysentineliq` e ignorado pelo pip-audit por nao estar no PyPI.
- Evidencia: alvos `make audit` e `make bandit`.
- Pendencia: rodar auditoria no CI com SBOM e politica de atualizacao.

## A07:2021 - Identification and Authentication Failures

- Login exclusivamente Google OIDC com authorization code + PKCE S256, state e nonce de uso unico, validacao de `iss`, `aud`, `exp` e `email_verified`.
- Access JWT curto HS256 com `jti` revogavel no Redis; refresh opaco rotativo por familia, com deteccao de reuso revogando a familia e apenas hash no banco.
- Rate limit e forca bruta cobrem as rotas de auth; falha do Redis em auth e fail-closed. CSRF double-submit protege refresh/logout por cookie.
- Evidencia: `backend/tests/unit/test_google_oidc.py`, `backend/tests/unit/test_jwt.py`, `backend/tests/unit/test_auth_service.py`, `backend/tests/unit/test_auth_routes.py`, `backend/tests/integration/test_auth_service_db.py`, `backend/tests/integration/test_revoked_tokens.py`.
- **NAO VALIDADO:** fluxo real com o Google (sem credenciais reais; JWKS/token mockados), MFA e recuperacao de conta. Nao ha cadastro por senha.

## A08:2021 - Software and Data Integrity Failures

- Lockfile versionado; dependencias instaladas apenas do lock; nenhuma desserializacao insegura (pickle/yaml.load) no codigo de aplicacao.
- SHA-256 do conteudo e metadados no Postgres; bucket/objetos sem ACL publica. Versionamento/lifecycle/retencao do bucket: **NAO VALIDADO**.
- Modelos PaddleOCR sao baixados do hoster oficial e ficam em `~/.paddlex`; checksums/provenance dos artefatos de modelo **NAO VALIDADOS**.
- pip-audit sem vulnerabilidades conhecidas; assinatura/provenance de artefatos e SBOM **NAO VALIDADO**.
- Evidencia: `backend/poetry.lock`, `make audit`, `make bandit`, `backend/tests/unit/test_document_service.py`, `backend/tests/integration/test_paddle_ocr_real.py`.
- Pendencia: verificacao de assinatura/provenance no CI.

## A09:2021 - Security Logging and Monitoring Failures

- Logs JSON com `request_id`; filtro mascara CPF, CNPJ, e-mail, telefone, JWT, Bearer e chaves; access log do uvicorn desativado para nao imprimir query string.
- Rate limit e forca bruta registram falhas/degradacao sem IP ou identificador bruto.
- **Metricas/alertas e retencao: NAO VALIDADO** (sem backend de metricas nesta fase).
- Texto OCR nao e logado integralmente; logs de ingestao nao incluem conteudo do documento.
- Evidencia: `backend/tests/unit/test_logging.py`, `backend/tests/unit/test_request_id.py`, `backend/tests/unit/test_rate_limit_middleware.py`.

## A10:2021 - Server-Side Request Forgery (SSRF)

- Guarda SSRF exige http/https (HTTPS em producao), rejeita credenciais, portas fora de 80/443 para URLs de usuario, IPs nao globais, loopback, link-local e metadados (`169.254.169.254`, `169.254.170.2`, `100.100.100.200`, `fd00:ec2::254`).
- DNS e revalidado por redirect; conexao TCP e fixada no IP validado via backend httpcore, reduzindo rebinding.
- Allowlist de infraestrutura fixa e separada de URLs de usuario.
- Evidencia: `backend/tests/unit/test_ssrf_guard.py`, `backend/tests/unit/test_safe_http_client.py`.
- Pendencias: somente o primeiro IP resolvido e tentado; politica de egress na borda **NAO VALIDADO**.

## DDoS (fora do OWASP Top 10)

- O app aplica rate limit, limite de corpo e timeout de requisicao.
- CDN/WAF, absorcao volumetrica e protecao de borda: **NAO VALIDADO**. Nao declarar o sistema como "protegido contra DDoS".

## Upload e armazenamento (P05)

- PDF/PNG/JPEG validados por magic bytes, SHA-256 e limite de tamanho em streaming; PDF tem limite de paginas e bloqueio de criptografia/JavaScript/arquivos embutidos com `evidence`.
- Chaves sao geradas pelo sistema (`users/{owner_id}/{kind}/{analysis_id}/original.{ext}`); nome original e sanitizado e salvo apenas como metadado. Repositorio e URL pre-assinada filtram pelo dono; IDOR retorna 404.
- Bucket privado, SSE `AES256`, presign curto e sem URL publica permanente. MinIO local criado pelo sistema; AWS real/IAM/SSE-KMS: **NAO VALIDADO**.
- **Antivirus/malware scanning: NAO VALIDADO.** A porta `AntivirusScanner` existe sem implementacao; arquivos estruturalmente validos ainda podem conter malware.
- Lifecycle, versionamento, retencao e quarentena de objetos: **NAO VALIDADO**.

## OCR e visao (P06)

- PDF nativo usa a camada de texto; PDF escaneado/imagem sao renderizados e passam pelo PaddleOCR. `OCR_MAX_PAGES`, `OCR_RENDER_DPI`, `OCR_TIMEOUT_SECONDS` e `OCR_MAX_IMAGE_PIXELS` limitam custo/abuso.
- Sinais heuristicos: qualidade (desfoque/resolucao/ruido), ELA, variancia de ruido por blocos, copy-move ORB e metadados de PDF. Cada sinal tem nome, valor 0..1, explicacao "Heuristic signal, not proof" e pagina/regiao quando aplicavel.
- Fixtures 100% sinteticas cobrem imagem limpa/borrada/pequena/colada, PDF nativo/escaneado/incremental/layers e todos os sinais. Nenhum documento real.
- OCR real validado apenas em CPU/Windows, idioma `en`, fixture sintetica: **19,6s** e **+444 MB RSS**. Modelos reais `pt`/`es`, inferencia dentro do container Docker e qualidade/limites com documentos reais: **NAO VALIDADOS**.
- **NAO VALIDADO:** integridade/provenance dos modelos baixados, OCR adversarial, antivirus do arquivo antes do OCR e analise forense pericial. Os sinais sao indicios, nao prova.
