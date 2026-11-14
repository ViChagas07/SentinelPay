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
- Os testes forcam `APP_ENV=local` e URLs locais no `backend/conftest.py`, mesmo que exista configuracao de producao no ambiente.

## Armadilhas conhecidas
- O `.env` atual aponta para servicos de producao. Nao rodar testes ou scripts locais contra ele; o Compose usa `.env.example`.
- A porta 5432 do host esta ocupada por um PostgreSQL local; o Compose mapeia o Postgres em `${POSTGRES_PORT}` (55432 no exemplo).
- Healthcheck do Mailpit: usar `/mailpit readyz`, pois o binario nao esta no PATH (senao falha com "executable file not found").
- `make test-docker` usa `API_BASE_URL` com default `http://localhost:8000`; se `API_PORT` mudar, exporte `API_BASE_URL` antes do alvo.
- As imagens oficiais do MinIO sairam do Docker Hub (404) e o Quay exige autenticacao (401); a imagem local e comunitaria e fixada (ADR-0004).
- O access log do uvicorn foi desativado (`--no-access-log`); ele nao passa pelo filtro de PII e poderia imprimir query string. Os logs da aplicacao continuam em JSON.
- A regex de telefone exige DDD; sem isso ela mascara segmentos de UUID `0000-0000` e corrompe `request_id`/paths nos logs.
- Ao adicionar migration, rebuild da imagem da API (`docker compose --env-file .env.example build api` + `make up`) antes de `make migrate`; o comando roda dentro do container.
- Graphify: use `graphify update .` para mudancas de codigo; a extracao semantica de docs pode recusar shrink e manter nos antigos, sem bloquear o grafo de codigo.
- Graphify com backend Gemini exige o extra `graphifyy[gemini]` (pacote `openai`); sem ele o chunk semantico falha com "the 'openai' package is required".
- PowerShell 5.1 nao aceita `&&`; encadear comandos com `;` ou `if ($?)`.
- O Graphify ignora `.env` por seguranca e por `.gitignore`; o caminho aparece como ignorado na saida, o que e esperado.
