# ADR 0018: ticket de uso único para concluir OIDC entre domínios

- Status: aceito
- Data: 2026-11-24
- Fase: F25

## Contexto

O BFF do front lê o refresh token no servidor Next para renovar a sessão. Isso exige que front e API sejam same-site, como registrado no ADR 0004. Em produção o front está em `sentinelpay1.vercel.app` e a API em `sentinelpay.up.railway.app`, domínios registráveis diferentes. O callback do Google grava `refresh_token` no domínio da API e redireciona para o front. O navegador não envia esse cookie ao BFF, então a sessão nunca é criada.

As alternativas consideradas foram:

- rewrite/proxy reverso de `/api/v1/*` na Vercel para o Railway: resolve o host, mas depende de um proxy externo e conflita com os Route Handlers existentes do BFF.
- access token ou refresh token na URL: expõe credencial ao JavaScript, ao histórico e a logs.
- cookie com `Domain` compartilhado: impossível entre `vercel.app` e `railway.app`.
- API sob o mesmo domínio do front: exigiria mudança de infraestrutura e DNS fora do escopo.

## Decisão

Após o callback, o backend cria um ticket aleatório de 256 bits, guarda no Redis o refresh token associado com TTL de 60 segundos e chave derivada por SHA-256 do ticket. O navegador é redirecionado para `FRONTEND_URL/api/v1/auth/complete?ticket=<ticket>`.

O BFF chama `POST /api/v1/auth/session-ticket` sem cookies, apenas com o ticket. O backend consome o ticket com `GETDEL`, rotaciona o refresh token e responde com access token no corpo e cookies de refresh e CSRF. O BFF grava os cookies de sessão no domínio do front e redireciona para o destino guardado em `sp_oidc`.

O ticket é de uso único, não aparece em logs de aplicação, não é aceito duas vezes e expira em 60 segundos. O endpoint é limitado por força bruta por IP. O fluxo antigo de refresh direto no `/complete` fica como fallback para same-site.

## Consequências

- O fluxo funciona com front e API em domínios diferentes sem expor tokens ao navegador.
- O backend ganha um endpoint de troca e uma chave no Redis, sem migration.
- O ticket aparece na URL por poucos segundos; é opaco, de uso único e não concede acesso sem a troca server-side.
- O callback passa a redirecionar falhas para o login do front com códigos estáveis, em vez de devolver problem+json na API.
- A configuração `GOOGLE_REDIRECT_URI` continua apontando para o callback da API e precisa coincidir com o Google Console.
