# ADR 0030: política de senha, hashing e tokens de autenticação

- Status: aceito
- Data: 2026-11-23
- Fase: P20

## Contexto

A autenticação por senha exige hashing resistente a GPU, regras de senha que o front possa
espelhar sem duplicar lógica e tokens de e-mail que não vazem nem permitam repetição.

## Decisão

1. Hash com Argon2id via `argon2-cffi`. Parâmetros (tempo, memória, paralelismo, tamanho de hash
   e salt) vêm de configuração e são verificados no login; se `argon2-cffi` indicar rehash, o novo
   hash é persistido na mesma transação do login.
2. Política no servidor: 10 a 128 caracteres, sem exigência de classes de símbolos, rejeição de
   lista local de senhas comuns e de senha que contenha e-mail ou nome do usuário. HIBP fica
   opcional e desligado por padrão, atrás de flag, para não criar dependência de rede.
3. Comparação de senha em tempo constante via verificador Argon2. Usuário inexistente e conta
   só-Google executam um hash falso com os mesmos parâmetros para equalizar o tempo de resposta.
4. `GET /api/v1/auth/password-policy` devolve mínimo, máximo, códigos de regra e o indicador de
   senha comum. O front calcula só a força visual, nunca a validade.
5. Tokens de verificação e reset são opacos (`secrets.token_urlsafe(32)`), com apenas SHA-256 no
   banco, expiração de 24 h e 30 min, uso único, IP e user agent de criação. Reenvio revoga tokens
   anteriores do mesmo tipo.
6. Links de e-mail usam `APP_BASE_URL` fixo; nunca o cabeçalho Host.
7. Bloqueio progressivo por conta usa `failed_login_count` e `locked_until` com atraso exponencial
   a partir de 5 falhas, limitado a 1 h. Sucesso zera contadores.

## Consequências

- Custo de CPU do login é estável mesmo para e-mails inexistentes.
- A política pode mudar via configuração sem alterar o front, que lê o endpoint.
- Tokens de e-mail são inúteis se o banco vazar, e um vazamento de token não expõe senha.
- HIBP e captcha seguem desligados até aprovação explícita.
