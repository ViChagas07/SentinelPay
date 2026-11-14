# Fontes normativas

Coloque aqui, em PDF ou Markdown, os documentos OFICIAIS que embasam as regras: layout FEBRABAN de boleto e de arrecadacao, tabelas oficiais de INSS e IRRF por competencia, salario minimo vigente, trechos da CLT usados.

Regras do agente:
- Nenhum valor legal (aliquota, faixa, teto, salario minimo) e escrito de memoria no codigo.
- Valores vivem em arquivos de dados versionados (data/regulatory/*.yaml) com campos `fonte`, `vigencia_inicio`, `vigencia_fim`.
- Sem fonte registrada, a regra retorna NAO VERIFICAVEL, nunca "fraude".
