# ADR 0031: segredos derivados e token de metricas opcional

- Status: aceito
- Data: 2026-11-24

## Contexto

O deploy no Railway falhou na inicializacao porque `Settings` exigia `SECURITY_HASH_SECRET` e
`METRICS_TOKEN` fora de `APP_ENV=local`. Os dois valores sao derivados ou opcionais por natureza:

1. `SECURITY_HASH_SECRET` so alimenta HMAC de chaves de rate limit/forca bruta, o HKDF da cifra
   de destino de notificacao e o hash de identificadores da observabilidade. Ele nao assina nada
   que o cliente valide, entao pode ser derivado de forma deterministica de `JWT_SECRET` sem
   quebrar sessoes entre replicas.
2. `METRICS_TOKEN` protege apenas `GET /metrics`, rota fora do schema publico. Exigir o token na
   subida derruba a API inteira por causa de uma rota de operacao que pode ficar bloqueada.

## Decisao

1. Fora de `APP_ENV=local`, se `SECURITY_HASH_SECRET` estiver vazio, ele e derivado de
   `JWT_SECRET` por HKDF-SHA256 com salt e info fixos do projeto, codificado em base64url. Valor
   explicito continua tendo precedencia, e o resultado e estavel entre processo, worker e replicas.
2. Fora de `APP_ENV=local`, `METRICS_TOKEN` vazio nao bloqueia a subida. A rota `/metrics` ja
   responde 401 quando o token esperado esta vazio, portanto o endpoint fica fechado em vez de
   derrubar a aplicacao. Placeholders (`CHANGE_ME`, `local-metrics-token`) continuam recusados.
3. `SECURITY_HASH_SECRET` continua aceito como configuracao explicita para quem quiser rotacionar
   independente do JWT. Trocar o segredo invalida chaves de rate limit em andamento, contadores de
   forca bruta e destinos cifrados de notificacao, entao a rotacao exige recadastro de telefone.

## Alternativas consideradas

- Manter os dois obrigatorios e apenas documentar o preenchimento no Railway: descartado porque o
  erro de deploy ja aconteceu e a falha e de disponibilidade, nao de seguranca.
- Gerar `SECURITY_HASH_SECRET` aleatorio em runtime: descartado porque cada processo teria um
  segredo diferente e as chaves de rate limit deixariam de ser compartilhadas entre API e worker.
- Auto-gerar `METRICS_TOKEN` e imprimir no log: descartado porque vazaria credencial em log.

## Consequencias

- Deploy sobe com apenas `JWT_SECRET` para os segredos internos; `/metrics` fica inacessivel ate
  alguem definir `METRICS_TOKEN`.
- `SECURITY_HASH_SECRET` derivado do JWT significa que rotacionar o JWT tambem rotaciona o hash
  interno, com o mesmo efeito sobre rate limit e destinos cifrados.
- Nenhuma migration ou mudanca de contrato de API.
