# ADR 0019 - Notificacoes: portas, consentimento e provedores pendentes

## Status

Aceito em 2026-11-14.

## Contexto

A P13 criou a tabela `notifications` como outbox da analise e a P14 acrescentou lembretes de
vencimento. Falta a Central de Notificacoes e a entrega por e-mail, SMS e WhatsApp sem acoplar
o dominio a um provedor e sem vazar dados pessoais em logs ou mensagens.

## Decisao

### Portas e adaptadores

- `EmailPort`, `SmsPort` e `WhatsAppPort` ficam em `application/ports`. O dominio nao conhece
  SMTP nem provedores.
- E-mail: `SmtpEmailAdapter` com `smtplib` sincrono em `asyncio.to_thread`, sem dependencia
  nova. No local aponta para Mailpit; em producao usa as variaveis `SMTP_*`.
- SMS e WhatsApp: `ConsoleSmsAdapter` e `ConsoleWhatsAppAdapter` registram apenas
  `sms_console_send`/`whatsapp_console_send`, sem destino nem corpo. Nenhum provedor e
  escolhido nesta fase.

### Central e entregas

- `notifications` continua sendo a fonte de verdade do item da Central. `read_at` marca leitura;
  apagar e hard delete com cascata nas entregas.
- `notification_deliveries` tem unicidade `(notification_id, channel)` e guarda status,
  tentativas e erro seguro. A tarefa de entrega cria a linha de forma idempotente e ignora
  canais ja enviados/pulados.
- Uma tarefa por notificacao processa os tres canais em sequencia, isolando excecoes. Retry com
  backoff exponencial reenvia apenas canais pendentes/falhos.
- A Central nunca depende do sucesso externo: a notificacao e criada na mesma transacao do
  evento de analise/payable e a entrega e assincrona.

### Consentimento

- E-mail transacional: habilitado por padrao para o e-mail da conta; sem destino arbitrario.
- SMS/WhatsApp: desabilitados por padrao. Exigem `enabled`, `consented_at` e telefone E.164.
- Telefone e cifrado com AES-GCM; chave de 256 bits derivada por HKDF-SHA256 de
  `SECURITY_HASH_SECRET`. O texto cifrado tem prefixo de versao para rotacao futura.
- Destino nunca entra em log, erro persistido ou template externo.

### i18n

- Templates estaticos em codigo para os 9 locales suportados, com fallback para `en` quando o
  `preferred_locale` e desconhecido. O conteudo externo e generico e nao contem valores, nomes,
  documentos ou resultado detalhado.

### Provedor de SMS/WhatsApp: PENDENTE

Nao escolher provedor sem decisao de produto. Criterios para a proxima decisao:

- custo por mensagem e previsibilidade de faturamento;
- cobertura Brasil/internacional e qualidade de entrega;
- suporte a remetente alfanumerico e opt-out;
- WhatsApp Business: template aprovado, categoria utilitaria, janela de atendimento e BSP;
- contrato/LGPD, suboperadores, regiao de armazenamento e retencao;
- API idempotente, webhooks de status, limites e SLA.

Ate la, o adaptador `console` e o unico implementado e deve ser tratado como NAO VALIDADO para
entrega real.

## Consequencias

- Trocar `console` por um provedor exige apenas um novo adaptador e configuracao; dominio,
  Central e tarefas nao mudam.
- Telefones so podem ser decifrados por processos com o mesmo `SECURITY_HASH_SECRET`; rotacao
  de segredo exige migracao de dados (nao implementada nesta fase).
- O e-mail depende de SMTP configurado; sem SMTP o canal falha de forma segura e a Central
  permanece disponivel.
- Nao ha WebSocket nem polling automatico no servidor; o cliente consulta a API.

## Alternativas rejeitadas

- Escolher um provedor de SMS/WhatsApp agora: sem criterios de custo/cobertura/template.
- Enviar direto do caso de uso: acoplaria a requisicao HTTP ao provedor e duplicaria tentativas.
- Guardar telefone em texto puro: viola minimizacao/LGPD e o requisito de protecao.
- WebSocket: YAGNI para o volume e a simplicidade atuais.
