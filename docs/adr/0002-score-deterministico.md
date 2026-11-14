# ADR 0002: Score deterministico como fonte da verdade

- Status: aceito
- Data: 2026-11-14

## Contexto
O score de risco (0 a 100) orienta decisoes sobre documentos financeiros e precisa ser reproduzivel, auditavel e explicavel. Um LLM pode alucinar, variar entre execucoes e nao oferecer garantia numerica.

## Decisao
O score e calculado por um componente deterministico e versionado (regras + modelo de ML com versao fixa). Para as mesmas entradas e a mesma versao, o resultado deve ser identico. O LLM recebe apenas fatos estruturados ja calculados e produz explicacao, resumo e sugestoes em linguagem natural; ele nunca altera, recalcula ou sobrescreve o score. Se o LLM falhar ou estiver indisponivel, a analise continua e a resposta degrada apenas a explicacao.

## Alternativas consideradas
- LLM decide o score: descartado por falta de reprodutibilidade, risco de alucinacao e dificuldade de auditoria.
- Score apenas por regras, sem ML: descartado porque o modelo agrega sinais que regras fixas nao capturam; as regras continuam necessarias para justificar e limitar o resultado.
- LLM como juiz final em caso de empate: descartado; empates e casos incertos devem ser resolvidos por regra explicita e versionada, com sinalizacao de revisao humana.

## Consequencias
Regras, pesos e versoes do modelo precisam ser versionados e testados com casos de regressao. A explicacao do LLM deve citar os fatos e fatores que recebeu, sem inventar novos. A ausencia de LLM nao bloqueia o pipeline. Mudar a formula do score exige novo ADR e nova versao do modelo, preservando a reprodutibilidade historica.
