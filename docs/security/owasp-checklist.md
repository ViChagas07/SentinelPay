# OWASP Top 10 (2021)

Ultima revisao: 2026-11-14 (P03). Cada item aponta o controle implementado e o teste/evidencia; o que nao pode ser validado esta marcado como NAO VALIDADO.

## A01:2021 - Broken Access Control

- **Status: NAO VALIDADO nesta fase.** Nao ha autenticacao/autorizacao nem rotas com dados de usuario; a P04 deve implementar JWT, ownership e RBAC.
- Rate limit e CSRF sao defesas auxiliares, nao substituem autorizacao.
- Evidencia: `docs/adr/0006-camadas-de-protecao.md`; testes de rate limit/CSRF em `backend/tests/unit/`.
- Pendencia: testes de IDOR e RBAC por rota.

## A02:2021 - Cryptographic Failures

- HSTS habilitado fora de `APP_ENV=local`; TLS/terminacao na borda continua **NAO VALIDADO**.
- Segredos ficam em `.env` ignorado; `.env.example` contem apenas placeholders. `SECURITY_HASH_SECRET` e obrigatorio fora de local.
- Chaves de rate limit/forca bruta sao pseudonimizadas com HMAC-SHA-256 no Redis; o valor bruto de IP/identificador nao e gravado.
- Evidencia: `backend/tests/unit/test_security_headers.py`, `backend/tests/unit/test_config.py`.
- Pendencia: politica de rotacao de segredos e TLS na CDN/proxy.

## A03:2021 - Injection

- SQL apenas por SQLAlchemy/parametros vinculados; a unica query da fase usa `CAST(:item_id AS uuid)` com bind.
- Teste de abuso com payloads classicos (`OR 1=1`, `DROP TABLE`, `UNION`) e XSS na rota de exemplo retorna 422, sem refletir a entrada e sem alterar `alembic_version`.
- Textos de usuario usam `PlainText` (sem `<`/`>`, sem controles, max 10k); API responde JSON/problem+json.
- Evidencia: `backend/tests/integration/test_injection_docker.py`, `backend/tests/unit/test_text_validation.py`, `backend/tests/unit/test_limits.py`.
- Pendencia: repetir o teste em cada filtro novo de negocio.

## A04:2021 - Insecure Design

- Rate limit Token Bucket atomico, cache SWR anti-stampede, forca bruta com backoff e guarda SSRF foram desenhados e testados; decisoes no ADR-0006.
- Testes de concorrencia: `backend/tests/integration/test_rate_limit_concurrency.py`, `backend/tests/integration/test_swr_cache.py`.
- Evidencia adicional: `backend/tests/unit/test_rate_limit_middleware.py`, `backend/tests/integration/test_bruteforce.py`, `backend/tests/unit/test_ssrf_guard.py`.

## A05:2021 - Security Misconfiguration

- Headers `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e CSP restritiva em todas as respostas; HSTS fora de local.
- TrustedHost e CORS com allowlist explicita; wildcard e rejeitado na configuracao. Swagger/Redoc/OpenAPI desativados fora de local.
- Evidencia: `backend/tests/unit/test_security_headers.py`, `backend/tests/unit/test_config.py`.
- Pendencia: revisar configuracao de proxy/CDN e exposicao de portas do Compose em producao.

## A06:2021 - Vulnerable and Outdated Components

- `pip-audit --local`: **nenhuma vulnerabilidade conhecida** em 2026-11-14; o comando avisa que o ambiente virtual local pode nao ser auditado integralmente (`PIPAPI_PYTHON_LOCATION`), entao a cobertura e **parcial**.
- `bandit -q -r src`: **0 achados** em 2026-11-14.
- Dependencias travadas em `backend/poetry.lock`; `paysentineliq` e ignorado pelo pip-audit por nao estar no PyPI.
- Evidencia: alvos `make audit` e `make bandit`.
- Pendencia: rodar auditoria no CI com SBOM e politica de atualizacao.

## A07:2021 - Identification and Authentication Failures

- Servico de forca bruta pronto: contadores por IP e identificador, janela, backoff exponencial e bloqueio temporario; falha do Redis e fail-closed.
- Rate limit em `/api/v1/auth/*` e fail-closed quando o Redis esta indisponivel.
- **Auth em si: NAO VALIDADO** (P04). Ainda nao ha login/JWT/refresh token.
- Evidencia: `backend/tests/unit/test_bruteforce_unit.py`, `backend/tests/integration/test_bruteforce.py`, `backend/tests/unit/test_rate_limit_middleware.py`.

## A08:2021 - Software and Data Integrity Failures

- Lockfile versionado; dependencias instaladas apenas do lock; nenhuma desserializacao insegura (pickle/yaml.load) no codigo de aplicacao.
- pip-audit sem vulnerabilidades conhecidas; assinatura/provenance de artefatos e SBOM **NAO VALIDADO**.
- Evidencia: `backend/poetry.lock`, `make audit`, `make bandit`.
- Pendencia: verificacao de assinatura/provenance no CI.

## A09:2021 - Security Logging and Monitoring Failures

- Logs JSON com `request_id`; filtro mascara CPF, CNPJ, e-mail, telefone, JWT, Bearer e chaves; access log do uvicorn desativado para nao imprimir query string.
- Rate limit e forca bruta registram falhas/degradacao sem IP ou identificador bruto.
- **Metricas/alertas e retencao: NAO VALIDADO** (sem backend de metricas nesta fase).
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
