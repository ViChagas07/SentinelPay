# ADR 0001: Stack e arquitetura base

- Status: aceito
- Data: 2026-11-14

## Contexto
O PaySentinelIQ e um backend de analise antifraude de boletos, contracheques e recibos, com pipeline de documentos, score de risco, explicacao por LLM, armazenamento de evidencias e notificacoes. A fase P00 apenas fixa a stack; nenhum codigo de produto foi criado.

## Decisao
Adotar Python 3.11, FastAPI e Clean Architecture em quatro camadas (dominio, aplicacao, infraestrutura e interface), com a regra de dependencia apontando para dentro e verificacao por import-linter. Persistencia em PostgreSQL com asyncpg e SQLAlchemy; Redis para cache, rate limit e backend de resultados; RabbitMQ com Celery para tarefas assincronas; LangGraph para orquestracao do pipeline; CrewAI para o relatorio; LangChain como camada de LLM e prompts. Vetores em PGVector no ambiente local e Pinecone em producao, atras de uma interface unica. Documentos em S3. Dependencias e ambiente gerenciados com Poetry.

## Alternativas consideradas
- Framework sincrono ou monolito sem camadas: descartado por acoplamento, testabilidade e dificuldade de isolar dominio.
- Um unico orquestrador LLM para pipeline e relatorio: descartado por misturar responsabilidades e dificultar testes deterministicos.
- Banco vetorial exclusivo em producao: descartado para manter paridade local com PGVector e reduzir custo no desenvolvimento.

## Consequencias
O dominio fica independente de framework e testavel sem infraestrutura. A stack exige disciplina de fronteiras, injecao de dependencia e testes de contrato entre camadas. PGVector e Pinecone precisam da mesma interface e de testes equivalentes. A escolha de tres bibliotecas de IA (LangGraph, CrewAI e LangChain) aumenta o numero de dependencias e exige versoes fixadas no Poetry. Reverter para uma stack mais simples exige novo ADR e migracao dos adaptadores.
