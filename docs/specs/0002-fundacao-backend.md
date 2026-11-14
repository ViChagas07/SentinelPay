# SPEC 0002: Fundacao transversal do backend

## Objetivo
Entregar a base reutilizavel do backend: configuracao tipada, composicao de dependencias, banco async, Unit of Work, erros problem+json, logs estruturados com mascaramento, convencoes REST e readiness. Nenhuma regra de negocio de fraude.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: `Settings` com pydantic-settings lendo somente do ambiente. Em `APP_ENV=local`, usar defaults locais; fora de local, falhar na inicializacao se `DATABASE_URL` ou `REDIS_URL` faltarem.
- RF2: raiz de composicao em `create_app`, com `Depends` e fabricas explicitas; sem container de DI.
- RF3: engine async `postgresql+asyncpg`, sessao por requisicao, portas `Repository` e `UnitOfWork` na aplicacao e adaptadores SQLAlchemy na infraestrutura.
- RF4: Alembic async com uma migration vazia (somente `alembic_version`). Base declarativa com `id` UUID, `created_at` e `updated_at`.
- RF5: hierarquia de erros de dominio/aplicacao mapeada para `application/problem+json` com `code` estavel em ingles, sem stack trace nem dado pessoal.
- RF6: logs JSON no stdout com `request_id` propagado e filtro que mascara CPF, CNPJ, e-mail, telefone e tokens.
- RF7: prefixo `/api/v1`, convencao de paginacao por cursor documentada, header `Idempotency-Key` reservado e resolvedor de `Accept-Language` com suporte a pt-BR, en, fr, ja, es, de, ar, ko e zh (fallback en).
- RF8: `GET /ready` verifica Postgres e Redis; `GET /health` continua sendo liveness leve.
- RNF1: sem tabelas de negocio, auth, IA ou regras de fraude.
- RNF2: testes unitarios das pecas e testes de integracao marcados como `docker` para sessao e migration.
- RNF3: sem segredos em logs, respostas ou repositorio.

## Fora do escopo
Autenticacao, autorizacao, modelos de negocio, tabelas de dominio, Celery, IA, OCR, frontend e paginacao implementada em endpoints.

## Contrato (endpoints, schemas, eventos)
- `GET /health` -> `200 {"status":"ok"}`. Nao toca Postgres nem Redis.
- `GET /ready` -> `200` quando Postgres e Redis respondem; `503` caso contrario, com `{"status":"ready|not_ready","checks":{"postgres":bool,"redis":bool}}`.
- `GET /api/v1/example/{item_id}` (rota removivel de prova) -> `200` com `item_id`, `status`, `locale` e `request_id`; UUID nulo retorna `404` problem+json com codigo `document_not_found`.
- Erros: `Content-Type: application/problem+json`, campos `type`, `title`, `status`, `detail`, `instance`, `code`, `request_id`.
- Headers: `X-Request-ID` aceito quando seguro e ecoado em todas as respostas; `Idempotency-Key` reservado para fases futuras.
- Locale: `Accept-Language` normalizado para um dos 9 locales suportados; invalido ou ausente cai em `en`.

## Criterios de aceite (cada um vira pelo menos um teste)
1. `Settings` falha fora de local sem URL obrigatoria e nao le arquivo `.env`.
2. `/health` continua retornando 200 sem dependencias.
3. `/ready` retorna 200 com Postgres/Redis e 503 quando um check falha (teste unitario com fake).
4. Erro de dominio vira problem+json com `code=document_not_found`, `request_id` e sem stack trace.
5. Erro inesperado vira 500 generico, sem mensagem interna.
6. Filtro de log mascara CPF, CNPJ, e-mail, telefone e tokens; JSON inclui request_id.
7. Rota de exemplo executa SELECT assincrono, retorna 200 e propaga request_id; UUID nulo retorna o erro mapeado.
8. Locale resolver cobre todos os locales e fallback.
9. Sessao async executa `SELECT 1` e migration vazia aplica `alembic upgrade head`.
10. Ruff, formatacao, mypy strict, import-linter e pytest sem Docker passam.

## Casos de borda e de abuso
- `X-Request-ID` invalido ou gigante e substituido por UUID gerado.
- `Accept-Language` com `q=0`, desconhecido ou malformado nao quebra e cai no fallback.
- Problema 500 nao revela tipo de excecao, SQL, stack trace ou dados pessoais.
- Logs de acesso nao incluem query string.
- `/health` nao depende de banco/Redis; `/ready` e interno.

## Plano de testes (TDD: teste falho primeiro)
1. Config: testes de defaults locais, obrigatoriedade fora de local e ausencia de leitura de `.env`.
2. Logs: testes do filtro de PII, do formatter JSON e do request_id no contexto.
3. Erros/locale: testes de handlers problem+json, codigo estavel e casos de `Accept-Language`.
4. Banco: testes unitarios de UoW/repository com fake e testes docker de sessao, `/ready`, rota de exemplo e migration.
5. Rodar `make check` e `make test-docker`; backup antes de `alembic upgrade head`.

## Riscos e NAO VALIDADO
- Dependencia de Docker para os testes de integracao; sem daemon, marcar NAO VALIDADO.
- A migration vazia e a unica alteracao de schema; qualquer tabela futura exige backup e nova migration.
- Logs de terceiros (uvicorn) nao passam pelo formatter JSON da aplicacao nesta fase.
- A rota de exemplo deve ser removida quando a primeira rota de negocio existir.
