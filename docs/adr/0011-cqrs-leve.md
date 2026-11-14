# ADR 0011: CQRS leve e descarte do Event Sourcing completo

- Status: aceito
- Data: 2026-11-14

## Contexto
A camada de aplicacao da P07 tinha `use_cases` com fronteiras mistas: `DocumentService` fazia upload (escrita) e URL de download (leitura); `ExampleService` era leitura mas chamava `commit`; `AuthService` so tinha operacoes de escrita; a analise de boleto era leitura/analise sem banco. A fila assincrona, a Central de Notificacoes e as listagens futuras vao consumir leituras e escritas com necessidades diferentes. O volume atual e pequeno e o PostgreSQL e a fonte de verdade.

## Decisao
- Adotar CQRS leve: `application/commands/` para casos de uso que mudam estado e `application/queries/` para leitura.
- Commands usam Unit of Work de escrita e retornam id ou DTO minimo. Queries usam portas de leitura estreitas, retornam DTOs de leitura e nunca chamam `commit` nem usam Unit of Work de escrita.
- Uma unica fonte de dados: o mesmo PostgreSQL. Nao havera banco de leitura, projecao, replicacao ou consistencia eventual.
- Migrar somente o que ja existe e se encaixa: upload de documento para command; URL de download, exemplo e analise de boleto para queries; autenticacao para o lado de commands, pois todas as operacoes publicas de sessao mudam estado.
- `AuthService` continua como um servico de comandos com tres operacoes; a divisao em um handler por operacao exige uma fase de auth e foi evitada para nao fazer refatoracao em massa.
- Contratos ativos no import-linter: queries nao importam commands; commands nao importam queries; queries nao importam Unit of Work de escrita; dominio nao importa aplicacao.
- A trilha de auditoria vira uma tabela append-only `analysis_events` na P11, sem dados pessoais no payload. Nenhuma tabela, broker ou publicacao de evento e criada agora.

## Alternativas descartadas
- **CQRS completo com banco de leitura:** descartado. A consistencia eventual e o custo operacional de sincronizacao nao trazem ganho no volume atual; a fonte unica PostgreSQL atende leitura e escrita.
- **Event Sourcing completo:** descartado. Um log imutavel de eventos conflita com o direito de apagar dados pessoais da LGPD e aumenta a complexidade de projecoes, versionamento e migracao sem necessidade proporcional.
- **Manter `use_cases` mistos:** descartado. As fronteiras de leitura/escrita ficariam implicitas e as queries continuariam podendo commitar ou carregar entidades inteiras.
- **Separar auth em tres handlers agora:** adiado. Exigiria refatorar rotas, testes e rotacao de tokens sem uma necessidade de leitura/escrita que justifique o risco nesta fase.

## Consequencias
- Commands e queries ficam testaveis separadamente e as queries nao podem commitar por contrato.
- O download de documento deixa de carregar a entidade `Document`; a porta de leitura seleciona apenas `s3_key` e filtra por `id` e `owner_id`.
- O exemplo deixa de usar Unit of Work e de commitar em uma leitura.
- A analise de boleto passa a ser um handler de query, sem banco; as regras, pesos e score da P07 nao mudam.
- `commands/auth.py` mantem o servico de sessao coeso; uma fase futura pode dividir login, refresh e logout em handlers menores.
- A suite Docker nao e exigida nesta fase; os testes sem Docker, Ruff, format, mypy e import-linter sao as checagens de aceite.
- A tabela `analysis_events` e a auditoria append-only ficam planejadas para a P11, sem PII no payload.
