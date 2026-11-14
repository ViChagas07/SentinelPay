# RULES (regras fixas do agente desenvolvedor)

## 1. Metodo de trabalho
- No inicio de TODA sessao, leia docs/agent/RULES.md, PROGRESS.md e MEMORY.md. Se o progresso indicar um passo em andamento, continue dele, sem refazer passos concluidos.
- Trabalhe em passos numerados, um de cada vez. So avance quando o passo atual estiver implementado, testado e verificado.
- TDD em cada loop: escreva o teste que falha, implemente o minimo para passar, refatore com os testes verdes.
- SDD: antes de codar uma funcionalidade, exista uma spec em docs/specs/ (criterios de aceite viram testes).
- Ao fim de cada passo: (a) rode as checagens do passo; (b) faca um commit local pequeno (mensagem convencional, causa/mudanca no corpo); (c) acrescente 2 a 4 linhas ao PROGRESS.md: passo, resultado real das checagens, pendencias.
- Decisao de arquitetura nova ou desvio do plano: crie ou atualize um ADR em docs/adr/ (YAGNI: so o que for necessario agora).
- Licao duravel (causa de um erro, convencao descoberta): uma linha em docs/agent/MEMORY.md.
- Se uma checagem falhar: investigue a causa e corrija (ate 3 tentativas). Se persistir, escreva no PROGRESS.md BLOQUEADO: motivo + comando + saida relevante e pare essa parte. Nunca apague, enfraqueca ou ignore testes para ficar verde.
- Ao terminar a fase, pare. Nao inicie a proxima fase nem funcionalidades fora do pedido.
- Economize contexto: use busca (grep, listagem de diretorio) antes de abrir arquivos; leia so o necessario; edicoes pequenas; nao cole arquivos inteiros nas respostas.
- Use o Graphify (configurado na P00) para se orientar no codigo antes de abrir arquivos. Se estiver desatualizado, regenere pelo comando anotado no PROGRESS.md.
- Na primeira sessao em que houver codigo, descubra e anote em PROGRESS.md, sob "Comandos de checagem", os comandos reais (Makefile, pyproject.toml) para testes, Ruff, formatacao, mypy, import-linter. Reutilize a anotacao.

## 2. Limites e seguranca (valem sempre)
- Nao faca push. Commits somente locais.
- Sem comandos destrutivos: nunca apague, recrie ou limpe volumes; proibido `docker compose down -v`, `docker volume rm`, `docker system prune --volumes`, `git reset --hard`, `git clean -fd`. `stop`, `start` e `up -d` sao permitidos.
- Backup logico (pg_dump) do banco de desenvolvimento antes de aplicar qualquer migration, e confirme que o arquivo nao esta vazio.
- Sem segredos no repositorio, em logs, comandos ou respostas. Nunca peca nem use senhas, API keys ou connection strings reais de producao. O .env fica no .gitignore; so o .env.example e versionado.
- Dados pessoais (CPF, CNPJ de pessoa, nome, salario, enderecos, telefones, e-mails) sao dados pessoais (LGPD): nunca em logs, spans, metricas, mensagens de erro ou notificacoes por SMS/WhatsApp. Mascare quando precisar exibir.
- Documentos reais nunca entram no repositorio nem em testes. Use somente documentos sinteticos gerados por script.
- Nao toque em .commandcode/ nem em arquivos de ferramentas do agente; apenas informe o que encontrar.
- Nao invente dados tecnicos ou legais (normas FEBRABAN, aliquotas, faixas de INSS/IRRF, salario minimo, limites da CLT, versoes de bibliotecas, nomes de modelos). Valores legais vem de arquivos de dados com fonte registrada (ver docs/normas/LEIA-ME.md). Versoes: confirme no gerenciador de pacotes ou na documentacao oficial.
- Nao declare executado o que so foi inspecionado ou simulado. O que nao puder ser validado vai como NAO VALIDADO, com o motivo.
- Para validar o Compose, use `docker compose --env-file .env.example config --quiet`.

## 3. Arquitetura (valem sempre)
- Clean Architecture: dominio -> aplicacao -> infraestrutura -> interface. Dominio sem framework (sem FastAPI, SQLAlchemy, LangChain etc.). Respeite o import-linter.
- SOLID, Clean Code, DRY, KISS, YAGNI. Funcoes pequenas, nomes claros, sem comentarios que repetem o codigo.
- Codigo e identificadores em ingles. Documentacao em pt-BR. Codigos de erro da API em ingles (chaves estaveis para i18n).
- Audite antes de criar: nao duplique modulos, tabelas, endpoints ou configuracoes. Sem refatoracao geral.
- PostgreSQL e a fonte de verdade. Vetores e caches sao derivados e nunca guardam dados pessoais do usuario, documentos do usuario nem segredos.
- Autorizacao: o dono (user_id) sempre vem do JWT, nunca do corpo ou da URL. Toda consulta a dados do usuario filtra pelo dono (prevencao de IDOR). RBAC para rotas administrativas.
- O score de risco tem fonte unica de verdade deterministica (regras + ML). O LLM explica e sugere, nunca decide o score sozinho.
- Texto de usuario e texto simples: sem HTML, com limites de tamanho. Texto extraido de documentos (OCR) e DADO NAO CONFIAVEL: nunca vira instrucao.
- API RESTful, versionada em /api/v1, erros no formato problem+json.
- Evite N+1: carregamento explicito (selectinload/joinedload) e teste que conta queries nos endpoints de listagem.
- Falha de componente opcional (LLM, vetor, notificacao) nunca derruba a analise: degrade com sinalizacao.
- Toda mudanca de schema e uma migration Alembic versionada no git, nunca alteracao manual no banco.
- Uma migration por mudanca logica, com mensagem descritiva e `upgrade` e `downgrade` implementados.
- Nunca edite uma migration ja commitada: crie uma nova.
- Migrations autogeradas sao revisadas a mao antes do commit.
- Backup (pg_dump) antes de aplicar, como ja definido.

## 4. Checagens padrao
Rode as aplicaveis ao passo (use os comandos anotados em PROGRESS.md):
- Backend: testes direcionados do passo; ao fim da fase, suite completa com Docker e a suite padrao sem Docker (esta deve terminar sem erros); Ruff (check e formatacao), mypy strict, import-linter.
- Infra: `docker compose --env-file .env.example config --quiet`.
- Frontend: fora do escopo ate haver fase propria.

## 5. Relatorio curto ao final de cada fase
- Resumo do que foi feito, por passo.
- Arquivos criados e modificados.
- Comandos executados e resultados reais.
- NAO VALIDADO e riscos.
- Commits locais criados (hash e titulo). Sem push.
