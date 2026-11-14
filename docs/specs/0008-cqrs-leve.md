# SPEC 0008: CQRS leve (commands e queries)

## Objetivo
Separar, na camada de aplicacao, casos de uso de escrita (`commands`) e de leitura (`queries`), mantendo o mesmo PostgreSQL. Sem banco de leitura, sem projecoes, sem Event Sourcing.

## Escopo
- Criar `application/commands/` e `application/queries/`.
- Migrar somente os casos de uso existentes que se encaixam:
  - upload de documento -> command;
  - URL de download de documento -> query;
  - verificacao do exemplo -> query;
  - analise de boleto -> query (sem alterar regras da P07);
  - autenticacao -> command-side, pois todas as operacoes publicas mudam estado; a divisao em um handler por operacao fica para uma fase de auth.
- Adicionar portas de leitura estreitas, sem carregar entidades de dominio inteiras.
- Adicionar contratos no import-linter.
- Atualizar ADR, MEMORY, PROGRESS e este documento.

## Fora do escopo
- Banco de leitura separado, projecoes, replicacao ou consistencia eventual.
- Event Sourcing, broker de eventos novo, tabela `analysis_events` (P11) ou publicacao de eventos.
- Alterar regras, pesos ou score de boleto da P07.
- Endpoint novo, autenticacao nova, fila ou Central de Notificacoes.
- Refatoracao geral de modulos fora da camada de aplicacao.

## Contratos
### Commands
- Ficam em `paysentineliq.application.commands`.
- Podem usar Unit of Work de escrita e portas de escrita.
- A Unit of Work do upload expoe somente `DocumentWriteRepository.add`; o comando nao recebe metodo de leitura.
- Retornam id ou DTO minimo; nao retornam entidade ORM nem `Document` inteiro.
- `UploadDocumentCommand` + `UploadDocumentHandler` -> `UploadedDocumentResult` com id, analysis_id, kind, sha256, size, content_type, original_name_sanitized e created_at.
- `AuthService` permanece como servico de comandos de sessao em `commands/auth.py`; `login_with_google`, `refresh` e `logout` mudam estado.

### Queries
- Ficam em `paysentineliq.application.queries`.
- Nunca mudam estado; nao chamam `commit` e nao usam Unit of Work de escrita.
- Retornam DTOs de leitura ou resultado imutavel de analise.
- `GetDocumentDownloadUrlQuery` + `GetDocumentDownloadUrlHandler` -> `DocumentDownloadUrlDTO`; a porta `DocumentReadRepository` retorna apenas `DocumentDownloadLocation(s3_key)`, sem carregar `Document`.
- `GetExampleQuery` + `GetExampleHandler` -> `ExampleStatusDTO`; usa `ExampleRepository.exists`, sem UoW e sem commit.
- `AnalyzeBoletoQuery` + `AnalyzeBoletoHandler` -> `BoletoAnalysis`; sem banco, sem UoW, sem alterar as regras da P07.

### Portas de leitura
- `DocumentReadRepository.get_download_location(document_id, owner_id) -> DocumentDownloadLocation | None` faz `SELECT` apenas de `s3_key` e filtra pelo dono.
- `ExampleRepository.exists(item_id) -> bool` continua sendo a porta de leitura existente.
- O adaptador SQLAlchemy de documentos de leitura nao reutiliza o repositorio que carrega `Document` inteiro.
- Consultas de lista futuras devem selecionar apenas as colunas do DTO e evitar N+1.

### Import-linter
- `queries` nao importa `commands`.
- `commands` nao importa `queries`.
- `queries` nao importa `application.ports.document_unit_of_work` nem `application.ports.auth_unit_of_work`.
- `domain` nao importa `application`.

## Criterios de aceite (viram testes)
1. Upload de documento continua criando o objeto no storage e o registro no banco, com prefixo do dono, nome sanitizado e compensacao em falha.
2. Upload retorna DTO minimo com os campos usados pela resposta HTTP, sem expor a entidade `Document`.
3. Download URL consulta apenas `s3_key` do documento do dono e retorna `DocumentDownloadUrlDTO`; documento de outro dono retorna 404.
4. Query de exemplo retorna `ExampleStatusDTO` e nao usa Unit of Work nem commit.
5. Analise de boleto continua com o mesmo resultado e score da P07; o handler nao usa banco nem UoW.
6. Rotas de documentos e exemplo preservam contrato HTTP, autenticacao e mascaramento de PII.
7. Os quatro contratos do import-linter passam.
8. `make check` (Ruff, format, mypy strict, import-linter e testes sem Docker) fica verde.

## Plano de testes
- Atualizar `tests/unit/test_document_service.py` para os handlers de comando/query; manter os testes de seguranca de upload.
- Atualizar `tests/unit/test_document_routes.py` e `test_example_route.py` para as novas dependencias.
- Atualizar `tests/unit/test_example_service.py` para a query sem UoW.
- Atualizar `tests/unit/test_boleto_analysis_service.py` para o handler de query, sem mudar os casos da P07.
- Adicionar teste unitario do adaptador `SqlAlchemyDocumentReadRepository` provando que a query seleciona `s3_key` e filtra por `id` e `owner_id`.
- Rodar testes direcionados, depois `make check`.

## Riscos e observacoes
- Auth permanece um servico com tres operacoes de escrita; a separacao em um handler por operacao exige uma fase de auth e nao foi feita para evitar refatoracao em massa.
- O read model de documentos e o exemplo usam a mesma sessao SQLAlchemy, mas portas separadas; nao ha banco de leitura.
- `analysis_events` e append-only e sera planejada na P11, sem payload com dados pessoais; nao existe nesta fase.
- A suite Docker nao e exigida nesta fase; os testes de integracao que dependem dela ficam fora do `make check`.
