# SPEC 0018 - Hardening de testes e qualidade

## Objetivo

Fechar lacunas de teste e qualidade do backend antes do deploy, sem inflar cobertura com testes
vazios, sem enfraquecer testes existentes e sem refatoracao em massa. A fase mede o que existe,
adiciona testes que provam invariantes de seguranca, contrato e desempenho de query, e deixa um
piso de cobertura aplicado no Makefile.

## Escopo

- Auditoria de cobertura por camada e lista de modulos sem teste direto.
- Piso de cobertura da suite sem Docker, aplicado em `make coverage` e `make check`.
- Suite padrao sem Docker e suite Docker cobrindo Postgres, Redis, RabbitMQ, MinIO e Mailpit.
- Utilitario de contagem de queries por evento do SQLAlchemy e teste em todo endpoint de
  listagem com relacionamentos (analises, payables e notificacoes).
- Testes de IDOR em todas as rotas com dono, SQLi, SSRF, CSRF, forca bruta, rate limit sob
  concorrencia, escalada de papel e upload malicioso.
- Teste de stampede do cache SWR e script de carga basica contra a API local.
- Snapshot do OpenAPI versionado e teste que detecta mudanca acidental de contrato.
- Higiene: `pip-audit`, `bandit`, ADRs coerentes, MEMORY revisada e import-linter sem excecoes
  injustificadas.

## Fora de escopo

- Playwright e Jest: pertencem a fase do frontend e ficam registrados no PROGRESS.md como
  pendencia daquela fase.
- Prometer capacidade, throughput ou latencia de producao a partir do script de carga local.
- Antivirus real, provedores reais de SMS/WhatsApp, AWS real, OCR real pt/es e LLM real.
- Refatoracao ampla de modulos ou mudanca de arquitetura.

## Piso de cobertura

- A suite sem Docker mede `paysentineliq` com `pytest-cov`.
- Piso inicial: 80% de declaracoes, com margem pequena sobre os 82,97% medidos em 2026-11-16.
- O piso vale para a suite sem Docker; modulos que dependem de servicos externos continuam
  cobertos pela suite Docker, que e registrada separadamente na auditoria.
- Cobertura nao pode ser aumentada com testes vazios, asserts triviais ou exclusao de codigo.

## Contagem de queries

- Utilitario em `tests/support/query_counter.py` escuta `before_cursor_execute` no
  `sync_engine` do SQLAlchemy e conta SELECTs.
- Cada endpoint de listagem com dados de dono e testado com mais de um registro; o numero de
  SELECTs deve ser constante e igual ao custo de autenticacao mais a consulta da lista.
- Um N+1 faz o teste falhar; nao ha tolerancia por numero de linhas.

## Seguranca

- IDOR: rotas com `{id}` de documento, analise, payable e notificacao retornam 404 para outro
  dono, sem efeito colateral no recurso.
- Escalada de papel: token com claim `admin` nao vence a role do banco.
- Upload malicioso: extensao falsa, bomba de descompressao simples e nome com traversal.
- SQLi, SSRF, CSRF, forca bruta e rate limit concorrente mantem os testes ja existentes e
  ganham evidencias na auditoria.

## Contrato

- `scripts/export_openapi.py` gera o OpenAPI local de forma deterministica.
- `backend/tests/contracts/openapi.json` e a fotografia versionada.
- O teste falha quando uma rota, status, schema ou campo muda sem atualizacao explicita do
  snapshot.

## Carga basica

- `scripts/load_check.py` dispara requisicoes concorrentes contra a API local, mede latencia
  p50/p95/max e conta status.
- O script valida token bucket (presenca de 429) e tempos basicos; nao e benchmark de producao
  e nao promete capacidade.

## Criterios de aceite (viram testes)

1. `make test` sem Docker passa sem erro.
2. `make test-docker` passa e cobre Postgres, Redis, RabbitMQ, MinIO e Mailpit.
3. `make coverage` falha abaixo de 80% e passa na suite atual.
4. Os tres endpoints de listagem usam numero constante de SELECTs com 1 ou N registros.
5. IDOR retorna 404 em todas as rotas com dono e nao altera o recurso do dono.
6. Claim `admin` no token nao promove usuario comum; role do banco vence.
7. Upload com extensao falsa, bomba de descompressao e traversal e rejeitado ou sanitizado.
8. Teste concorrente do SWR comprova uma unica recomputacao.
9. Snapshot do OpenAPI existe e o teste compara o schema atual campo a campo.
10. `pip-audit`, `bandit`, Ruff, mypy strict e import-linter passam.

## Riscos e NAO VALIDADO

- Cobertura de 80% nao garante ausencia de defeitos; mede apenas declaracoes executadas.
- A suite Docker depende de Docker Desktop e dos servicos locais; throughput, HA e producao
  continuam NAO VALIDADOS.
- O script de carga usa uma unica origem e nao representa trafego real, CDN ou DDoS de borda.
- Ataques reais, adaptativos e virus/malware reais seguem NAO VALIDADOS.
