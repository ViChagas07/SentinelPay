# Contrato da API do SentinelPay

Fase: F00 (descoberta).
Data: 2026-11-15.
Escopo: contrato observado no backend FastAPI em `backend/src/paysentineliq`, sem alterar nenhum arquivo fora de `frontend/`.

Este documento descreve apenas o que o backend oferece hoje. Rotas que o front-end venha a precisar e que não existem ficam em `frontend/docs/BACKEND_GAPS.md`, sempre marcadas como proposta. Nenhuma rota foi inventada aqui.

Índice:

1. Como este contrato foi levantado
2. Convenções transversais
3. Auth
4. Usuário e conta
5. Organização
6. Painel
7. Verificação e jobs
8. Boletos
9. Contracheques
10. Recibos e vencimentos
11. Notificações
12. Inteligência Antifraude
13. Busca
14. Infra e diagnóstico
15. Autenticação em detalhe
16. Análise de ponta a ponta
17. Classificação de risco
18. Catálogo de erros
19. Não validado

## 1. Como este contrato foi levantado

- Leitura direta dos routers em `backend/src/paysentineliq/interface/api/routes/`: `auth.py`, `users.py`, `protected.py`, `documents.py`, `analyses.py`, `payables.py`, `notifications.py`, `ops.py`, `example.py`.
- Leitura dos modelos Pydantic declarados nesses routers, das dependências em `interface/api/dependencies.py`, dos middlewares em `interface/api/main.py`, `limits.py`, `rate_limit.py`, `upload_limit.py`, `security_headers.py`, `middleware.py`, e dos handlers em `application/commands/` e `application/queries/`.
- Leitura dos enums e regras em `domain/analysis.py`, `domain/scoring.py`, `domain/payables.py`, `domain/notification.py`, `domain/document.py`, `domain/user.py`.
- Leitura da configuração em `infrastructure/config.py`, `.env.example` e `docker-compose.yml`.

Tentativa de baixar o `/openapi.json`:

- `docker compose --env-file .env.example ps` falhou porque o daemon do Docker Desktop não estava em execução (`npipe:////./pipe/dockerDesktopLinuxEngine` não encontrado).
- `GET http://localhost:8000/openapi.json` e `GET http://127.0.0.1:8000/openapi.json` falharam com conexão recusada.
- Conclusão: o OpenAPI gerado não pôde ser lido nesta sessão. O contrato abaixo vem do código, que é a fonte usada pelo próprio FastAPI. Itens que só o OpenAPI poderia confirmar ficam marcados em "Não validado".
- As docs interativas (`/docs`, `/redoc`, `/openapi.json`) só existem quando `APP_ENV=local` (`backend/src/paysentineliq/interface/api/main.py:152-160`). Fora de local elas são `None`.

## 2. Convenções transversais

| Item | Regra | Fonte no backend |
| --- | --- | --- |
| Prefixo | Todas as rotas de produto usam `/api/v1`. Saúde, prontidão e métricas ficam na raiz. | `interface/api/constants.py:1`, `interface/api/main.py:207-216` |
| Base local | API em `http://localhost:8000` (`API_PORT=8000`) e front-end em `http://localhost:3000` (`FRONTEND_URL` e `CORS_ALLOWED_ORIGINS`). | `.env.example`, `docker-compose.yml` (`api.ports`) |
| Formato | JSON UTF-8 nas respostas. Datas em `YYYY-MM-DD`; timestamps em ISO 8601 com timezone. UUIDs em string. | Modelos Pydantic dos routers |
| Autenticação | `Authorization: Bearer <access_token>` nas rotas protegidas. O access token é obtido em `POST /api/v1/auth/refresh`. | `interface/api/dependencies.py:409-439` |
| Erros | `application/problem+json` com `type`, `title`, `status`, `detail`, `instance`, `code` e `request_id`. Alguns erros acrescentam `evidence` e/ou `Retry-After`. | `interface/api/problems.py:40-72`, `interface/api/problems.py:75-100` |
| Rate limit | Token bucket por IP e, quando autenticado, também por usuário. Padrão: capacidade 60, recarga 1 token/s. Excedeu: 429 com `Retry-After`. Em rotas de auth, Redis indisponível falha fechado com 503. | `interface/api/rate_limit.py:15-101`, `infrastructure/config.py:65-66` |
| Corpo máximo | 1 MiB para JSON em geral. 25 MiB para `/api/v1/analyses` e `/api/v1/documents/upload`. | `interface/api/main.py:168-177`, `interface/api/limits.py:12-85`, `interface/api/upload_limit.py:26-88` |
| Páginas de PDF | Até 50 páginas por PDF no upload. | `infrastructure/config.py:131-132`, `infrastructure/storage/inspector.py` |
| Timeout de requisição | 30 s. Estourou: 504 `request_timeout`. A análise em si roda em worker, não dentro da requisição. | `interface/api/limits.py:98-116`, `infrastructure/config.py:75-76` |
| Request ID | O backend aceita `X-Request-ID` seguro (até 64 caracteres) ou gera um UUID, devolve no header e no problem+json. | `interface/api/middleware.py:17-60`, `interface/api/problems.py:49-65` |
| Paginação | Cursor opaco, sempre `next_cursor`. Não há paginação por offset nem total de itens. | `application/queries/analysis_cursor.py:10-43`, `application/queries/payables.py:20-57`, `application/queries/notifications.py:17-47` |
| Ordenação de análises | `created_at` decrescente. | `infrastructure/db/repositories/analysis_read.py` |
| Ordenação de vencimentos | `due_date` crescente, desempate por `id`. | `infrastructure/db/repositories/payables.py` |
| Ordenação de notificações | `created_at` decrescente. | `infrastructure/db/repositories/notifications.py` |
| Idempotência | Só em `POST /api/v1/analyses`, via `Idempotency-Key`. Mesma chave e mesmo arquivo devolvem o mesmo id; chave igual com arquivo diferente gera 409. | `application/commands/create_analysis.py:90-112`, `application/commands/create_analysis.py:208-214` |

O header `Idempotency-Replayed` é gravado na resposta, mas o CORS só expõe `X-Request-ID` (`interface/api/main.py:187-201`). Em chamada cross-origin, o JavaScript não consegue ler `Idempotency-Replayed`; o front-end deve detectar replay pelo mesmo `analysis_id` retornado e pelo estado do job.

Toda rota protegida também pode devolver 503 `security_service_unavailable` quando o Redis de revogação de token está indisponível, porque a checagem de `jti` falha fechado (`interface/api/dependencies.py:420-439`, `application/errors.py:31-38`).

Qualquer rota com path param UUID, query tipada ou corpo validado pode devolver 422 `validation_error` quando o formato é inválido (`interface/api/problems.py:103-114`). As tabelas abaixo listam apenas os 422 com código de negócio específico, além desse caso genérico.

## 3. Auth

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/auth/google/login` | Pública. Deve ser navegação de página inteira, não `fetch`. | Nenhum corpo. | 302 para o Google. Seta cookie `oidc_state` (HttpOnly, `Path=/api/v1/auth/google`, `SameSite=Lax`, `Max-Age=600`, `Secure` fora de local). | n/a | n/a | 429 `rate_limited`; 503 `auth_not_configured` ou `rate_limit_unavailable` | `interface/api/routes/auth.py:53-87`, `interface/api/auth_cookies.py:43-60` |
| GET | `/api/v1/auth/google/callback` | Pública, mas exige `code`, `state` igual ao cookie `oidc_state` e state existente no Redis. | Query `code`, `state`, `error` (opcionais no contrato do Google). | 303 para `FRONTEND_URL`. Seta `refresh_token` (HttpOnly, `Path=/api/v1/auth`, `SameSite=Lax`, `Max-Age=7 dias`, `Secure` fora de local) e `csrf_token` (legível por JS, `Path=/`, `SameSite=Lax`, `Secure` fora de local). Limpa `oidc_state`. Nenhum token vai na URL. | n/a | n/a | 400 `invalid_state`; 401 `google_auth_failed`; 403 `email_not_verified`; 429 `too_many_attempts` ou `rate_limited`; 503 `rate_limit_unavailable` ou `security_service_unavailable` | `interface/api/routes/auth.py:90-149`, `interface/api/auth_cookies.py:11-28`, `interface/api/csrf.py:17-32` |
| POST | `/api/v1/auth/refresh` | Cookie `refresh_token` mais CSRF double-submit: cookie `csrf_token` e header `X-CSRF-Token` com o mesmo valor. | Sem corpo. | 200 com `access_token`, `token_type` (`bearer`), `expires_in` (segundos) e `user` (`id`, `email`, `name`, `role`, `preferred_locale`, `timezone`). Rotaciona `refresh_token` e `csrf_token`. Em `invalid_refresh_token` ou `refresh_token_reuse`, limpa os cookies de auth. | n/a | n/a | 401 `invalid_refresh_token` ou `refresh_token_reuse`; 403 `csrf_invalid`; 429 `too_many_attempts` ou `rate_limited`; 503 `rate_limit_unavailable` ou `security_service_unavailable` | `interface/api/routes/auth.py:152-201`, `interface/api/csrf.py:43-52` |
| POST | `/api/v1/auth/logout` | CSRF double-submit. O access token é opcional e, se válido, tem o `jti` revogado. | Sem corpo. | 204 sem corpo. Revoga a família do refresh token quando o cookie existe. Limpa `refresh_token` e `csrf_token`. | n/a | n/a | 403 `csrf_invalid`; 503 `security_service_unavailable` | `interface/api/routes/auth.py:204-219`, `application/commands/auth.py:112-135`, `interface/api/auth_cookies.py:75-81` |

Observações de contrato:

- O login não devolve access token no callback. A página do front-end precisa chamar `POST /api/v1/auth/refresh` depois do redirect para obter o access token e os dados do usuário (`interface/api/routes/auth.py:131-148`).
- O refresh é rotativo e detecta reuso. Um token já revogado revoga a família inteira (`application/commands/auth.py:82-110`).
- O access token é JWT HS256 com claims `sub`, `role`, `jti`, `exp`, `iat`. TTL padrão de 15 minutos (`infrastructure/security/jwt.py:36-61`, `infrastructure/config.py:87-93`).
- O refresh token é opaco, aleatório, guardado somente como SHA-256 no banco, com validade padrão de 7 dias (`application/commands/auth.py:137-148`, `domain/refresh_token.py`).
- Força bruta: 5 tentativas por janela de 900 s, bloqueio base de 30 s e teto de 3600 s, por IP e por identificador (`infrastructure/config.py:77-80`, `interface/api/routes/auth.py:231-252`).
- O rate limit vale para todas as rotas `/api/v1`, inclusive auth (`interface/api/rate_limit.py:17-48`).

## 4. Usuário e conta

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/users/me` | Bearer | Nenhum. | `id`, `email`, `name` (pode ser nulo), `role` (`user` ou `admin`), `preferred_locale`, `timezone`. | n/a | n/a | 401 `invalid_access_token`; 429 `rate_limited` | `interface/api/routes/users.py:13-33`, `domain/user.py:6-8` |

Não existe endpoint para editar nome, locale, timezone, e-mail, foto, excluir conta, exportar dados ou listar sessões. O backend grava `preferred_locale` padrão `pt-BR` e `timezone` padrão `America/Sao_Paulo` (`infrastructure/db/models.py`, `UserModel`), mas não expõe alteração desses campos fora do `PUT /api/v1/notification-preferences`, que muda o locale como efeito colateral (`application/commands/notifications.py:73-107`).

## 5. Organização

Nenhum endpoint. O backend é single-user por dono: todas as consultas filtram por `owner_id` vindo do JWT. Não existe modelo de organização, membros, convites, papéis por organização, cobrança ou uso por tenant. Evidência: os routers registrados em `interface/api/main.py:207-216` e as tabelas em `infrastructure/db/models.py` não têm entidade de organização. A ausência está registrada em `BACKEND_GAPS.md`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n/a | Nenhuma rota de organização | n/a | n/a | n/a | n/a | n/a | n/a | `interface/api/main.py:207-216`, `infrastructure/db/models.py` |

## 6. Painel

Nenhum endpoint de estatística, série temporal, totais ou agregação. O que existe são listas paginadas por cursor, sem total: `GET /api/v1/analyses`, `GET /api/v1/payables` e `GET /api/v1/notifications`. Não dá para montar contadores confiáveis no front-end apenas paginando, porque não há total nem agregação. Evidência: `interface/api/routes/analyses.py:124-147`, `interface/api/routes/payables.py:121-142`, `interface/api/routes/notifications.py:122-141`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n/a | Nenhuma rota de painel ou estatística | n/a | n/a | n/a | n/a | n/a | n/a | `interface/api/main.py:207-216` |

## 7. Verificação e jobs

A verificação é assíncrona. O upload e a criação do job acontecem em uma única chamada multipart.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/analyses` | Bearer | `multipart/form-data` com `kind` (`boleto`, `payslip` ou `receipt`) e `file` (PDF, PNG ou JPEG). Header opcional `Idempotency-Key` com 8 a 128 caracteres do conjunto `A-Z a-z 0-9 . _ : -`. Header `Accept-Language` define o locale do job. | 202 com `analysis_id` e `status` (`queued`). Em replay idempotente, header `Idempotency-Replayed: true`. | n/a | n/a | 401 `invalid_access_token`; 409 `idempotency_conflict`; 413 `upload_too_large`; 422 `empty_document`, `unsupported_document_type`, `invalid_document`, `pdf_page_limit_exceeded`, `encrypted_pdf`, `pdf_active_content` (com `evidence`), `invalid_idempotency_key` ou `validation_error`; 429 `analysis_quota_exceeded` ou `rate_limited`; 503 `storage_not_configured`, `storage_unavailable` ou `task_dispatch_failed`; 504 `request_timeout` | `interface/api/routes/analyses.py:96-121`, `application/commands/create_analysis.py:86-200` |
| GET | `/api/v1/analyses` | Bearer | Nenhum corpo. Query `limit` (1 a 50, padrão 20) e `cursor`. | `items[]` com `id`, `status`, `kind`, `score` (nulo até terminar), `band` (nula até terminar), `error_code`, `created_at`, `updated_at`; mais `next_cursor`. | Cursor opaco. | Nenhum filtro por tipo, status, banda, período ou texto. | 401 `invalid_access_token`; 422 `invalid_cursor` ou `validation_error`; 429 `rate_limited` | `interface/api/routes/analyses.py:80-93`, `interface/api/routes/analyses.py:124-147` |
| GET | `/api/v1/analyses/{analysis_id}` | Bearer. O dono vem do JWT, nunca da URL. | Nenhum corpo. | `id`, `status`, `kind`, `created_at`, `updated_at`, `error_code`, `result_available`, `result` (nulo ou objeto), conforme tabela de resultado abaixo. | n/a | n/a | 401 `invalid_access_token`; 404 `analysis_not_found`; 429 `rate_limited`; 503 `storage_not_configured` | `interface/api/routes/analyses.py:150-194`, `application/queries/analyses.py:72-121` |

Estados exatos do job (`domain/analysis.py:11-16`):

| Status | Significado |
| --- | --- |
| `queued` | Job criado, documento persistido, aguardando worker. Também é o estado após um retry agendado. |
| `processing` | Worker reivindicou o job com `task_id` e lease. |
| `completed` | Terminou sem flags de degradação. |
| `degraded` | Terminou com resultado, mas com uma ou mais flags de degradação (por exemplo, LLM indisponível). |
| `failed` | Terminou em erro terminal. O motivo fica em `error_code`. |

Não existe status `cancelled`. `retry_scheduled` é tipo de evento, não status de job (`domain/analysis.py:19-28`). O retry volta o job para `queued` (`application/commands/process_analysis.py:97-123`, `infrastructure/db/repositories/analyses.py`).

Como acompanhar progresso:

- Somente polling em `GET /api/v1/analyses/{analysis_id}` ou na lista. Não há SSE, WebSocket, `StreamingResponse` ou endpoint de eventos. Evidência: não existe rota de eventos em `interface/api/routes/` e não há `WebSocket`/`text/event-stream` no backend.
- O detalhe não expõe etapa atual, percentual, tentativa nem início de processamento. Durante `processing`, a única informação é o próprio status.
- O histórico de eventos existe no banco (`analysis_events`), mas não tem endpoint de leitura no contrato atual.

Formato de `result` quando `result_available` é `true` (`interface/api/routes/analyses.py:50-77`, `application/queries/analyses.py:164-217`):

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `score` | inteiro 0 a 100 | Score final devolvido pelo backend. É ele que vale. |
| `band` | `low`, `attention` ou `high` | Classe final devolvida pelo backend. O front-end não recalcula. |
| `base_score` | inteiro 0 a 100 | Score antes do ajuste do LLM. |
| `llm_adjustment` | inteiro 0 a 20 | Ajuste somado pelo LLM. Nunca reduz e nunca passa de 20. |
| `evidence[]` | lista | `rule_id`, `severity` (`critical`, `high`, `medium`, `low`, `info`), `weight`, `message_key`, `source`. Máximo de 50 itens na resposta. |
| `justification` | string | Texto pronto para exibição, em até 4000 caracteres. Pode vir do LLM ou de template de fallback. |
| `inconsistencies[]` | lista de strings | Até 5 itens. |
| `degradation_flags[]` | lista de strings | Até 20 itens. Valores possíveis na tabela abaixo. |

Se a leitura do relatório no bucket falhar, `GET /api/v1/analyses/{analysis_id}` não devolve erro: responde 200 com `result_available=false` e `result=null` (`application/queries/analyses.py:104-121`). A tela deve tratar isso como resultado indisponível, não como análise sem risco.

Flags de degradação (`domain/analysis.py:30-38`):

| Flag | Significado |
| --- | --- |
| `llm_unavailable` | LLM indisponível. |
| `rag_unavailable` | Base de conhecimento indisponível. |
| `ml_unavailable` | Modelo de ML indisponível. |
| `prompt_injection_detected` | Tentativa de injeção detectada no documento. |
| `guardrail_classifier_unavailable` | Classificador de injeção indisponível. |
| `llm_output_rejected` | Saída do LLM reprovada pelos guardrails. |
| `llm_judge_unavailable` | Judge do LLM indisponível. |
| `llm_judge_rejected` | Judge reprovou a saída do LLM. |

Códigos de erro de uma análise `failed` (`application/commands/process_analysis.py:136-157`):

`analysis_timeout`, `unsupported_document`, `document_not_found`, `invalid_document`, `llm_unavailable`, `rag_unavailable`, `storage_unavailable`, `ocr_unavailable`, `embedding_unavailable`, `upload_too_large`, `analysis_failed`.

O que o detalhe não devolve hoje:

- Campos extraídos do documento. O relatório JSON gravado no bucket tem `fields`, mas o `AnalysisResultResponse` não inclui `fields` (`domain/analysis.py:149-176`, `application/queries/analyses.py:164-192`, `interface/api/routes/analyses.py:58-77`).
- `document_id`, nome do arquivo, URL do documento original ou preview.
- `rule_set_version`, `model_versions`, `report_s3_key`.
- Coordenadas de evidência, página ou região.

### 7.1 Documentos (upload legado)

Estas duas rotas existem, mas não criam job de análise. `POST /documents/upload` grava o documento e devolve um `analysis_id` que não é persistido em `analyses`; ele só compõe a chave do S3 (`application/commands/documents.py:143-172`). O fluxo de produto deve usar `POST /api/v1/analyses`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/documents/upload` | Bearer | `multipart/form-data` com `kind` (`bank_slip`, `payslip` ou `receipt`) e `file`. Aceita PDF, PNG e JPEG. | 201 com `id`, `analysis_id`, `kind`, `sha256`, `size`, `content_type`, `original_name_sanitized`, `created_at`. | n/a | n/a | 401 `invalid_access_token`; 413 `upload_too_large`; 422 `empty_document`, `unsupported_document_type`, `invalid_document`, `pdf_page_limit_exceeded`, `encrypted_pdf`, `pdf_active_content` ou `validation_error`; 429 `rate_limited`; 503 `storage_not_configured` ou `storage_unavailable` | `interface/api/routes/documents.py:43-71`, `application/commands/documents.py:122-172` |
| GET | `/api/v1/documents/{document_id}/url` | Bearer. O dono vem do JWT. | Nenhum corpo. | `url` assinada e `expires_in` em segundos (padrão 300). | n/a | n/a | 401 `invalid_access_token`; 404 `document_not_found`; 429 `rate_limited`; 503 `storage_not_configured` ou `storage_unavailable` | `interface/api/routes/documents.py:74-89`, `application/queries/documents.py:20-58` |

## 8. Boletos

Não existe rota específica de boleto. Boleto é o `kind=boleto` de `POST /api/v1/analyses`; a listagem e o detalhe usam as rotas de análises (`interface/api/routes/analyses.py:32-42`).

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/analyses` | Bearer | `kind=boleto` mais arquivo. | Igual à seção de jobs. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:96-121` |
| GET | `/api/v1/analyses` | Bearer | `limit`, `cursor`. | Itens com `kind` igual a `boleto`. | Cursor. | Nenhum filtro por `kind`; o front-end teria que filtrar no cliente, com paginação incompleta. | Igual à seção de jobs. | `interface/api/routes/analyses.py:124-147` |
| GET | `/api/v1/analyses/{analysis_id}` | Bearer | Nenhum. | Resultado sem os campos extraídos do boleto. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:150-157` |

Os campos extraídos de boleto existem no relatório interno: `line`, `barcode`, `amount`, `due_date`, `beneficiary`, `beneficiary_tax_id`, `payer`, `payer_tax_id`, `additional_tax_ids`, `bank_header` e `decoded` (`infrastructure/ai/report.py:36-63`). Eles não são expostos pela API atual. A tela de boleto depende dessa lacuna, registrada em `BACKEND_GAPS.md`.

## 9. Contracheques

Não existe rota específica de contracheque. Contracheque é o `kind=payslip` de `POST /api/v1/analyses`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/analyses` | Bearer | `kind=payslip` mais arquivo. | Igual à seção de jobs. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:96-121` |
| GET | `/api/v1/analyses` | Bearer | `limit`, `cursor`. | Itens com `kind` igual a `payslip`. | Cursor. | Nenhum filtro por `kind`. | Igual à seção de jobs. | `interface/api/routes/analyses.py:124-147` |
| GET | `/api/v1/analyses/{analysis_id}` | Bearer | Nenhum. | Resultado sem os campos extraídos do contracheque. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:150-157` |

Os campos internos de contracheque incluem `employer_name`, `employer_cnpj`, `employee_name`, `employee_cpf_masked`, `employee_cpf_valid`, `competency`, `items[]`, `total_earnings`, `total_deductions`, `net`, `irrf_base`, `dependents` e `layout_confidence` (`infrastructure/ai/report.py:66-102`). Não são expostos pela API atual.

As evidências de contracheque têm no domínio um `status` (`triggered` ou `not_verifiable`), mas a resposta da API só devolve `rule_id`, `severity`, `weight`, `message_key` e `source`. O front-end não consegue distinguir uma regra disparada de uma regra não verificável (`domain/payslip/analysis.py`, `domain/payslip/rules.py:19-21`). Lacuna registrada em `BACKEND_GAPS.md`.

## 10. Recibos e vencimentos

### 10.1 Recibos

Não existe rota específica de recibo. Recibo é o `kind=receipt` de `POST /api/v1/analyses`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/analyses` | Bearer | `kind=receipt` mais arquivo. | Igual à seção de jobs. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:96-121` |
| GET | `/api/v1/analyses` | Bearer | `limit`, `cursor`. | Itens com `kind` igual a `receipt`. | Cursor. | Nenhum filtro por `kind`. | Igual à seção de jobs. | `interface/api/routes/analyses.py:124-147` |
| GET | `/api/v1/analyses/{analysis_id}` | Bearer | Nenhum. | Resultado sem os campos extraídos do recibo. | n/a | n/a | Igual à seção de jobs. | `interface/api/routes/analyses.py:150-157` |

Os campos internos de recibo incluem `line`, `barcode`, `amount`, `due_date`, `issuer`, `reference`, `decoded`, `barcode_checked` e `not_validated` (`infrastructure/ai/report.py:131-163`). Não são expostos pela API atual.

### 10.2 Vencimentos (payables)

Um recibo analisado pode gerar um vencimento quando o valor e a data foram extraídos com confiança maior ou igual a 0,5 e o risco não é alto (`infrastructure/ai/graph.py:847-881`). O status inicial depende da banda: `low` gera `pending`; `attention` ou injeção detectada gera `pending_confirmation`; `high` não gera vencimento (`domain/payables.py:75-84`).

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/payables/reminder-preferences` | Bearer | Nenhum. | `offsets_days[]`, `local_time`, `channels[]`, `timezone`. | n/a | n/a | 401 `invalid_access_token`; 429 `rate_limited` | `interface/api/routes/payables.py:81-95` |
| PUT | `/api/v1/payables/reminder-preferences` | Bearer | Substitui tudo: `offsets_days[]` (1 a 31 valores únicos entre 0 e 30), `local_time` (`HH:MM:SS`) e `channels[]` (hoje só `in_app`). | Igual ao GET. | n/a | n/a | 401; 422 `validation_error`; 429 | `interface/api/routes/payables.py:49-118`, `domain/payables.py:17-23` |
| GET | `/api/v1/payables` | Bearer | Query `status` repetível (`pending_confirmation`, `pending`, `paid`, `overdue`, `dismissed`), `due_from`, `due_to`, `limit` (1 a 50, padrão 20), `cursor`. | `items[]` com `id`, `analysis_id`, `description`, `amount` (string decimal com duas casas), `due_date`, `status`, `created_at`, `updated_at`; mais `next_cursor`. | Cursor opaco por `(due_date, id)`. | Status, intervalo de vencimento. Não há filtro por texto, valor, análise ou tipo. | 401; 422 `invalid_cursor` ou `validation_error`; 429 | `interface/api/routes/payables.py:29-43`, `interface/api/routes/payables.py:121-142`, `application/queries/payables.py:20-57` |
| POST | `/api/v1/payables/{payable_id}/confirm` | Bearer | Nenhum. | O vencimento atualizado. | n/a | n/a | 401; 404 `payable_not_found`; 409 `payable_invalid_state`; 429 | `interface/api/routes/payables.py:145-151`, `infrastructure/db/repositories/payables.py` |
| POST | `/api/v1/payables/{payable_id}/pay` | Bearer | Nenhum. | O vencimento atualizado com `status=paid`. | n/a | n/a | 401; 404; 409; 429 | `interface/api/routes/payables.py:154-160` |
| POST | `/api/v1/payables/{payable_id}/dismiss` | Bearer | Nenhum. | O vencimento atualizado com `status=dismissed`. | n/a | n/a | 401; 404; 409; 429 | `interface/api/routes/payables.py:163-169` |
| PATCH | `/api/v1/payables/{payable_id}/due-date` | Bearer | `{"due_date": "YYYY-MM-DD"}`. | O vencimento atualizado. | n/a | n/a | 401; 404; 409 `payable_invalid_state`; 422 `validation_error`; 429 | `interface/api/routes/payables.py:45-47`, `interface/api/routes/payables.py:172-179` |

Transições (`infrastructure/db/repositories/payables.py`):

- `confirm` só aceita `pending_confirmation` e leva para `pending`.
- `pay` e `dismiss` aceitam `pending_confirmation`, `pending` e `overdue`.
- `reschedule` aceita os mesmos três status ativos; data igual devolve o item sem alteração; data diferente cancela lembretes pendentes antigos.
- `paid` e `dismissed` são terminais; tentar transicionar gera 409 `payable_invalid_state`.

Não existe `GET /api/v1/payables/{payable_id}`. Isso importa porque o payload de notificação de vencimento traz `payable_id`, mas não descrição nem valor; sem o GET individual, a central de notificações não consegue abrir o item diretamente. Lacuna registrada em `BACKEND_GAPS.md`.

## 11. Notificações

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/notifications/unread-count` | Bearer | Nenhum. | `{"unread": <inteiro>}`. | n/a | n/a | 401; 429 | `interface/api/routes/notifications.py:103-108` |
| POST | `/api/v1/notifications/read-all` | Bearer | Nenhum. | `{"updated": <inteiro>}`. | n/a | n/a | 401; 429 | `interface/api/routes/notifications.py:111-119` |
| GET | `/api/v1/notifications` | Bearer | Query `type` repetível, `unread` booleano, `limit` (1 a 50, padrão 20), `cursor`. | `items[]` com `id`, `type`, `payload` (objeto string para string), `read`, `read_at`, `created_at`; mais `next_cursor`. | Cursor opaco. | Tipo e não lidas. | 401; 422 `invalid_cursor` ou `validation_error`; 429 | `interface/api/routes/notifications.py:37-49`, `interface/api/routes/notifications.py:122-141` |
| POST | `/api/v1/notifications/{notification_id}/read` | Bearer | Nenhum. | A notificação atualizada. | n/a | n/a | 401; 404 `notification_not_found`; 429 | `interface/api/routes/notifications.py:144-153` |
| DELETE | `/api/v1/notifications/{notification_id}` | Bearer | Nenhum. | 204 sem corpo. | n/a | n/a | 401; 404 `notification_not_found`; 429 | `interface/api/routes/notifications.py:156-165` |
| GET | `/api/v1/notification-preferences` | Bearer | Nenhum. | `locale`, `timezone`, `channels[]` com `channel`, `enabled`, `destination` mascarado e `consented_at`. | n/a | n/a | 401; 429 | `interface/api/routes/notifications.py:97-100`, `interface/api/routes/notifications.py:168-176` |
| PUT | `/api/v1/notification-preferences` | Bearer | Substitui tudo: `locale` opcional e objetos `email`, `sms`, `whatsapp`, cada um com `enabled`, `destination` e `consent`. | Igual ao GET. | n/a | n/a | 401; 422 `invalid_locale`, `invalid_notification_preference` ou `validation_error`; 429 | `interface/api/routes/notifications.py:59-87`, `interface/api/routes/notifications.py:179-212` |

Tipos de notificação (`domain/notification.py:22-29`):

`analysis_completed`, `high_risk_detected`, `receipt_analyzed`, `payable_due_soon`, `payable_due_today`, `payable_overdue`, `payable_due_reminder`.

Canais de entrega (`domain/notification.py:39-43`): `email`, `sms`, `whatsapp`. Os lembretes dentro do app usam `NotificationChannel.IN_APP` (`domain/payables.py:17-19`), que é distinto de `DeliveryChannel`.

Payload por tipo, construído no backend:

- Notificações de análise: `analysis_id`, `document_type`, `status`, `score`, `band` (`infrastructure/ai/graph.py:1002-1013`).
- Notificações de vencimento: `payable_id`, `due_date`, `offset_days` (nos lembretes), `type` e `channel` (`in_app`) (`infrastructure/db/repositories/payables.py`).
- Não há título nem corpo renderizado na resposta da Central. O front-end monta o texto a partir de `type` e `payload`.
- `GET /api/v1/notifications` não devolve status de entrega por canal. As entregas existem em `notification_deliveries`, mas não há endpoint de leitura (`domain/notification.py:127-143`, `infrastructure/db/repositories/notifications.py`).

Preferências:

- Sem linha salva, o canal de e-mail volta habilitado por padrão para o e-mail da conta, e SMS e WhatsApp voltam desabilitados (`infrastructure/db/repositories/notifications.py`, `_email_preference` e `_phone_preference`).
- O `PUT` é substituição completa dos três canais. Enviar apenas SMS desabilita e-mail se `email.enabled=false` for enviado.
- O destino de e-mail é sempre o e-mail da conta e volta mascarado no GET; o destino enviado em `email.destination` é ignorado (`application/commands/notifications.py:85-96`).
- SMS e WhatsApp exigem E.164, `enabled` com `consent=true` e destino preenchido (`interface/api/routes/notifications.py:78-87`).
- O `locale` aceito pelo backend é o conjunto de 9 locales de `application/locale.py:1-12`. O front-end deste produto usa apenas `pt-BR`, `es` e `en` por decisão de produto, mas o backend aceita os demais.
- `PUT /api/v1/notification-preferences` altera `users.preferred_locale`; não existe `PATCH /api/v1/users/me` para locale (`application/commands/notifications.py:99-102`).

## 12. Inteligência Antifraude

Nenhum endpoint de catálogo, explicação de regra, fonte de conhecimento, versão de modelo, métrica de modelo ou feedback. A inteligência aparece apenas como resultado de uma análise em `GET /api/v1/analyses/{analysis_id}`.

O backend tem internamente:

- Regras versionadas de boleto (`febraban-v1`), contracheque (`payslip-v1`) e recibo (`receipt-v1`), com `rule_id`, `severity`, `weight`, `message_key` e `source` (`domain/boleto/rules.py`, `domain/payslip/rules.py`, `domain/receipt/rules.py`).
- Fusão determinística, ML e visual (`domain/scoring.py:117-170`).
- RAG e LLM que explicam, mas não decidem o score (`infrastructure/ai/graph.py`, `docs/adr/0002-score-deterministico.md`).
- Guardrails cujos achados viram evidências `guardrail.*` com peso 0 (`application/security/guardrails.py`).

Nada disso tem rota própria de leitura. As lacunas para a tela de Inteligência estão em `BACKEND_GAPS.md`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n/a | Nenhuma rota de catálogo, regra, fonte, modelo ou feedback | n/a | n/a | n/a | n/a | n/a | n/a | `interface/api/main.py:207-216` |

## 13. Busca

Nenhum endpoint de busca global, sugestão, busca por beneficiário, por descrição de vencimento ou por texto de documento. As listas só aceitam cursor e, no caso de vencimentos e notificações, filtros de status e tipo. Evidência: `interface/api/routes/analyses.py:124-130`, `interface/api/routes/payables.py:121-130`, `interface/api/routes/notifications.py:122-130`.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n/a | Nenhuma rota de busca | n/a | n/a | n/a | n/a | n/a | n/a | `interface/api/main.py:207-216` |

## 14. Infra e diagnóstico

Estas rotas não são telas de produto, mas o front-end pode precisar de `health` e `ready` em diagnóstico interno.

| Método | Rota | Auth exigida | Request | Response | Paginação | Filtros | Erros | Fonte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Pública | Nenhum. | `{"status": "ok"}`. Não toca banco nem Redis. | n/a | n/a | 405 para método errado | `interface/api/routes/ops.py:16-22` |
| GET | `/ready` | Pública | Nenhum. | 200 `{"status":"ready","checks":{"postgres":true,"redis":true}}` ou 503 `not_ready` com os checks falsos. | n/a | n/a | 503 | `interface/api/routes/ops.py:25-40` |
| GET | `/metrics` | Bearer ou `X-Metrics-Token` iguais a `METRICS_TOKEN`. Fora do schema OpenAPI. | Nenhum. | Texto Prometheus. | n/a | n/a | 401 `metrics_unauthorized`; 503 `metrics_unavailable` | `interface/api/routes/ops.py:43-72` |
| GET | `/api/v1/protected/user` | Bearer | Nenhum. | `user_id`, `role`. Rota de verificação de RBAC. | n/a | n/a | 401 `invalid_access_token`; 429 `rate_limited` | `interface/api/routes/protected.py:21-25` |
| GET | `/api/v1/protected/admin` | Bearer com papel `admin` | Nenhum. | `user_id`, `role`. Rota de verificação de RBAC. | n/a | n/a | 401 `invalid_access_token`; 403 `forbidden`; 429 `rate_limited` | `interface/api/routes/protected.py:28-32` |
| GET | `/api/v1/example/{item_id}` | Pública. Rota de demonstração. | UUID no path. | `item_id`, `status`, `locale`, `request_id`. | n/a | n/a | 404 `document_not_found` | `interface/api/routes/example.py:12-43` |

As rotas `protected` e `example` são de verificação e demonstração, não devem ser usadas em telas de produto.

## 15. Autenticação em detalhe

### 15.1 Fluxo Google OIDC

1. O navegador abre `GET /api/v1/auth/google/login` (`interface/api/routes/auth.py:53-87`).
2. O backend gera `state`, `nonce` e `code_verifier`, guarda no Redis com TTL de 600 s e monta a URL do Google com PKCE S256 (`application/ports/oidc_state.py`, `infrastructure/security/google_oidc.py`). Authlib 1.9.5 monta a URL e troca o code; a validação do ID token usa joserfc, porque `authlib.jose` está depreciado (`docs/adr/0007-autenticacao.md`).
3. O backend seta o cookie `oidc_state` e responde 302 para o Google (`interface/api/auth_cookies.py:43-60`).
4. O Google volta para `GOOGLE_REDIRECT_URI`, que deve ser `/api/v1/auth/google/callback` (`.env.example`, `infrastructure/config.py:101-110`).
5. O callback compara `state` da query com o cookie em tempo constante, consome o state do Redis e troca o `code` (`interface/api/routes/auth.py:102-129`).
6. O ID token RS256 é validado com joserfc contra o JWKS do Google, incluindo assinatura, `iss`, `aud`, `exp`, `nonce` e `email_verified` (`infrastructure/security/google_oidc.py`, `docs/adr/0007-autenticacao.md`).
7. O usuário é criado ou atualizado por `google_sub` (`application/commands/auth.py:52-80`).
8. O backend responde 303 para `FRONTEND_URL` setando `refresh_token` e `csrf_token` (`interface/api/routes/auth.py:134-149`).
9. O front-end, na página de destino, chama `POST /api/v1/auth/refresh` com `X-CSRF-Token` lido do cookie `csrf_token` e com `credentials: "include"` (`interface/api/routes/auth.py:152-201`).
10. O backend devolve o access token no corpo e rotaciona os cookies.

O access token nunca é colocado em URL, em cookie ou em `localStorage` pelo backend. O contrato só garante que ele sai no corpo do refresh.

### 15.2 Expiração, refresh e logout

- Access token: 15 minutos por padrão (`ACCESS_TOKEN_TTL_MINUTES=15`).
- Refresh token: 7 dias por padrão (`REFRESH_TOKEN_TTL_DAYS=7`), rotativo a cada refresh.
- Reuso de refresh revogado: 401 `refresh_token_reuse` e revogação da família.
- Logout: revoga a família do refresh e, se houver Bearer válido, revoga o `jti` no Redis até o `exp`.
- Redis indisponível em auth: falha fechado com 503 `security_service_unavailable` ou `rate_limit_unavailable` (`docs/adr/0007-autenticacao.md`, `interface/api/rate_limit.py:66-80`).
- Revogação de access token é por `jti`, não por usuário. Não há "logout de todos os dispositivos".

### 15.3 Cookies e CORS

Configuração no backend (`interface/api/main.py:187-201`, `infrastructure/config.py:73-74`, `infrastructure/config.py:108-110`, `interface/api/auth_cookies.py`):

| Cookie | Atributos em dev (`APP_ENV=local`) | Atributos fora de local |
| --- | --- | --- |
| `refresh_token` | HttpOnly, `SameSite=Lax`, `Path=/api/v1/auth`, `Secure=false`, `Domain` vazio, `Max-Age=604800` | HttpOnly, `SameSite=Lax`, `Path=/api/v1/auth`, `Secure=true`, `Domain=COOKIE_DOMAIN` se configurado, `Max-Age=604800` |
| `csrf_token` | Não HttpOnly, `SameSite=Lax`, `Path=/`, `Secure=false`, `Domain` vazio | Não HttpOnly, `SameSite=Lax`, `Path=/`, `Secure=true` |
| `oidc_state` | HttpOnly, `SameSite=Lax`, `Path=/api/v1/auth/google`, `Secure=false`, `Max-Age=600` | HttpOnly, `SameSite=Lax`, `Path=/api/v1/auth/google`, `Secure=true` |

CORS:

- `allow_origins` vem de `CORS_ALLOWED_ORIGINS`, exato, sem wildcard. O default local é `http://localhost:3000` (`infrastructure/config.py:74`, `infrastructure/config.py:403-408`).
- `allow_credentials=true`.
- Métodos: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
- Headers permitidos: `Authorization`, `Content-Type`, `Accept-Language`, `X-Request-ID`, `Idempotency-Key`, `X-CSRF-Token`.
- Header exposto: `X-Request-ID`.
- `TrustedHostMiddleware` também valida `Host`, com allowlist e sem wildcard (`interface/api/main.py:183-186`, `infrastructure/config.py:73`, `infrastructure/config.py:403-406`).
- Em dev, front-end em `http://localhost:3000` e API em `http://localhost:8000` são same-site (mesmo host, portas diferentes). O cookie host-only de `localhost` é enviado para a API quando a chamada usa `credentials: "include"`.
- Em produção, o cookie é gravado no host da API. Se o front-end chama a API diretamente em `api.exemplo.com`, o cookie host-only funciona. Se for necessário compartilhar cookie entre subdomínios, configurar `COOKIE_DOMAIN`. Se o front-end e a API estiverem em sites diferentes (domínios registráveis diferentes), `SameSite=Lax` impede o envio do cookie em requisições cross-site e o refresh não funciona; nesse caso, use proxy reverso no mesmo site.
- `Secure=true` fora de local exige HTTPS. HSTS é habilitado fora de local (`interface/api/security_headers.py:21-25`).
- `CORS_ALLOWED_ORIGINS` deve conter exatamente a origem do front-end, incluindo esquema e porta. Não há regex nem curinga.

Consequências práticas para o front-end:

- Toda chamada autenticada usa `Authorization: Bearer`.
- `POST /auth/refresh` e `POST /auth/logout` precisam de `credentials: "include"` e do header `X-CSRF-Token` lido do cookie `csrf_token`.
- O cookie `csrf_token` é legível por JS porque `HttpOnly=false` (`interface/api/csrf.py:24-32`).
- O cookie `refresh_token` não é legível por JS.
- O callback termina em `FRONTEND_URL`. Não há `return_to`, então o backend sempre redireciona para a URL configurada.
- Erros no callback são problem+json na URL da API, não redirect para o front-end (`interface/api/routes/auth.py:102-129`, `interface/api/problems.py:75-100`). Isso é uma lacuna de UX registrada em `BACKEND_GAPS.md`.

## 16. Análise de ponta a ponta

1. O front-end envia `POST /api/v1/analyses` com `kind` e `file` (`interface/api/routes/analyses.py:96-121`). O locale do job vem do header `Accept-Language`; sem o header, o resolvedor devolve `en` (`application/locale.py:12-30`, `interface/api/dependencies.py:162-165`). O front-end deve enviar sempre `pt-BR`, `es` ou `en` conforme a interface, porque a justificativa é gerada nesse locale.
2. O backend inspeciona o arquivo por magic bytes, tamanho, páginas e conteúdo ativo (`infrastructure/storage/inspector.py`, `application/commands/documents.py:64-119`).
3. Em uma transação, grava o documento, cria a análise `queued` e o evento `queued`; depois publica a tarefa na fila `analysis` (`application/commands/create_analysis.py:114-199`).
4. Responde 202 com `analysis_id` e `status=queued`.
5. O worker Celery reivindica o job com `task_id` e lease, grava evento `processing` e roda o grafo (`application/commands/process_analysis.py:74-96`, `infrastructure/ai/graph.py`).
6. O grafo carrega o documento, faz ingestão e OCR, classifica o tipo, roda as regras determinísticas, o ML, o visual, o RAG e a interpretação, aplica guardrails e persiste o relatório no bucket (`infrastructure/ai/graph.py:911-985`).
7. Na mesma transação de conclusão, grava o resultado, a notificação, o vencimento (quando recibo) e o evento `completed` ou `degraded` (`infrastructure/ai/graph.py:996-1019`).
8. Em erro transitório com tentativas restantes, volta para `queued` com evento `retry_scheduled`; no limite, grava `failed` com `error_code` (`application/commands/process_analysis.py:97-123`).
9. O front-end descobre o resultado por polling em `GET /api/v1/analyses/{analysis_id}`.

O que existe para acompanhar:

- `GET /api/v1/analyses/{analysis_id}` com `status` e, ao final, `result`.
- `GET /api/v1/analyses` para listar.

O que não existe:

- SSE, WebSocket ou long polling.
- Endpoint de eventos (`analysis_events`).
- Percentual, etapa, tentativa ou timestamp de início no detalhe.
- Cancelamento.
- Retry manual.
- Exclusão.

## 17. Classificação de risco

Fonte única: `domain/scoring.py:73-99` e `domain/scoring.py:117-170`, com aplicação do ajuste final em `infrastructure/ai/graph.py:800-809`.

| Banda | Faixa de score | Fonte |
| --- | --- | --- |
| `low` | 0 a 39 | `ScoringConfig.low_max = 39`, `fuse_risk` em `domain/scoring.py:155-160` |
| `attention` | 40 a 69 | `ScoringConfig.attention_max = 69`, `fuse_risk` em `domain/scoring.py:157-160` |
| `high` | 70 a 100 | `else` de `fuse_risk` em `domain/scoring.py:159-160` |

A faixa do meio se chama `attention`, não `medium`. `medium` existe apenas como severidade de evidência, não como banda de risco. Em português: baixo = `low`, médio = `attention`, alto = `high`.

Regras adicionais:

- Piso crítico: se qualquer evidência for `critical` e o score bruto for menor que 80, o score sobe para 80 e a banda vira `high` (`ScoringConfig.critical_floor = 80`, `domain/scoring.py:151-160`).
- O ajuste do LLM é limitado por `LLM_MAX_SCORE_ADJUSTMENT` (padrão 5) e, no domínio, a 20. Ele nunca reduz o score, e o score final é `min(100, base_score + llm_adjustment)`, com piso crítico reaplicado (`infrastructure/ai/graph.py:800-809`, `domain/analysis.py:135-141`, `infrastructure/config.py:163`).
- `base_score` é o score fundido de determinístico, ML e visual. `score` é o final. A banda é sempre recalculada pelo backend a partir do `score` final (`infrastructure/ai/graph.py:800-809`).
- A interface consome `band` e `score` da API. Ela não recalcula classe nem score. `frontend/lib/risk/` pode mapear `band` para rótulo, cor e ícone, e pode exibir a faixa numérica apenas como legenda informativa, sem derivar a classe.
- Os pesos da fusão são `0.60` determinístico, `0.30` ML e `0.10` visual; o componente de ML combina `anomaly_weight = 0.20` (`domain/scoring.py:73-99`). A nota de calibração é "a calibrar com dados reais" (`domain/scoring.py:82`).
- A fonte oficial da decisão é `docs/adr/0002-score-deterministico.md`.

## 18. Catálogo de erros

Formato comum (`interface/api/problems.py:40-72`):

```json
{
  "type": "https://paysentineliq.local/problems/<code>",
  "title": "<titulo>",
  "status": 422,
  "detail": "<mensagem>",
  "instance": "/api/v1/analyses/{analysis_id}",
  "code": "<code>",
  "request_id": "<uuid>"
}
```

Erros de domínio e aplicação (`application/errors.py` e `domain/errors.py`):

| Código | HTTP | Origem ou significado |
| --- | --- | --- |
| `csrf_invalid` | 403 | CSRF ausente ou diferente em refresh/logout. |
| `security_service_unavailable` | 503 | Redis indisponível em operação de segurança. |
| `ssrf_blocked` | 400 | URL bloqueada pela guarda SSRF. |
| `invalid_access_token` | 401 | Bearer ausente, inválido, expirado ou revogado. |
| `forbidden` | 403 | Papel insuficiente. |
| `auth_not_configured` | 503 | Google OIDC não configurado. |
| `google_auth_failed` | 401 | Troca de code ou validação do ID token falhou. |
| `email_not_verified` | 403 | E-mail do Google não verificado. |
| `invalid_state` | 400 | State ausente, diferente do cookie ou já consumido. |
| `invalid_refresh_token` | 401 | Refresh ausente, inválido ou expirado. |
| `refresh_token_reuse` | 401 | Reuso de refresh revogado. |
| `too_many_attempts` | 429 | Força bruta em auth. Inclui `Retry-After`. |
| `upload_too_large` | 413 | Upload acima de `UPLOAD_MAX_MB` (padrão 25 MiB). |
| `request_too_large` | 413 | Corpo JSON acima de 1 MiB. |
| `empty_document` | 422 | Arquivo vazio. |
| `unsupported_document_type` | 422 | Não é PDF, PNG nem JPEG. |
| `invalid_document` | 422 | Conteúdo inválido. |
| `pdf_page_limit_exceeded` | 422 | PDF acima do limite de páginas. |
| `encrypted_pdf` | 422 | PDF criptografado. |
| `pdf_active_content` | 422 | PDF com JavaScript ou embed. Inclui `evidence[]`. |
| `storage_not_configured` | 503 | S3 não configurado. |
| `storage_unavailable` | 503 | S3 indisponível. |
| `document_not_found` | 404 | Documento inexistente ou de outro dono. |
| `unsupported_document` | 422 | Tipo sem análise suportada. |
| `invalid_idempotency_key` | 422 | Chave fora do formato ou tamanho. |
| `idempotency_conflict` | 409 | Mesma chave com arquivo diferente. |
| `analysis_quota_exceeded` | 429 | Limite de análises ativas por usuário. Padrão 2. |
| `task_dispatch_failed` | 503 | Fila de análise indisponível. |
| `notification_not_found` | 404 | Notificação inexistente ou de outro dono. |
| `invalid_locale` | 422 | Locale não suportado. |
| `invalid_notification_preference` | 422 | Preferência inválida. |
| `payable_not_found` | 404 | Vencimento inexistente ou de outro dono. |
| `payable_invalid_state` | 409 | Transição de status inválida. |
| `analysis_not_found` | 404 | Análise inexistente ou de outro dono. |
| `invalid_cursor` | 422 | Cursor opaco inválido. |
| `ocr_unavailable` | 503 | OCR indisponível. |
| `ocr_timeout` | 504 | OCR estourou o tempo. |
| `ocr_page_limit_exceeded` | 422 | OCR acima do limite de páginas. |
| `ocr_image_too_large` | 422 | Imagem renderizada acima do limite. |
| `guardrail_violation` | 422 | Violação de guardrail. |

Erros de middleware e de validação:

| Código | HTTP | Origem |
| --- | --- | --- |
| `request_timeout` | 504 | `TimeoutMiddleware` (`interface/api/limits.py:98-116`) |
| `rate_limited` | 429 | `RateLimitMiddleware`, com `Retry-After` (`interface/api/rate_limit.py:82-101`) |
| `rate_limit_unavailable` | 503 | Rate limit indisponível em rota de auth (`interface/api/rate_limit.py:66-80`) |
| `validation_error` | 422 | Falha de validação do FastAPI, sem refletir o payload (`interface/api/problems.py:103-114`) |
| `internal_error` | 500 | Erro inesperado, sem stack trace (`interface/api/problems.py:131-139`) |
| `bad_request` | 400 | HTTPException genérica (`interface/api/problems.py:15-24`) |
| `unauthorized` | 401 | HTTPException genérica |
| `forbidden` | 403 | HTTPException genérica |
| `not_found` | 404 | HTTPException genérica |
| `method_not_allowed` | 405 | HTTPException genérica |
| `conflict` | 409 | HTTPException genérica |
| `unprocessable_entity` | 422 | HTTPException genérica |
| `metrics_unauthorized` | 401 | `/metrics` sem credencial (`interface/api/routes/ops.py:51-59`) |
| `metrics_unavailable` | 503 | `/metrics` sem registry (`interface/api/routes/ops.py:60-68`) |

Notas:

- O `instance` usa o template da rota quando existe, para não refletir payload ou PII (`interface/api/problems.py:32-37`).
- O `request_id` também vai no header `X-Request-ID` (`interface/api/problems.py:63-65`).
- Erros de validação não devolvem a lista de campos inválidos, só `validation_error` com detalhe genérico (`interface/api/problems.py:103-114`). O front-end precisa validar antes de enviar para dar mensagens por campo.

## 19. Não validado

- `GET /openapi.json`: não foi possível baixar porque API e Docker não estavam em execução nesta sessão. O contrato foi extraído do código, não do schema gerado.
- Fluxo real com Google: o backend declara que testes usam JWKS e token mockados e que o fluxo real não foi executado sem credenciais (`docs/agent/MEMORY.md`).
- `GOOGLE_REDIRECT_URI` de produção: o `.env` de produção atual, que não é versionado, aponta para `/api/auth/google/callback` segundo `docs/agent/MEMORY.md`. O contrato e o `.env.example` usam `/api/v1/auth/google/callback`. O valor precisa ser corrigido antes de um deploy real.
- Comportamento real de cookies e CORS em domínios de produção: a análise é estática, a partir de `main.py`, `auth_cookies.py` e `csrf.py`. Não foi exercitada em navegador.
- Contagem exata de rate limit em produção: depende de `RATE_LIMIT_CAPACITY` e `RATE_LIMIT_REFILL_PER_SEC` configurados.
- Retenção e lifecycle do bucket: não há política exposta na API.
- Antivírus: existe porta, mas não implementação declarada; não há campo de status na API.
- Coordenadas de evidência: não existem no contrato. Os `bbox` e `region` internos de OCR e visão (`domain/ingestion.py:4-22`, `application/ports/ocr.py:7-18`) não são persistidos no relatório nem devolvidos pela API.
