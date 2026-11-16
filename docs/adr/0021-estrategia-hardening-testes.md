# ADR 0021 - Estrategia de hardening e testes

## Status

Aceito em 2026-11-16.

## Contexto

A fase P17 precisa fechar lacunas de teste do backend sem inflar cobertura, sem enfraquecer
testes e sem refatoracao em massa. A suite atual tem 779 testes sem Docker e 41 testes Docker;
a cobertura sem Docker e 82,97% e a camada de infraestrutura tem 73,7% porque repositorios, S3,
Redis, SWR e servicos externos sao exercitados principalmente com Docker.

## Decisao

### Piso de cobertura

- Piso de 80% de declaracoes para a suite sem Docker, aplicado no alvo `make coverage`, que
  tambem roda em `make check`.
- A medicao e por declaracao, nao por branch; adotar branch coverage agora reduziria o numero
  sem aumentar a qualidade dos testes e exigiria uma rodada de calibracao.
- Modulos que so fazem sentido com servico externo continuam medidos pela suite Docker e
  aparecem separados na auditoria. O piso nao e aplicado a suite Docker para nao transformar
  disponibilidade do Docker Desktop em criterio de qualidade.

### Suite e marcadores

- `make test` roda `pytest -m "not docker"`; `make test-docker` roda build, up, migrate
  (com backup) e `pytest -m docker --run-docker`.
- Postgres, Redis, RabbitMQ, MinIO e Mailpit continuam cobertos pelos testes de repositorio,
  rate limit/SWR, fila E2E, S3 e Mailpit ja existentes; a auditoria mapeia cada servico para o
  teste correspondente.

### N+1

- Um utilitario unico escuta `before_cursor_execute` no `sync_engine` do SQLAlchemy e conta
  SELECTs. Testes de listagem comparam o custo com 1 e N registros e exigem numero constante.
- Testes de repositorio continuam validos para filtros e cursor; o teste de endpoint usa o app
  em processo com banco real para provar o caminho completo.

### Seguranca

- IDOR e escalada de papel sao provados com banco real em teste Docker, nao apenas com fakes.
- SQLi, SSRF, CSRF, forca bruta e rate limit concorrente mantem os testes existentes; a fase
  adiciona apenas os cenarios sem evidencia previa (upload malicioso e IDOR de mutacoes).
- Upload malicioso e testado no dominio e na borda: extensao falsa, nome com traversal e bomba
  de descompressao. A checagem de dimensao da imagem acontece pelo cabecalho antes de decodificar
  os pixels, para nao alocar memoria proporcional a uma imagem bomb.

### Contrato

- O OpenAPI e exportado por script e comparado com um snapshot versionado em
  `backend/tests/contracts/openapi.json`. Atualizar o snapshot e uma acao explicita, nunca
  automatica no teste.

### Carga

- O script de carga e um smoke test local de concorrencia e token bucket; ele mede latencia
  p50/p95/max e conta 429, mas nao promete capacidade de producao.

### Frontend

- Playwright e Jest ficam para a fase do frontend. O backend nao cria infraestrutura de teste
  de navegador.

## Alternativas rejeitadas

- Excluir modulos de infraestrutura da medicao para elevar o percentual: esconderia a lacuna.
- Testes vazios ou asserts triviais para atingir piso: proibido pela SPEC e pelas regras.
- Rodar branch coverage sem calibrar: mudaria a metrica sem resolver lacunas reais.
- Testar IDOR apenas com handler fake: nao prova o filtro SQL nem a ausencia de efeito colateral.
- Snapshot gerado automaticamente quando o teste falha: mascararia mudancas acidentais.
- Benchmark de carga como criterio de aceite: ambiente local e compartilhado nao representa
  producao e criaria falsa confianca.

## Consequencias

- `make check` fica alguns segundos mais lento por medir cobertura, mas passa a falhar em
  regressao de cobertura.
- Modulos de infraestrutura com baixa cobertura sem Docker precisam da suite Docker para medicao
  completa; isso fica explicito na auditoria e no PROGRESS.md.
- Qualquer mudanca de contrato exige atualizar o snapshot no mesmo commit, revisando o diff.
- O script de carga pode reportar bucket ja drenado; o resultado deve ser lido como smoke test,
  nunca como capacidade.
