# Lacunas de backend para o front-end

Fase: F00 (descoberta).
Data: 2026-11-15.
Escopo: tudo o que as telas do produto precisam e o backend ainda não oferece.

Aviso: não existe pasta `referencia-v0/` nem protótipo navegável neste repositório. A busca por `referencia-v0`, `prototipo`, `wireframe`, `mockup`, `.fig`, `.html`, `.png` e `.jpg` fora de `docs/` não encontrou telas. A lista abaixo cobre as áreas pedidas no escopo do produto (Auth, Usuário e conta, Organização, Painel, Verificação e jobs, Boletos, Contracheques, Recibos e vencimentos, Notificações, Inteligência Antifraude, Busca) e os fluxos que o backend já implementa.

Nenhuma rota proposta aqui existe hoje. Todas são propostas para o backend, com método, payload e resposta desejados. A coluna "Hoje" aponta o arquivo do backend que evidencia a ausência ou a limitação. Quando a coluna diz apenas "não existe", a evidência é a ausência da rota na lista de routers de `backend/src/paysentineliq/interface/api/main.py:207-216` e nos modelos de `backend/src/paysentineliq/infrastructure/db/models.py`.

Prioridades:

- P0: bloqueia o fluxo principal ou impede uma tela de funcionar sem gambiarra.
- P1: necessário para a experiência completa do protótipo.
- P2: importante, mas pode esperar uma fase seguinte.
- P3: melhoria futura.

## 1. Contrato e correções que não são rotas novas

| Tela ou fluxo | Problema hoje | Evidência | Correção proposta | Prioridade |
| --- | --- | --- | --- | --- |
| Upload de documento | `POST /api/v1/documents/upload` devolve `analysis_id`, mas esse UUID não é uma análise persistida. Ele só é usado na chave do S3. Não existe job nem linha em `analyses`. | `interface/api/routes/documents.py:27-71`, `application/commands/documents.py:143-172`, `infrastructure/db/models.py` (`DocumentModel` não tem `analysis_id`) | Remover o campo `analysis_id` da resposta ou renomear para `upload_id`. Se o objetivo for criar job, usar `POST /api/v1/analyses` e não o upload legado. | P0 |
| Preferências de notificação | `PUT /api/v1/notification-preferences` substitui os três canais. O front-end precisa enviar o estado completo, senão desabilita canais sem querer. O locale é alterado como efeito colateral. | `interface/api/routes/notifications.py:179-212`, `application/commands/notifications.py:73-107` | `PATCH /api/v1/notification-preferences` com atualização parcial e sem mexer no locale. Criar `PATCH /api/v1/users/me` para locale e timezone. | P0 |
| Preferências de lembrete | `PUT /api/v1/payables/reminder-preferences` também substitui tudo. | `interface/api/routes/payables.py:98-118` | `PATCH` com atualização parcial, mantendo o `PUT` para compatibilidade. | P1 |
| Erros de validação | `validation_error` não diz qual campo falhou. | `interface/api/problems.py:103-114` | Incluir `errors[]` com `field`, `code` e `message_key`, sem refletir valores sensíveis. | P1 |
| Callback de auth | Falha no callback devolve problem+json na URL da API. O usuário sai do produto e vê JSON. | Resolvido na F25: `GET /api/v1/auth/google/callback` redireciona para `FRONTEND_URL/login?reason=auth_failed&code=<codigo>&error=<codigo>` com allowlist estável. | Nenhuma. | resolvido |
| Login com deep link | O callback sempre redireciona para `FRONTEND_URL`, sem caminho de retorno. | `interface/api/routes/auth.py:134`, `infrastructure/config.py:108` | `GET /api/v1/auth/google/login?return_to=<path>` com allowlist de paths do front-end. | P1 |
| Access token | Não há endpoint de sessão. O front-end precisa tentar `refresh` na inicialização e tratar 401 como "deslogado". | `interface/api/routes/auth.py`, `interface/api/dependencies.py:409-455` | Opcional: `GET /api/v1/auth/session` devolvendo o usuário quando o refresh cookie é válido, ou documentar o 401 do refresh como sinal de deslogado. | P3 |
| Header de replay | O front-end não consegue ler `Idempotency-Replayed` em chamada cross-origin. | O header é setado em `interface/api/routes/analyses.py:116-117`, mas o CORS só expõe `X-Request-ID` (`interface/api/main.py:200`). | Adicionar `Idempotency-Replayed` a `expose_headers` no CORS. | P2 |
| Descrição de vencimento | A descrição padrão é gerada em português fixo, mesmo quando a interface está em es ou en. | `infrastructure/ai/graph.py:866-868` usa o literal "Conta de consumo" quando emissor e referência faltam. | Gerar a descrição no locale do job ou devolver um `message_key` para o front-end traduzir. | P2 |

## 2. Auth

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Login | Iniciar o fluxo Google e voltar para a tela de origem. | Resolvido na F25 para o retorno de sessão: o callback redireciona para `FRONTEND_URL/api/v1/auth/complete?ticket=<ticket>` e o destino continua no cookie `sp_oidc`. Ainda não existe `return_to` no backend. | `GET /api/v1/auth/google/login?return_to=/boletos`; validar allowlist; resposta 302. | P1 |
| Callback com erro | Mostrar erro amigável no front-end. | Resolvido na F25: falhas redirecionam para `/login?reason=auth_failed&code=<code>&error=<code>` com mensagens em pt, es e en. | Nenhuma. | resolvido |
| Sessão | Saber se há sessão antes de renderizar o shell. | Só é possível tentar `POST /api/v1/auth/refresh`. | `GET /api/v1/auth/session` com cookie de refresh e CSRF; 200 com o mesmo `user` do refresh; 401 se não houver sessão. | P3 |
| Logout global | Encerrar todas as sessões. | Logout revoga a família atual e o `jti` atual. | `POST /api/v1/auth/logout-all`; 204; revoga todas as famílias do usuário. | P2 |
| MFA | Segunda etapa de login. | Não existe. | Fluxo OIDC com `acr_values` ou TOTP; endpoints próprios. | P2 |
| Exibir erro de rate limit | Orientar o usuário a aguardar. | 429 já traz `Retry-After`. | Nenhuma mudança necessária. | n/a |
| Cookie de sessão | Manter access e refresh fora do alcance de JavaScript. | Resolvido na F25 para o fluxo Google: o callback emite ticket de uso único, o BFF troca em `POST /api/v1/auth/session-ticket` e grava cookies first-party HttpOnly. O backend não expõe tokens ao JavaScript. | Emitir `Set-Cookie` com access token HttpOnly e `Path=/` apenas se o BFF for eliminado. | P3 |
| Retorno de erro no login | Mostrar mensagem clara ao voltar do Google. | Resolvido na F25: códigos `invalid_state`, `google_auth_failed`, `access_denied`, `email_not_verified`, `too_many_attempts` e `security_service_unavailable` chegam ao login. | Nenhuma. | resolvido |

## 3. Usuário e conta

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Perfil | Editar nome de exibição. | Só `GET /api/v1/users/me`. | `PATCH /api/v1/users/me` com `{"name": "..."}`; 200 com o perfil. | P1 |
| Idioma e fuso | Alterar `preferred_locale` e `timezone` sem passar por notificações. | Locale só muda via `PUT /notification-preferences`; timezone não muda. | `PATCH /api/v1/users/me` com `{"preferred_locale": "pt-BR", "timezone": "America/Sao_Paulo"}`; validar locale e IANA timezone. | P0 |
| Excluir conta | Direito de eliminação (LGPD). | Não existe. | `DELETE /api/v1/users/me` com confirmação; 202 ou 204; apaga ou anonimiza dados e revoga sessões. | P1 |
| Exportar dados | Portabilidade (LGPD). | Não existe. | `POST /api/v1/users/me/export`; 202 com `export_id`; `GET /api/v1/users/me/export/{id}` com URL assinada. | P1 |
| Sessões | Listar dispositivos e revogar. | Não existe. | `GET /api/v1/users/me/sessions`; `DELETE /api/v1/users/me/sessions/{id}`; `DELETE /api/v1/users/me/sessions`. | P2 |
| Avatar do Google | Exibir a foto real no shell. | O backend não guarda a foto do Google; o shell usa iniciais do nome real. | `avatar_url` no perfil, atualizado pelo `picture` do ID token. | P2 |
| Papel | Mostrar badge de admin. | `role` já vem em `/users/me`. | Nenhuma mudança necessária. | n/a |

## 4. Organização

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Seletor no shell | Mostrar organização e plano reais na sidebar. | Não existe entidade de organização. O componente está pronto, mas não recebe dados. | `GET /api/v1/organizations/current` com `id`, `name`, `plan` e `role`; o shell mostra sem dropdown quando houver uma só. | P0 |
| Organização | Agrupar usuários, documentos e análises por empresa. | Não existe entidade de organização. Todo dado é por `owner_id` individual. | `GET /api/v1/organizations/current`; `PATCH /api/v1/organizations/current`; `GET /api/v1/organizations/current/members`; `POST /api/v1/organizations/current/invites`; `DELETE /api/v1/organizations/current/members/{id}`. Exige mudança de modelo e de autorização. | P2 |
| Papéis | Admin, analista e leitor dentro da organização. | Só existe `user` e `admin` global. | `role` por organização (`owner`, `admin`, `analyst`, `viewer`) e RBAC por rota. | P2 |
| Uso e cobrança | Mostrar consumo e limites. | Não existe medição por organização. | `GET /api/v1/organizations/current/usage` com contadores de análises, armazenamento e assentos; `GET /api/v1/organizations/current/subscription`. | P3 |
| Convite | Convidar por e-mail. | Não existe. | `POST /api/v1/organizations/current/invites`; `GET` e `DELETE` de convites; e-mail transacional. | P3 |

## 5. Painel

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Cartões do painel | Total de análises, por status, por banda, risco alto, vencimentos próximos e não lidas. | Só listas paginadas sem total. | `GET /api/v1/dashboard/summary?from=&to=` devolvendo contadores por status e banda, total de vencimentos por status, próximo vencimento e notificações não lidas. | P0 |
| Série temporal | Gráfico de análises e risco por dia. | Não existe agregação. | `GET /api/v1/dashboard/trends?from=&to=&bucket=day` com `points[]` de data, total, low, attention, high. | P1 |
| Atividade recente | Lista mista de análises, vencimentos e notificações. | Não existe feed unificado. | `GET /api/v1/dashboard/activity?limit=` com `items[]` de tipo, id, título, timestamp e status. | P2 |
| Filtro por período | Ver o painel do mês. | Não existe. | Query `from` e `to` no summary e no trends. | P1 |
| Saúde da fila | Mostrar se há processamento atrasado. | Não existe endpoint de fila para o usuário. | `GET /api/v1/dashboard/jobs` com contadores `queued`, `processing`, `failed`, `degraded` e tempo médio. | P2 |

## 6. Verificação e jobs

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Filtrar análises | Separar boletos, contracheques e recibos; filtrar por status, banda e período. | `GET /api/v1/analyses` só aceita `limit` e `cursor`. | Estender `GET /api/v1/analyses` com `kind`, `status`, `band`, `created_from`, `created_to`, `q` e `limit`/`cursor`. | P0 |
| Nome do documento na lista | Identificar a análise sem abrir. | A lista não traz nome do arquivo nem documento. | Incluir `document_name` e `document_id` nos itens da lista. | P0 |
| Progresso por etapa | Mostrar "lendo documento", "aplicando regras", "gerando explicação". | Resolvido na P18.1: `GET /api/v1/analyses/{id}` devolve `progress` com `percent`, `stage`, `detail`, `started_at` e `indeterminate`; `GET /api/v1/analyses/{id}/events` entrega SSE com snapshot e eventos `progress`. | Nenhuma mudança necessária. Percentual e etapa vêm do pipeline, com subprogresso de OCR por página. | n/a |
| Linha do tempo | Exibir eventos e retries. | O SSE entrega progresso, status e cancelamento, mas não a lista histórica de eventos e retries. | `GET /api/v1/analyses/{id}/history` com `event_type`, `rule_code`, `degradation_flags`, `payload` seguro e `created_at`. | P2 |
| Cancelar | Interromper análise enfileirada ou em processamento. | Resolvido na P18.1: `POST /api/v1/analyses/{id}/cancel`, restrito ao dono, idempotente, 202 com `cancelling` ou `cancelled`, 409 `analysis_not_cancellable` em estado terminal. | Nenhuma mudança necessária. O worker aborta entre etapas, em páginas do OCR e em chamadas longas de RAG/LLM. | n/a |
| Reprocessar | Tentar de novo após falha. | Não existe. | `POST /api/v1/analyses/{id}/retry`; 202; volta para `queued`. | P1 |
| Excluir análise | Remover job e documento (LGPD). | Não existe. | `DELETE /api/v1/analyses/{id}`; 204; apaga documento, relatório e eventos. | P1 |
| Baixar relatório | Exportar o JSON da análise. | Relatório existe no bucket, sem rota. | `GET /api/v1/analyses/{id}/report` com URL assinada ou JSON. | P2 |
| Versões do motor | Mostrar regra, modelo e prompt usados. | `rule_set_version` e `model_versions` ficam no relatório, não na API. | Incluir `rule_set_version`, `model_versions` e `created_at` no detalhe. | P1 |
| Documento original | Abrir o PDF ou imagem analisada. | O detalhe não devolve `document_id`. A rota `GET /documents/{id}/url` aceita qualquer documento do dono, mas o id da análise não é exposto. | Incluir `document_id` e `document_url` (presign curto) no detalhe, ou `GET /api/v1/analyses/{id}/document-url`. | P0 |
| Reenviar por `document_id` | Evitar upload duplicado. | `POST /api/v1/analyses` só aceita multipart. | `POST /api/v1/analyses` com JSON `{"document_id": "..."}` e `kind`, mantendo multipart. | P3 |
| Analisar em lote | Vários arquivos de uma vez. | Não existe. | `POST /api/v1/analyses/batch` multipart com múltiplos arquivos; 202 com lista de jobs. | P3 |

## 7. Boletos

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Lista de boletos | Ver só boletos. | Não há filtro `kind` na lista de análises. | `GET /api/v1/analyses?kind=boleto` (ver seção 6). | P0 |
| Campos do boleto | Mostrar linha digitável, código de barras, valor, vencimento, beneficiário, pagador e banco. | O resultado da API omite `fields`. | Incluir `fields` tipado no resultado de boleto: `line`, `barcode`, `amount`, `due_date`, `beneficiary`, `beneficiary_tax_id`, `payer`, `payer_tax_id`, `additional_tax_ids`, `bank_header`, `decoded`. | P0 |
| Confiança por campo | Indicar campo ilegível. | Confiança existe no relatório, não na API. | Incluir `confidence` por campo e um indicador de `illegible`. | P1 |
| Banco e moeda | Exibir banco e moeda decodificados. | Existem em `decoded` no relatório, não na API. | Expor `decoded.bank_code`, `bank_name`, `currency`, `due_factor`, `due_date`, `amount`, `free_field`. | P1 |
| Evidência por regra | Explicar o porquê do score. | A API traz `rule_id`, `severity`, `weight`, `message_key` e `source`. | Manter. O front-end traduz `message_key` com dicionário próprio. | n/a |

## 8. Contracheques

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Lista de contracheques | Ver só contracheques. | Não há filtro `kind`. | `GET /api/v1/analyses?kind=payslip`. | P0 |
| Campos do contracheque | Mostrar empregador, empregado, competência, itens, totais, líquido, base de IRRF e dependentes. | O resultado da API omite `fields`. | Incluir `fields`: `employer_name`, `employer_cnpj`, `employee_name`, `employee_cpf_masked`, `employee_cpf_valid`, `competency`, `items[]`, `total_earnings`, `total_deductions`, `net`, `irrf_base`, `dependents`, `layout_confidence`. | P0 |
| Itens da folha | Listar proventos e descontos com categoria. | Itens existem no relatório, não na API. | Expor `items[]` com `description`, `kind`, `category`, `amount`, `overtime_percent`, `confidence`. | P0 |
| Regras não verificáveis | Distinguir "não verificável" de "disparada". | `AnalysisEvidence` perde o `status` do domínio. | Incluir `status` (`triggered`, `not_verifiable`) na evidência de contracheque. | P1 |
| Tabelas regulatórias | Mostrar a fonte e a vigência de INSS, IRRF e salário mínimo. | Não há endpoint. | `GET /api/v1/intelligence/regulatory-tables?competency=YYYY-MM` com `source`, `valid_from`, `valid_to` e `authoritative`. | P1 |

## 9. Recibos e vencimentos

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Lista de recibos | Ver só recibos. | Não há filtro `kind`. | `GET /api/v1/analyses?kind=receipt`. | P0 |
| Campos do recibo | Mostrar emissor, referência, valor, vencimento e linha. | O resultado da API omite `fields`. | Incluir `fields`: `line`, `barcode`, `amount`, `due_date`, `issuer`, `reference`, `decoded`, `barcode_checked`, `not_validated`. | P0 |
| Detalhe do vencimento | Abrir um vencimento a partir da notificação ou da lista. | Não existe `GET /api/v1/payables/{id}`. | `GET /api/v1/payables/{payable_id}` devolvendo o mesmo schema da lista, mais `analysis` resumida. | P0 |
| Resumo de vencimentos | Cartões de pendentes, confirmar, vencidos e total. | Não existe agregação. | `GET /api/v1/payables/summary` com contadores por status, total por status e próximo vencimento. | P0 |
| Calendário | Visão mensal por `due_date`. | A lista aceita `due_from` e `due_to`, mas sem contagem por dia. | `GET /api/v1/payables/calendar?from=&to=` com `days[]` de data, quantidade e total. | P2 |
| Busca | Procurar por descrição. | A lista não tem `q`. | `GET /api/v1/payables?q=...` com busca em descrição. | P1 |
| Editar descrição e valor | Corrigir dado extraído. | Só `PATCH /due-date`. | `PATCH /api/v1/payables/{id}` com `description`, `amount` e `due_date`; registrar auditoria. | P2 |
| Ações em lote | Marcar vários como pagos ou dispensados. | Só ações individuais. | `POST /api/v1/payables/bulk` com `ids[]` e `action` (`pay`, `dismiss`, `confirm`); 200 com resultados por id. | P2 |
| Data de pagamento | Histórico e relatório. | `paid` não guarda data de pagamento. | `POST /api/v1/payables/{id}/pay` com `{"paid_at": "YYYY-MM-DD"}` opcional e campo `paid_at` na resposta. | P2 |
| Exportar | CSV ou planilha. | Não existe. | `GET /api/v1/payables/export?format=csv&status=...` com URL assinada. | P2 |
| Anexar comprovante | Guardar recibo do pagamento. | Não existe. | `POST /api/v1/payables/{id}/receipt` multipart; `DELETE` para remover. | P3 |
| Enriquecer notificação | Mostrar descrição e valor na central. | Payload tem `payable_id`, `due_date`, `offset_days`, `type` e `channel`, mas não descrição nem valor. | Incluir `description` e `amount` no payload ou permitir buscar o vencimento pelo GET individual. | P0 |

## 10. Notificações

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Contador por tipo | Badge por categoria. | `unread-count` devolve só o total. | `GET /api/v1/notifications/unread-count?group_by=type` com `by_type` e `total`. | P1 |
| Contagem de alertas de risco alto | Título e favicon com contagem real. | Só é possível paginar `GET /notifications?type=high_risk_detected&unread=true` até 500 itens. | `GET /api/v1/notifications/unread-count?type=high_risk_detected` ou endpoint equivalente com `unread` exato. | P1 |
| Status de entrega | Mostrar se e-mail, SMS e WhatsApp saíram. | Entregas existem no banco, sem rota. | `GET /api/v1/notifications/{id}/deliveries` com `channel`, `status`, `attempts`, `sent_at` e `last_error_safe`. | P1 |
| Preferência por tipo | Silenciar só um tipo. | Preferência é por canal, não por tipo. | Estender `PUT/PATCH /notification-preferences` com matriz `types` e `channels`. | P2 |
| Marcar como não lida | Voltar o estado. | Só marcar como lida. | `POST /api/v1/notifications/{id}/unread`; 200 com a notificação. | P3 |
| Excluir em lote | Limpar a central. | Só exclusão individual. | `POST /api/v1/notifications/delete` com `ids[]`; 200 com `deleted`. | P2 |
| Filtrar por período | Ver notificações antigas. | Só tipo e não lida. | Adicionar `created_from` e `created_to` ao `GET /notifications`. | P2 |
| Texto da notificação | Título e corpo prontos. | A API devolve `type` e `payload`; o texto é responsabilidade do front-end. | Manter como está e documentar as chaves de payload. Ou devolver `title` e `body` localizados. | P3 |
| Preferência de e-mail | Ver o e-mail de destino completo. | O GET devolve mascarado, por privacidade. | Manter mascarado e exibir o e-mail da conta em `/users/me`. | n/a |

## 11. Inteligência Antifraude

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Catálogo de regras | Explicar cada evidência sem dicionário hardcoded no front-end. | Regras existem no domínio, sem rota. | `GET /api/v1/intelligence/rules?kind=boleto` com `rule_id`, `version`, `severity`, `weight`, `message_key`, `source`, `authoritative`. | P1 |
| Fontes e vigência | Mostrar de onde a regra veio. | `source` aparece na evidência, mas não há catálogo. | `GET /api/v1/intelligence/sources` com caminho, tipo, versão, vigência e `authoritative`. | P1 |
| Modelos e versões | Mostrar versão do ML, do LLM e do classificador. | Só existe no relatório interno. | `GET /api/v1/intelligence/models` com nome, versão, hash, métricas sintéticas e data de treino. | P2 |
| Feedback | Marcar falso positivo ou falso negativo. | Não existe. | `POST /api/v1/analyses/{id}/feedback` com `label` (`false_positive`, `false_negative`, `correct`) e `comment` opcional; 201. | P1 |
| Tendências | Ver padrões de fraude no tempo. | Não existe. | `GET /api/v1/intelligence/trends?from=&to=` com regras mais disparadas e bandas por período. | P2 |
| Glossário | Explicar termos (linha digitável, DV, competência). | Não existe endpoint. | `GET /api/v1/intelligence/glossary?locale=pt-BR` com termos e definições. Alternativa: conteúdo estático no front-end com fonte revisada. | P2 |
| Explicação da evidência | Texto humano por `message_key`. | Só a chave. | Manter `message_key` estável e publicar o catálogo de mensagens em um contrato versionado. | P1 |

## 12. Busca

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Busca global | Procurar por análise, boleto, contracheque, recibo, vencimento e notificação. | Não existe endpoint de busca. A paleta do shell mostra o estado de indisponibilidade e oferece apenas navegação e ações. | `GET /api/v1/search?q=&types=&limit=&cursor=` com grupos `analyses`, `payables`, `notifications` e `documents`, cada um com itens resumidos e `next_cursor`. | P0 |
| Sugestões | Autocomplete. | Não existe. | `GET /api/v1/search/suggest?q=` com até 10 sugestões de beneficiário, descrição e id. | P2 |
| Busca em boleto | Procurar por beneficiário, linha ou valor. | Só metadados de análise, sem `q`. | Incluir `q` em `GET /analyses` e indexar campos extraídos de forma segura. | P1 |
| Busca em vencimento | Procurar por descrição. | Só status e data. | `GET /payables?q=`. | P1 |
| Busca em notificação | Procurar por texto do payload. | Só tipo e não lida. | `GET /notifications?q=` com busca em `payload` permitido. | P2 |
| Privacidade | Não indexar conteúdo bruto de documento. | Não existe índice de busca. | Indexar apenas metadados e campos extraídos mascarados; nunca o texto OCR completo. | P0 |

## 13. Observabilidade e operação para o usuário

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Status do serviço | Avisar manutenção. | `/health` e `/ready` existem. | O front-end pode usar `GET /ready` em diagnóstico interno, sem expor ao usuário final. | n/a |
| Fila do usuário | Mostrar processamentos pendentes. | `GET /analyses?status=queued` não existe. | Coberto pelo filtro de status na seção 6. | P1 |
| Uso e cota | Mostrar quantas análises simultâneas restam. | A cota é 2, mas não há endpoint de uso. | `GET /api/v1/usage` com `active_analyses`, `max_concurrent`, `storage_bytes` e `plan`. | P2 |

## 14. Dados que o front-end não deve inventar

- Cada tela deve usar estados vazios, de carregamento e de erro para os campos que a API não devolve. Não preencher nome de documento, beneficiário, valor, vencimento ou classe com dado fictício.
- A classe de risco deve vir de `band` da API. O front-end não recalcula a partir de `score`.
- A tradução de `message_key` e de `type` de notificação é responsabilidade do front-end, com dicionário versionado. Isso não é lacuna de backend, é contrato de i18n.
- Enquanto as rotas propostas não existirem, as telas correspondentes devem mostrar o estado "indisponível" ou usar apenas as rotas existentes, sem simular resposta.

## 15. F06: Painel Principal (2026-11-16)

O painel usa apenas `GET /api/v1/users/me`, `GET /api/v1/analyses`, `GET /api/v1/payables` e as rotas de notificação já usadas pelo shell. Como não há agregação, os resumos são calculados sobre as listas paginadas, com limite de 500 análises e 50 vencimentos. Quando o limite corta a janela, a interface mostra "Amostra parcial" e os contadores recebem "+". A média e a conformidade são apresentadas como média e proporção da amostra do período.

| Tela | Necessidade | Hoje | Proposta | Prioridade |
| --- | --- | --- | --- | --- |
| Painel, risco médio | média do período, média anterior, variação, tamanho da amostra e indicador de truncamento | Não existe agregação. O front pagina até 500 análises e calcula sobre a amostra. | `GET /api/v1/dashboard/summary?from=&to=` com `period`, `average`, `previous_average`, `delta`, `sample_size` e `truncated`. | P0 |
| Painel, conformidade | percentual de análises concluídas com risco baixo, com numerador e denominador | Calculado sobre a amostra de análises. | Incluir `conformity: { low, total, percent }` no summary. | P0 |
| Painel, alertas de risco alto | contagem exata no período e destino dos alertas não lidos | O front conta análises na faixa alta da amostra. O shell pagina notificações até 500 para o título e o favicon. | Incluir `high_risk` no summary e `GET /api/v1/notifications/unread-count?type=high_risk_detected` para o shell. | P1 |
| Painel, comprovantes pendentes | contagem exata de payables com `pending_confirmation` | O front usa a primeira página de ativos e mostra "+" quando há `next_cursor`. | `GET /api/v1/payables/summary` com `counts` por status e `pending_confirmation`. | P0 |
| Painel, distribuição | série diária por faixa no período | O front agrupa a amostra de análises por dia no fuso do usuário. | `GET /api/v1/dashboard/trends?from=&to=&bucket=day` com `points[]` de `date`, `low`, `attention`, `high` e `truncated`. | P1 |
| Painel, próximos vencimentos | lista ativa ordenada por vencimento, com descrição, valor e status | `GET /api/v1/payables` entrega os campos e a ordenação. O front reordena para garantia. | Nenhuma mudança, desde que a ordenação por `due_date` ascendente continue documentada. | n/a |
| Análises recentes | número do documento, emissor, CNPJ e valor | O item da lista tem apenas id, status, tipo, score, banda, erro e datas. A interface mostra "Indisponível" nesses campos. | Incluir `document_name`, `document_id` e um resumo de `fields` (emissor, CNPJ e valor) em `GET /api/v1/analyses`, ou expor os campos no detalhe e um `fields_summary` na lista. | P0 |
| Detalhe da análise | abrir a linha em `/verificacao/[id]` | A rota de detalhe existe na API, mas a tela do front ainda é provisória. | Implementar a tela de detalhe na fase correspondente usando `GET /api/v1/analyses/{id}`. | P1 |

Fallback atual do painel:

- O bloco de risco médio, a conformidade, as métricas e o gráfico usam os itens reais de `GET /api/v1/analyses` no período, com nota visível sobre a ausência de totais agregados.
- Quando a amostra é truncada, o contador recebe "+" e o painel mostra "Amostra parcial".
- Emissor, CNPJ e valor aparecem como "Indisponível", com nota na seção e link para esta lacuna.
- O contador de comprovantes pendentes usa a primeira página de payables ativos. Se houver `next_cursor` e a contagem for maior que zero, aparece "+". Se for zero, aparece "Indisponível".
- O título e o favicon continuam vindo do shell, que usa a contagem paginada de alertas não lidos.

## 16. F07: Central de Verificação e dossiê (2026-11-16)

A F07 usa `POST /api/v1/analyses`, `GET /api/v1/analyses/{id}` e `GET /api/v1/analyses`.
Nenhuma rota nova foi chamada. O contrato só oferece polling e os estados `queued`,
`processing`, `completed`, `degraded` e `failed`.

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Upload, limite | O produto pediu 300 MB, mas o backend aceita no máximo `UPLOAD_MAX_MB` (25 MiB no `.env.example`) e responde 413 acima disso. | O cliente valida com `NEXT_PUBLIC_UPLOAD_MAX_MB` espelhando o backend. Não há rota que informe o limite. | Ajustar `UPLOAD_MAX_MB` para 300 e publicar o limite em `GET /api/v1/config/upload` ou no detalhe de capacidades. | P0 |
| Upload, progresso do servidor | O XHR mede o envio até o BFF do front-end. Depois de 100%, o tempo de inspeção e gravação no S3 não é reportado. | Não existe progresso de processamento no contrato. | `POST /api/v1/analyses` com `202` já cobre o aceite; opcionalmente expor `upload_state` no detalhe. | P3 |
| Job, etapa atual | Mostrar leitura, extração, regras, classificação e justificativa com estado ativo. | O detalhe não expõe etapa, percentual, tentativa nem início de processamento. Os eventos existem em `analysis_events`, sem rota. | `GET /api/v1/analyses/{id}/events` com `event_type`, `stage`, `status` e `created_at`, ou `stage` e `progress` no detalhe. | P1 |
| Job, retry e cancelamento | Tentar de novo um job com falha e cancelar um job em fila. | Não existe `POST /retry` nem `POST /cancel`. O front só repete o polling e oferece novo envio. | `POST /api/v1/analyses/{id}/retry` (202, volta para `queued`) e `POST /api/v1/analyses/{id}/cancel` (202 ou 409 se terminal). | P1 |
| Dossiê, documento | Visualizar PDF ou imagem da análise aberta pela lista ou após recarregar. | O detalhe não devolve `document_id` nem URL assinada. | Incluir `document_id` e `document_url` (presign curto) no detalhe, ou `GET /api/v1/analyses/{id}/document-url`. | P0 |
| Dossiê, campos extraídos | Tabela de campos com valores reais e botão de copiar. | `AnalysisResultResponse` não inclui `fields`; o relatório no bucket tem os campos. | Incluir `fields` tipado por `kind` no resultado, com confiança e indicador de ilegível. | P0 |
| Dossiê, evidências | Mostrar trecho, campo, página e marcas sincronizadas sobre o documento, sem tratar regra não verificável como violação. | A evidência traz `rule_id`, `severity`, `weight`, `message_key` e `source`. Não há status da regra, trecho, campo, página nem coordenadas. | Incluir `status` (`triggered`, `not_verifiable`, `not_applicable`, `passed`), `page`, `bbox`, `excerpt` e `field` por evidência, quando disponíveis, e a página do documento no detalhe. | P1 |
| Dossiê, versões e idioma | Mostrar idioma detectado e versão do pipeline. | O detalhe não devolve `rule_set_version`, `model_versions` nem idioma. | Incluir `rule_set_version`, `model_versions` e `language` no detalhe. | P2 |
| Dossiê, relatório | Baixar o relatório da análise. | O relatório JSON existe no bucket, sem rota. | `GET /api/v1/analyses/{id}/report` com URL assinada ou JSON. | P2 |
| Dossiê, revisão | Marcar a análise como revisada. | Não existe estado nem rota de revisão. | `POST /api/v1/analyses/{id}/review` com `reviewed_at` e, se necessário, `note`. | P2 |
| Verificações recentes | Separar boletos e contracheques. | `GET /api/v1/analyses` não aceita `kind` nem `status`. | Estender a lista com `kind`, `status`, `band`, `created_from`, `created_to` e `q`. | P0 |
| Verificações recentes | Identificar o documento sem abrir. | O item da lista não traz nome, emissor nem valor. | Incluir `document_name`, `document_id` e um resumo de `fields`. | P0 |

Fallbacks da F07:

- O upload usa o limite real do backend (25 MiB) e mostra a divergência de 300 MB nesta tabela.
- Sem etapa, a análise mostra progresso indeterminado, tempo decorrido e as etapas documentadas do pipeline sem inventar uma etapa ativa.
- Sem documento na API, o visualizador só aparece quando o arquivo local ainda está em memória após o envio.
- Sem coordenadas, a lista de evidências não desenha marcas sobre o documento e explica a limitação.
- Sem `fields`, a tabela de campos mostra estado vazio honesto.

## 17. F08: Listas de boletos e folha (2026-11-16)

As rotas `/boletos` e `/folha` usam somente `GET /api/v1/analyses?limit=50&cursor=...`.
O item devolve `id`, `status`, `kind`, `score`, `band`, `error_code`, `created_at` e
`updated_at`. Não há filtro, total por classe, ordenação no servidor, exportação nem
exclusão. Para não inventar dados, o front percorre o cursor até 500 análises, aplica
filtros e paginação sobre essa amostra real, marca a amostra truncada com "+" e mostra
"Indisponível" nos campos ausentes. Exportar CSV e excluir não aparecem.

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Listas, filtros | filtrar por tipo, período, classe, status, faixa de valor, emissor/CNPJ e texto | Só `limit` e `cursor`; o front filtra a amostra. | `GET /api/v1/analyses?kind=&status=&band=&created_from=&created_to=&amount_min=&amount_max=&issuer=&q=&sort=&direction=&limit=&cursor=` devolvendo a página já filtrada e ordenada. | P0 |
| Listas, contagens | contagem exata por Todos, Baixo, Médio e Alto com os demais filtros aplicados | Não há contagem no servidor; o front conta a amostra de até 500 itens. | Incluir `counts: { all, low, attention, high }` na resposta da lista, calculado com os filtros exceto `band`. | P0 |
| Listas, paginação | paginação no servidor por página, com total | Cursor apenas; sem total e sem salto de página. | `page` e `page_size` com `total` e `total_pages`, mantendo `cursor` como alternativa. | P0 |
| Listas, campos | colunas de número do documento, beneficiário, CNPJ, valor, vencimento, empregador, competência e líquido | O item só tem identificador da análise, status, tipo, score, banda e datas. A interface mostra "Indisponível". | Incluir no item `document_id`, `document_number`, `beneficiary_name`, `beneficiary_tax_id`, `amount`, `due_date`, `employer_name`, `employer_tax_id`, `competency` e `net_amount`, mascarando dados sensíveis conforme a política. | P0 |
| Listas, busca | busca textual por documento, beneficiário, CNPJ ou linha digitável | Só é possível buscar o id da análise no front. | `q` no servidor com os campos extraídos indexados e mascarados; nunca indexar OCR bruto. | P0 |
| Listas, exportação | exportar CSV da visão filtrada | Não existe rota. | `GET /api/v1/analyses/export?format=csv&kind=&status=&band=&...` com `text/csv` e URL assinada ou stream. | P1 |
| Listas, exclusão | excluir um documento e suas análises | Não existe `DELETE` de análise nem de documento. | `DELETE /api/v1/analyses/{id}` com 204 e auditoria, ou `DELETE /api/v1/documents/{id}` com confirmação. | P1 |
| Linhas em análise | atualizar sozinhas quando o job termina | O polling funciona por análise, sem evento nem push. O front usa backoff de 2,5 s a 20 s. | Manter o polling ou oferecer `GET /api/v1/analyses/events?since=` ou SSE para atualizar a lista sem varrer tudo. | P2 |

Rotas de exportação e exclusão (não exibidas na interface):

- Exportar CSV em `/boletos` e `/folha`: `GET /api/v1/analyses/export?format=csv&kind=&status=&band=&created_from=&created_to=&q=&sort=&direction=`, resposta `200 text/csv` com `Content-Disposition` ou URL assinada de curta duração. A tela depende da visão filtrada atual, não apenas da página visível.
- Excluir documento em `/boletos` e `/folha`: `DELETE /api/v1/analyses/{analysis_id}`, resposta `204 No Content`, com auditoria e confirmação explícita. Se a exclusão for por documento, usar `DELETE /api/v1/documents/{document_id}` e remover as análises vinculadas.

Os dois botões ficam ocultos até as rotas existirem, conforme a regra da fase.

Fallbacks da F08:

- `GET /api/v1/analyses` é lido por cursor até 10 páginas de 50 itens. Com mais resultados,
  a página mostra a nota de amostra parcial e as contagens recebem "+".
- Filtros de período, status, classe e busca são aplicados sobre a amostra real. Faixa de
  valor, emissor/CNPJ e ordenação por valor aparecem desabilitados e explicados.
- As linhas mostram o id da análise em mono no lugar do número do documento e
  "Indisponível" nos demais campos extraídos.
- Exportar CSV e excluir não são exibidos porque as rotas não existem.
- Se o backend expuser filtros, contagens e total, a tela pode trocar a amostra por uma
  chamada por página sem mudar a URL.

## 18. F09: Pagamentos, notificações e inteligência (2026-11-16)

As três rotas usam apenas o que existe no contrato atual: `GET/POST/PATCH` de payables,
preferências de lembrete globais, notificações com cursor, leitura, contagem e
preferências de canal. Não há endpoint de inteligência antifraude. A interface não cria
vencimentos manuais, canais por notificação, verificação de contato, métricas de modelo
nem casos históricos.

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Pagamentos, emissor | lista de recibos com emissor separado da descrição | O payable devolve `description`, que pode ser genérica, e não tem nome ou CNPJ do emissor. A tela mostra "Descrição / emissor" e explica a limitação. | Incluir `issuer_name`, `issuer_tax_id` e `description` no payable, com máscara de dados sensíveis. | P0 |
| Pagamentos, cadastro manual | tipo, emissor, valor, vencimento, anexo opcional, antecedência e canais no cadastro | Só existe `POST /api/v1/analyses` com `kind=receipt` e arquivo obrigatório. O pipeline extrai os campos. Emissor, valor e vencimento aparecem desabilitados como "Extraído após a análise". O arquivo não é opcional. | `POST /api/v1/payables` com `kind`, `issuer`, `amount`, `due_date`, `attachment` opcional, `reminder_days[]` e `channels[]`; resposta 201 com o payable. Ou ampliar o upload de recibo com metadados explícitos. | P0 |
| Pagamentos, anexo | anexo opcional do recibo | O upload exige arquivo e não devolve URL do documento. | Aceitar `attachment` opcional e expor `document_url` assinada no payable. | P1 |
| Pagamentos, lembrete por recibo | antecedência e canais por recibo | `PUT /payables/reminder-preferences` é global e só aceita `in_app`; e-mail, SMS e WhatsApp ficam em `notification-preferences`. | Aceitar `reminder` por payable, com `offsets_days`, `local_time` e canais autorizados. | P1 |
| Pagamentos, edição | editar descrição e valor além do vencimento | Só existe `PATCH /api/v1/payables/{id}/due-date`. | `PATCH /api/v1/payables/{id}` com `description`, `amount`, `due_date` e validação de estado. | P1 |
| Pagamentos, exclusão | excluir vencimento com confirmação | Não existe `DELETE`. O item aparece desabilitado com explicação e a tela registra a lacuna. | `DELETE /api/v1/payables/{id}` com 204, auditoria e regra para payables pagos. | P0 |
| Pagamentos, detalhe | abrir um vencimento isolado e linkar de notificação | Não existe `GET /payables/{id}`. A tela carrega até 500 payables e destaca o id; se não estiver na amostra, mostra aviso honesto. | `GET /api/v1/payables/{id}` com o mesmo payload da lista. | P0 |
| Pagamentos, resumo e paginação | contagens exatas por situação e total | O front calcula sobre a amostra ativa de até 500 e sinaliza truncamento. A paginação é local sobre a amostra. | `GET /api/v1/payables/summary` e lista com `total`, `page`, `page_size` e filtros de situação. | P0 |
| Pagamentos, histórico | saber quando foi pago, confirmado ou dispensado e por quem | O payable só tem `updated_at`; não há histórico de transições. | `GET /api/v1/payables/{id}/events` com `action`, `actor`, `created_at` e metadados. | P2 |
| Pagamentos, comprovante | anexar comprovante ao marcar como pago | `POST /pay` só muda o status. | Aceitar `POST /pay` multipart com comprovante opcional e URL assinada. | P2 |
| Notificações, tempo real | atualização imediata de novos alertas | Não há SSE, WebSocket ou long polling. A página usa polling de 20 s e o contrato só oferece polling. | `GET /api/v1/notifications/events` SSE com `event: notification`, `id` e payload, ou `since` incremental. | P1 |
| Notificações, canal | filtrar a lista por e-mail, SMS, WhatsApp ou app | O item não tem `channel`; apenas alguns payloads trazem `channel` (normalmente `in_app`). O filtro aparece desabilitado e explicado. | Incluir `channel` e `delivery_status` no item de notificação e aceitar `channel` no filtro da lista. | P0 |
| Notificações, contato verificado | mostrar se o destino foi verificado | `ChannelPreference` tem apenas `consented_at`, sem `verified_at` ou estado de verificação. A interface chama de consentimento e registra a lacuna. | Incluir `verified_at`, `verification_status` e `verification_sent_at` por canal, com fluxo de código. | P1 |
| Notificações, preferências parciais | alterar um canal sem reenviar os outros | O GET devolve destinos mascarados e o PUT substitui os três canais; SMS/WhatsApp habilitados exigem o número E.164 completo. A interface pede reentrada do número para salvar. | `PATCH /api/v1/notification-preferences` por canal, ou devolver um token/últimos dígitos que permita atualizar sem expor o destino completo. | P0 |
| Notificações, filtro de lidas | ver apenas lidas | `unread=false` retorna todas; não há filtro de lidas. A interface oferece Todas e Não lidas. | Aceitar `read=true` ou `read_state=read|unread|all`. | P2 |
| Notificações, contagens por tipo | badge e resumo por tipo | Só existe `unread-count` total. | `GET /api/v1/notifications/summary` com `unread`, `by_type` e `by_channel`. | P2 |
| Notificações, título e corpo | exibir o texto sem montar no cliente | O item devolve `type` e `payload`; o front traduz e compõe a mensagem. | Incluir `title` e `body` localizados ou `title_key` e `body_key` com parâmetros. | P2 |
| Inteligência, visão | padrões, casos históricos, métricas do classificador e explicações | Não há endpoint. A rota mostra "Em desenvolvimento" sem números ou gráficos. | `GET /api/v1/intelligence/overview` com `rules`, `cases`, `classifier_metrics` e `explanations`, com estado vazio honesto e versões. | P1 |
| Inteligência, catálogo de regras | listar regras, fontes e versões | Não existe. | `GET /api/v1/intelligence/rules?version=&status=` com `rule_id`, `version`, `source`, `severity`, `description`. | P1 |
| Inteligência, casos | casos históricos com desfecho e sinais | Não existe. | `GET /api/v1/intelligence/cases?from=&to=` com ids anonimizados, desfecho e evidências agregadas. | P2 |
| Inteligência, métricas | métricas do classificador por versão e coorte | Não existe. | `GET /api/v1/intelligence/model-metrics?model=&version=` com precisão, recall, calibração e tamanho da amostra. | P1 |
| Inteligência, feedback | registrar feedback humano sobre falsos positivos | Não existe. | `POST /api/v1/intelligence/feedback` com `analysis_id`, `label` e `note`, e listagem agregada. | P2 |

Fallbacks da F09:

- Pagamentos usam até 500 payables reais por cursor. O resumo e a linha do tempo usam
  apenas a amostra ativa; a paginação da visão é local. Com cursor restante, a tela avisa.
- O cadastro de recibo envia o arquivo real para análise e explica que emissor, valor,
  vencimento e anexo opcional não são aceitos como metadados manuais.
- Lembretes são globais (`in_app`) e os canais de e-mail, SMS e WhatsApp ficam em
  Notificações. Não existe lembrete por recibo.
- Notificações usam polling de 20 s, filtro de tipo e de não lidas no servidor; canal fica
  desabilitado. Cada item deriva o destino real do payload e não inventa um link.
- Preferências de canal usam atualização otimista com reversão. Número telefônico já
  habilitado precisa ser redigitado por causa do GET mascarado e do PUT completo.
- A rota de inteligência é somente um estado "Em desenvolvimento" com a lista do que
  virá, sem métricas, gráficos ou casos fictícios.

## 19. F10: Minha conta (2026-11-16)

`GET /users/me` devolve perfil, papel, locale e fuso. `POST /auth/logout` encerra a sessão
atual. Não existe edição de perfil, organização, membros, plano, lista de sessões, logout
global, uso de armazenamento, exportação ou exclusão. Preferências de idioma, tema e
formato de data ficam nos cookies `locale`, `theme` e `date_format` e são aplicadas pelo
front. A página mostra estados indisponíveis e não inventa dados.

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Perfil, nome | editar o nome de exibição | `GET /users/me` devolve `name`, mas não existe `PATCH`. O campo é somente leitura e explica a lacuna. | `PATCH /api/v1/users/me` com `{ "name": "..." }`, validação de 1 a 120 caracteres, resposta com o perfil atualizado. | P1 |
| Perfil, avatar | mostrar a foto real do Google | A API não devolve `avatar_url`. O front usa iniciais do nome e e-mail e explica. | Incluir `avatar_url` e `avatar_source` no perfil, com URL assinada ou cache permitido. | P1 |
| Organização | nome, plano e papel da organização | Não existe entidade de organização. A tela mostra o papel da conta e "Não disponível" nos demais campos. | `GET /api/v1/organizations/me` com `id`, `name`, `plan`, `role`; `GET /api/v1/organizations/{id}/members` quando o papel permitir. | P0 |
| Membros | lista de membros com papel e convite | Não existe. A seção não lista ninguém. | `GET /api/v1/organizations/{id}/members`, `POST /invites` e `DELETE /members/{id}` com RBAC. | P1 |
| Preferências da conta | idioma, tema e formato de data persistidos na conta | Não há endpoint. O front usa cookies e não usa `PUT /notification-preferences`, que substitui canais e exige reentrada de telefone. | `GET/PATCH /api/v1/users/me/preferences` com `locale`, `theme` e `date_format`, sem efeito colateral em canais. | P0 |
| Sessões | listar sessões e encerrar todas | Não há lista nem logout global. A tela mostra a sessão atual e desabilita "Sair de todos os dispositivos". | `GET /api/v1/auth/sessions` com `id`, `created_at`, `last_seen_at`, `ip`, `user_agent`, `current`; `DELETE /auth/sessions/{id}`; `POST /auth/logout-all`. | P1 |
| Início da sessão | mostrar quando a sessão começou | O refresh token não expõe `created_at`; a tela mostra a expiração do cookie BFF e diz que o início não é informado. | Incluir `created_at` na sessão atual ou no `GET /auth/sessions`. | P2 |
| Uso e armazenamento | documentos armazenados e bytes usados | Não existe endpoint de uso. A tela mostra "Não informado pela API". | `GET /api/v1/account/usage` com `documents_count`, `storage_bytes`, `by_kind` e `updated_at`. | P1 |
| Exportação LGPD | exportar dados da conta | Não existe rota. A tela encaminha ao canal de privacidade configurado por env. | `POST /api/v1/account/export` criando job assíncrono e `GET /account/export/{id}` com status e URL assinada. | P0 |
| Exclusão LGPD | excluir a conta com confirmação e reautenticação | Não existe `DELETE /account`. O diálogo exige a palavra traduzida e encaminha ao canal de privacidade sem chamar endpoint falso. | `DELETE /api/v1/account` com `confirmation`, reautenticação recente, auditoria e prazo de retenção legal. | P0 |
| Provedor de login | trocar ou adicionar provedor | O backend só aceita Google. A tela informa isso e não oferece troca. | `GET /api/v1/auth/providers` e fluxo de vinculação/desvinculação, se o produto permitir. | P2 |
| Canal de privacidade | contato quando não há endpoint | A tela usa `NEXT_PUBLIC_PRIVACY_CONTACT_URL` ou `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`, com fallback `/suporte`. | Manter o canal por env até existirem exportação e exclusão. | P2 |

Fallbacks da F10:

- Idioma, tema e formato de data ficam em cookies; a ADR 0011 explica e o formato de data
  afeta chamadas de `formatDate` com `dateStyle`.
- Nome, e-mail e avatar são somente leitura. A API não tem PATCH nem foto.
- Organização, plano, membros, sessões, uso, exportação e exclusão mostram estados
  indisponíveis ou encaminham ao canal de privacidade.
- A expiração da sessão vem do cookie BFF; o início real não é exibido porque não existe
  no contrato.
- O diálogo de exclusão exige a palavra de confirmação, usa Zod e `react-hook-form`, e
  nunca chama uma rota destrutiva inexistente.

## 20. F11: Revisão final (2026-11-16)

A revisão final não criou endpoint, tela ou funcionalidade de negócio. As lacunas das
seções anteriores continuam válidas. Esta fase confirmou os contratos usados pelo
front-end e manteve duas observações de prioridade baixa.

| Tela ou fluxo | Necessidade | Hoje | Proposta (método, rota, payload, resposta) | Prioridade |
| --- | --- | --- | --- | --- |
| Tratamento de 429 | avisar e respeitar Retry-After | O backend usa Token Bucket e o front lê `Retry-After` quando presente. Sem o cabeçalho, a interface usa uma mensagem genérica. | Manter `Retry-After` em segundos nas respostas 429 e documentar o limite por rota. | P2 |
| Saúde da API | distinguir indisponibilidade de erro de sessão | O front usa os estados existentes de erro e a página `/servico-indisponivel`. Não há endpoint de status. | `GET /health` público e estável para o front exibir manutenção sem tentar autenticar. | P2 |

Fallbacks da F11:

- 401, 403 e 429 já são tratados com os contratos existentes. Nenhuma resposta de API
  foi inventada.
- O Lighthouse usa uma sessão real criada pelo script de teste no container do backend,
  não uma rota de produto.
- A observabilidade opcional não depende de endpoint novo: o DSN do Sentry é configurado
  por variável de ambiente e desligado por padrão.

## 21. F12: progresso e cancelamento (2026-11-17)

A P18.1 fechou as lacunas de progresso e cancelamento. Contratos agora dispon�veis:

- `GET /api/v1/analyses/{id}` inclui `progress` com `percent` (0 a 100), `stage` (`validation`, `ocr`, `extraction`, `classification`, `rag`, `llm`, `persistence`), `detail`, `started_at` e `indeterminate`, al�m de `cancelled_at`.
- `GET /api/v1/analyses/{id}/events` entrega `text/event-stream` com snapshot inicial, eventos `progress` e `done`. O snapshot permite reconectar e abrir a tela no meio da an�lise.
- `POST /api/v1/analyses/{id}/cancel` responde 202 com `{ analysis_id, status }`. Estados `completed`, `degraded` e `failed` retornam 409 `analysis_not_cancellable`.
- Status novos: `running`, `cancelling` e `cancelled`. `processing` continua aceito como alias legado.

O front usa SSE e cai para polling de `GET /analyses/{id}` ap�s duas falhas de conex�o. A linha do tempo hist�rica completa de eventos e retries continua fora do contrato e segue como lacuna P2.

## 22. F13: identidade visual (2026-11-17)

O front entrega o kit de marca em `frontend/public/brand/` e mant�m os originais intactos em `frontend/assets/brand/originals/`. O favicon oficial recebido tem xadrez de transpar�ncia gravado nos pixels e foi descartado. Os favicons em uso foram gerados do s�mbolo transparente.

Relat�rios PDF e e-mails transacionais n�o s�o gerados pelo front. Para aplicar a marca nesses canais, o backend precisa de uma c�pia pr�pria do asset, porque n�o deve ler `frontend/public` em runtime.

| Canal | Necessidade | Hoje | Proposta | Prioridade |
| --- | --- | --- | --- | --- |
| Relat�rio PDF, cabe�alho | usar a vers�o com fundo branco, com propor��o e respiro preservados | O relat�rio JSON existe no bucket, sem template versionado no reposit�rio. | Copiar `logo-symbol-on-white-512.png` para os assets do gerador de PDF e inserir no cabe�alho, com altura entre 24 e 40 px e �rea de respiro de 25%. | P2 |
| E-mails transacionais, cabe�alho | usar a vers�o com fundo branco, com `alt` e propor��o preservados | N�o h� templates de e-mail no backend. | Copiar o mesmo asset para o servi�o de e-mail e inserir no cabe�alho. Nunca usar a variante clara em fundo branco nem a vers�o colorida em fundo escuro. | P2 |

## 23. F15 e F16: login com e-mail e senha (2026-11-23)

O redesenho do painel direito de `/login` introduziu as abas "Entrar" e "Criar conta". A F16 ligou
essas abas ao fluxo real de e-mail e senha, atr�s da flag `AUTH_PASSWORD_ENABLED`, que vem do
endpoint p�blico de capacidades.

Contratos agora atendidos pelo backend (prefixo `/api/v1/auth`):

| Rota | M�todo | Payload | Resposta | Status |
| --- | --- | --- | --- | --- |
| `/auth/capabilities` | GET | nenhum | `{ password_enabled, signup_enabled, password_reset_enabled, google_enabled }` | atendido |
| `/auth/password-policy` | GET | nenhum | `{ min_length, max_length, requirements, hibp_enabled }` | atendido |
| `/auth/register` | POST | `{ nome_completo, email, senha, aceite_termos, aceite_privacidade }` | 202 neutro e e-mail de verifica��o; 503 quando a flag est� desligada | atendido |
| `/auth/login` | POST | `{ email, senha }` | 200 com o mesmo par de cookies do OIDC; 401 gen�rico; 403 `email_not_verified`; 429 com `Retry-After` | atendido |
| `/auth/verify-email` | POST | `{ token }` | 204 com `email_verified_at` atualizado; 400 `invalid_auth_token` | atendido |
| `/auth/resend-verification` | POST | `{ email }` | 202 neutro com limite por IP e e-mail | atendido |
| `/auth/forgot-password` | POST | `{ email }` | 202 neutro, tempo equalizado e link de 30 minutos | atendido |
| `/auth/reset-password` | POST | `{ token, nova_senha }` | 204, revoga as sess�es ativas e envia aviso | atendido |
| `/auth/change-password` | POST | `{ senha_atual, nova_senha }` | 204 com sess�o autenticada | atendido, sem tela de conta ainda |

O BFF exp�e os mesmos caminhos em `/api/v1/auth/*`, valida a origem, mant�m os cookies HttpOnly e
nunca devolve tokens ao JavaScript.

### Pend�ncias que dependem de decis�o externa

| Necessidade | Hoje | O que falta | Prioridade |
| --- | --- | --- | --- |
| Provedor de e-mail e dom�nio remetente | O c�digo tem a porta `EmailSender`, um emissor de desenvolvimento que grava em `var/auth-outbox` e um adaptador SMTP gen�rico por vari�veis de ambiente. | Contratar o provedor ou apontar o SMTP para um dom�nio remetente verificado, com SPF, DKIM e DMARC, e trocar `AUTH_EMAIL_PROVIDER` para `smtp` em produ��o. | P1 |
| Cadastro habilitado em produ��o | `AUTH_PASSWORD_ENABLED` est� ligada por padr�o e habilita o login por senha. O cadastro s� aparece com SMTP pronto, porque `signup_enabled` exige provedor de e-mail. | Configurar SMTP e `APP_BASE_URL` reais antes de divulgar o cadastro. | P1 |
| Captcha anti-bot | `CAPTCHA_ENABLED` existe e est� desligada. Nenhum provedor foi contratado. | Escolher o provedor, implementar a verifica��o no backend e s� ent�o ligar a flag e renderizar o widget. | P2 |
| Pol�tica de vincula��o Google e senha | Implementada: vincula apenas conta com e-mail verificado e `email_verified=true` do Google; caso contr�rio, bloqueia e registra o evento. | Revis�o jur�dica e de produto da pol�tica registrada no ADR 0029. | P2 |
| Reten��o de `auth_events` | Sem prazo autom�tico de expurgo. A exclus�o de conta mant�m o evento com `user_id` nulo. | Definir o prazo de guarda dos registros de seguran�a e agendar a rotina de expurgo no worker. | P2 |
| Limites de rate limit e bloqueio | Valores padr�o configur�veis por ambiente: 20 tentativas de login por IP e 10 por e-mail em 15 minutos; 10 e 5 para cadastro; 10 e 5 para esqueci; 10 e 3 para reenvio; bloqueio progressivo a partir de 5 falhas, at� 1 hora. | Validar os n�meros com dados reais de uso e ajustar as vari�veis `AUTH_RATE_LIMIT_*` e `ACCOUNT_LOCKOUT_*`. | P2 |
| Tela de troca de senha na conta | O endpoint `/auth/change-password` existe e segue o mesmo contrato, mas `/account` ainda n�o tem a se��o. | Adicionar a se��o em `/account` consumindo o endpoint. | P2 |
| Verifica��o de senha vazada (HIBP) | `PASSWORD_HIBP_ENABLED` existe e est� desligada. | Aprovar sa�da de rede para a API do HIBP por k-anonymity antes de ligar. | P3 |
## 24. F21: cadastro com Google e foto de perfil (2026-11-24)

O cadastro por Google ja funciona hoje: `login_with_google` cria a conta quando o `google_sub` nao
existe, marca o e-mail como verificado e registra consentimento em `google_signin`. A foto de perfil, porem, nao e coletada nem armazenada, e nao ha senha local para contas Google.

| Necessidade | Metodo e rota desejada | Payload | Resposta esperada | Hoje | Tela que depende | Prioridade |
| --- | --- | --- | --- | --- | --- | --- |
| Guardar a foto do perfil Google | `POST /api/v1/users/me` ou campo `avatar_url` em `GET /users/me` | `{ avatar_url }` ou `null` para remover | `200` com o perfil atualizado | O escopo `profile` entrega `picture` no ID token, mas `GoogleIdentity` so mapeia `google_sub`, `email` e `name`. O model `users` nao tem coluna de avatar e o front desenha iniciais em `user-avatar.tsx`. | Sidebar, menu do usuario e `/account` | P2 |
| Trocar a foto | mesma rota com `PUT /api/v1/users/me/avatar` | `{ avatar_url }` | `200` | inexistente | `/account` secao perfil | P3 |

Notas de implementacao para o backend, se decidir atender:

- Adicionar `picture_url` em `GoogleIdentity` e ler `claims.get("picture")` em `google_oidc.py`.
- Criar coluna `avatar_url` em `users` com migration, validando `https` e host do Google, para evitar
  carregar URL arbitraria no `img` do front.
- O front ja tem `UserAvatar` com fallback de iniciais; basta consumir o campo quando existir.
- Senha local para conta Google nao existe por desenho. O acesso e sempre OIDC e a senha nunca e
  extraida do Google. Cadastro com e-mail e senha e um fluxo separado, dependente de SMTP e da flag
  `signup_enabled`.
