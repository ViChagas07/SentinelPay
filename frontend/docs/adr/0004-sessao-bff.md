# ADR 0004: Sessão com BFF e cookie HttpOnly

- Status: aceito
- Data: 2026-11-15
- Fase: F03

## Contexto

O backend entrega o access token apenas no corpo de `POST /api/v1/auth/refresh`. O refresh token fica em cookie HttpOnly com `Path=/api/v1/auth`, e o CSRF token fica em cookie legível por JS. O callback do OIDC sempre redireciona para `FRONTEND_URL` fixo, sem parâmetro de retorno.

A exigência de produto é que nenhuma credencial fique exposta ao JavaScript do navegador. Guardar o access token em `localStorage`, `sessionStorage` ou em memória do cliente viola essa exigência.

## Decisão

### Camada BFF

O Next.js atua como Backend for Frontend:

- O access token é gravado em cookie `sp_session`: HttpOnly, `SameSite=Lax`, `Path=/`, `Secure` em produção, `Max-Age` igual a `expires_in` retornado pela API.
- O cliente chama apenas `/api/v1/*` no mesmo host. O Route Handler `app/api/v1/[...path]/route.ts` valida a sessão, injeta `Authorization: Bearer` e repassa a resposta.
- O navegador nunca recebe o access token em corpo, URL ou cookie legível.
- O cookie `sp_session` contém o JWT assinado pelo backend. Alteração é detectada pela validação de assinatura no backend; não há criptografia adicional no front-end.

### Retorno do OIDC sem `return_to`

- `/api/v1/auth/login` valida `next` e grava o cookie `sp_oidc` (HttpOnly, 10 minutos) com o destino.
- O backend volta para `FRONTEND_URL`. O middleware detecta `sp_oidc` e redireciona para `/api/v1/auth/complete`.
- O caminho `/api/v1/auth/complete` está sob `Path=/api/v1/auth`, então recebe `refresh_token` e `csrf_token`.
- O BFF troca o refresh, grava `sp_session`, apaga `sp_oidc` e redireciona para o destino validado.
- Se não houver `sp_oidc`, o endpoint ainda tenta o refresh e decide entre `/painel` e `/login`.

### Renovação e expiração

- O BFF tenta o refresh uma vez quando a chamada ao backend responde 401.
- O refresh rotaciona `refresh_token`; os `Set-Cookie` do backend são encaminhados ao navegador para preservar a rotação.
- Se o refresh falhar, `sp_session` é apagado e a resposta é 401 com `code=session_expired`.
- O cliente limpa o cache do TanStack Query e redireciona para `/login?reason=expired`.
- O middleware faz checagem otimista pela presença de `sp_session`. A validação real acontece no BFF.

### Logout

- `/api/v1/auth/logout` lê refresh e CSRF, chama o backend, encaminha a limpeza de cookies, apaga `sp_session` e responde 204.
- O cliente limpa o cache e navega para `/login`.
- Se o backend falhar, o cookie local ainda é apagado e o usuário sai da interface.

### Rotas

- Públicas: `/`, `/login`, `/termos`, `/privacidade`.
- Privadas: `/painel`, `/verificacao`, `/boletos`, `/folha`, `/pagamentos`, `/inteligencia`, `/notificacoes`, `/account`.
- Sem sessão em rota privada: redireciona para `/login?next=<destino>`.
- Com sessão em `/login`: redireciona para `/painel`.
- `/dev/design` continua bloqueada fora de desenvolvimento.

### Deploy

O BFF lê os cookies do backend no servidor Next. Isso exige que front-end e API sejam same-site e compartilhem host, o que acontece em desenvolvimento porque ambos usam `localhost` (porta não compõe escopo de cookie).

Em produção, a API deve ser exposta sob o mesmo host do front-end por proxy reverso, por exemplo `app.exemplo.com/api/v1/*` encaminhando para o serviço FastAPI. Sem isso, o cookie `refresh_token` fica no host da API, o servidor Next não o vê e o BFF não consegue renovar a sessão. A alternativa seria o navegador falar direto com a API, o que exigiria access token em memória no cliente e violaria a exigência de credencial inacessível ao JS.

`API_INTERNAL_URL` é a URL usada pelo servidor Next para alcançar o FastAPI. `NEXT_PUBLIC_API_URL` continua existindo apenas para desenvolvimento direto e diagnóstico.

## Alternativas descartadas

- Access token em `localStorage`: vulnerável a XSS e viola o requisito.
- Access token em variável de módulo no cliente: continua acessível a JS e se perde a cada navegação de página inteira.
- Refresh direto do navegador contra a API: exigiria ler o cookie CSRF e guardar o access token em memória. Descartado pelo mesmo motivo.
- Servir o access token em cookie pelo próprio backend: o backend não oferece essa opção hoje.
- Sessão stateless em cookie criptografado pelo Next: exigiria uma chave de criptografia no front-end e não resolveria a rotação de refresh do backend.

## Consequências

- Todo o tráfego de produto passa pelo servidor Next, o que adiciona um salto e exige atenção a streaming e upload de até 25 MiB.
- O upload multipart é repassado como corpo bruto, sem reparse, preservando o boundary.
- O BFF nunca encaminha `Authorization`, `Cookie` ou `Set-Cookie` arbitrários do navegador para a API.
- O middleware usa a convenção `middleware.ts` pedida na fase. O Next 16 chama essa convenção de `proxy.ts` e a mantém com aviso de depreciação; a migração é um rename de arquivo.
- Um token de acesso vazado por outro caminho continua limitado a 15 minutos e revogável por `jti`.
- Quando o backend oferecer `return_to` e redirecionamento de erro para o front-end, o cookie `sp_oidc` pode ser simplificado.
