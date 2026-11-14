# MEMORY (memoria duravel do projeto)

Registre aqui apenas o que ajuda sessoes futuras: decisoes que valem sempre, armadilhas ja encontradas (com a causa), convencoes. Nada de segredos, nada de diario de tarefas (isso fica no PROGRESS.md).

## Decisoes duraveis
- Stack e fronteiras em ADR-0001; score deterministico em ADR-0002; `graphify-out/` fora do git em ADR-0003.
- `.env` local guarda as credenciais e nunca e versionado; somente `.env.example` (placeholders) entra no git.
- A raiz do projeto e `SentinelPay/`. A antiga pasta `repo/` era uma duplicata dos arquivos de raiz e nao deve ser recriada.
- Codigo e identificadores em ingles; documentacao em pt-BR (RULES).

## Armadilhas conhecidas
- O `.env` atual aponta para servicos de producao. Nao rodar testes ou scripts locais contra ele; criar configuracao de teste separada na P01.
- Graphify com backend Gemini exige o extra `graphifyy[gemini]` (pacote `openai`); sem ele o chunk semantico falha com "the 'openai' package is required".
- PowerShell 5.1 nao aceita `&&`; encadear comandos com `;` ou `if ($?)`.
- O Graphify ignora `.env` por seguranca e por `.gitignore`; o caminho aparece como ignorado na saida, o que e esperado.
