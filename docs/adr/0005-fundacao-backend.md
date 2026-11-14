# ADR 0005: Fundacao transversal do backend

- Status: aceito
- Data: 2026-11-14

## Contexto
As fases seguintes precisam de uma base comum para configuracao, banco, erros, logs, localizacao e prontidao. Sem ela, cada funcionalidade criaria seu proprio formato de erro, sessao ou logging. A P02 nao tem regra de negocio e deve evitar abstrações que ainda nao sao necessarias.

## Decisao
- Configuracao: `pydantic-settings` lendo apenas variaveis de ambiente, sem arquivo `.env` embutido. `APP_ENV=local` usa defaults locais; qualquer outro valor exige `DATABASE_URL` e `REDIS_URL` na inicializacao.
- Injecao de dependencia: `Depends` do FastAPI com fabricas explicitas na interface e uma raiz de composicao em `create_app`. Sem container de DI ou service locator.
- Banco e UoW: `AsyncSession` por requisicao; `UnitOfWork` e repositorios sao portas na aplicacao; SQLAlchemy fica na infraestrutura. O UoW faz `commit`/`rollback` explicitos e nao cria sessao propria.
- Erros: RFC 7807 (`application/problem+json`) com `code` estavel em ingles, `request_id` e `instance` sem query string. A hierarquia de dominio/aplicacao define status e mensagem publica segura; erro inesperado vira 500 generico.
- Logs: JSON no stdout, `request_id` em `ContextVar`, sem query string, com filtro de mascaramento de CPF, CNPJ, e-mail, telefone e tokens. Tracebacks de erro inesperado nao vao para o cliente.
- Readiness: `/health` permanece liveness sem dependencias; `/ready` executa `SELECT 1` no Postgres e `PING` no Redis e retorna 503 se algum falhar.
- Convencoes REST: prefixo `/api/v1`; paginacao por cursor nao implementada nesta fase; `Idempotency-Key` reservado; locale resolvido por `Accept-Language` com fallback `en`.

## Alternativas consideradas
- Container de DI (Dishka, dependency-injector): descartado por complexidade e por YAGNI; `Depends` cobre o escopo atual.
- Session global por processo: descartado por concorrencia e isolamento de transacao.
- Repositorios como classes concretas na aplicacao: descartado para manter dominio/aplicacao independentes de SQLAlchemy.
- Erros no formato padrao do FastAPI: descartado por falta de `code` estavel e formato inconsistente entre validacao, HTTP e dominio.
- Logs de texto com mascaramento manual em cada chamada: descartado por risco de esquecimento; o filtro centraliza a regra.
- Ler `.env` automaticamente: descartado para evitar acoplamento a arquivo local e vazamento de configuracao de producao.

## Consequencias
A base fica testavel e previsivel, com fronteiras claras e sem dependencia de frameworks em dominio/aplicacao. O UoW explicito exige que cada caso de uso chame `commit`; esquecer o commit descarta a transacao. O filtro de PII cobre logs da aplicacao, mas logs de terceiros ainda precisam ser revisados. A rota `/api/v1/example` e temporaria e deve ser removida quando a primeira rota de negocio chegar. Reverter a decisao de DI ou de formato de erro exige novo ADR e ajuste dos handlers/testes.
