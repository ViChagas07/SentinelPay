# SPEC 0005: Storage S3 e upload seguro

## Objetivo
Receber PDF/PNG/JPEG com validacao de conteudo, tamanho e estrutura, e armazenar cada documento no bucket privado sob o prefixo do usuario, com metadados no PostgreSQL. Sem URL publica permanente e sem antivirus implementado nesta fase.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: porta `StoragePort` com `put`, `get_stream`, `delete` e URL pre-assinada curta; adaptador S3 compativel com MinIO local e AWS em producao.
- RF2: bucket privado, sem ACL publica, com criptografia do lado do servidor (`AES256`) em cada objeto.
- RF3: chave determinada pelo sistema: `users/{user_id}/{kind}/{analysis_id}/original.{ext}` e `.../report.json`; nome original nunca compoe a chave, apenas metadado sanitizado.
- RF4: validacao por magic bytes (PDF, PNG, JPEG), ignorando extensao e Content-Type do cliente; tamanho maximo `UPLOAD_MAX_MB` abortando durante a leitura; limite de paginas `PDF_MAX_PAGES`; SHA-256.
- RF5: rejeitar PDF com JavaScript ou arquivos embutidos, registrando as evidencias encontradas (nao apenas um erro generico).
- RF6: tabela `documents` (id, owner_id, kind, s3_key, sha256, size, content_type, original_name_sanitized, created_at) e repositorio com filtro obrigatorio por dono.
- RF7: porta `AntivirusScanner` definida, sem implementacao (YAGNI); ausencia registrada como NAO VALIDADO.
- RF8: `POST /api/v1/documents/upload` autenticado e `GET /api/v1/documents/{id}/url` com URL pre-assinada curta; IDOR retorna 404 sem revelar existencia.
- RNF1: nenhum documento e conteudo sao gravados no banco fora do bucket; apenas metadados e hash.
- RNF2: nomes originais sanitizados; sem HTML/controle; nunca usados em logs.
- RNF3: streaming e limites nao carregam o arquivo inteiro em memoria; pypdf recebe o arquivo em threadpool.

## Fora do escopo
Antivirus/malware scanning, OCR, classificacao de documento, geracao de `report.json`, URL publica, CDN, lifecycle/versionamento de bucket e AWS real nesta fase.

## Contrato (endpoints, chaves, erros)
- `POST /api/v1/documents/upload` (multipart `kind` + `file`, Bearer) -> `201` com `id`, `analysis_id`, `kind`, `sha256`, `size`, `content_type`, `original_name_sanitized`, `created_at`.
- `GET /api/v1/documents/{id}/url` (Bearer) -> `200 {url, expires_in}` com URL pre-assinada curta; outro dono -> `404 document_not_found`.
- Chaves: `users/{user_id}/{kind}/{analysis_id}/original.pdf|png|jpg` e `users/{user_id}/{kind}/{analysis_id}/report.json`.
- Erros: `unsupported_document_type` (422), `upload_too_large` (413), `empty_document` (422), `invalid_document` (422), `pdf_page_limit_exceeded` (422), `pdf_active_content` (422 com `evidence`), `encrypted_pdf` (422), `document_not_found` (404), `storage_not_configured` (503).
- Extensao e Content-Type sao definidos pelo detector, nunca pelo cliente. Nome original vira metadado sanitizado.

## Criterios de aceite (cada um vira pelo menos um teste)
1. PDF/PNG/JPEG validos sao detectados por assinatura; arquivo com extensao `.pdf` mas bytes PNG e tratado como PNG; texto/binario arbitrario e recusado.
2. Upload acima do limite e abortado com 413; leitura nao consome o stream inteiro.
3. PDF acima do limite de paginas e recusado; PDF com `/JavaScript` ou `/EmbeddedFile` e recusado com `evidence`.
4. Nome `../../etc/passwd` nao aparece na chave; chave sempre `users/{owner_id}/...`; nome sanitizado e mantido apenas como metadado.
5. Upload valido grava no MinIO sob o prefixo do dono, com SSE, e cria linha em `documents` com hash/tamanho/tipo.
6. Outro usuario nao consegue obter URL nem metadados de documento alheio (IDOR 404).
7. Adaptador S3: put/get stream/delete/URL pre-assinada funcionam contra MinIO; URL nao e publica permanente.
8. Upload anonimo e recusado com 401; erros usam problem+json.
9. Checklist OWASP atualizado com upload/storage e pendencias de antivirus.

## Casos de borda e de abuso
- Arquivo vazio, extensao enganosa, Content-Type enganoso, magic bytes truncados, nome com traversal/controle/nome vazio/grande.
- PDF malformado, criptografado, com muitas paginas, JavaScript, arquivos embutidos, objetos indiretos maliciosos.
- Upload concorrente, stream nao-seekable, falha do S3 apos gravacao (compensacao de objeto), falha do banco.
- IDOR por id de documento; usuario tentando escolher prefixo/chave/nome; URL expirada; bucket ausente.
- Conteudo grande/chunked sem Content-Length; limite de corpo do P03.

## Plano de testes (TDD: teste falho primeiro)
1. Chaves/sanitizacao: prefixo, extensao, traversal e nome vazio.
2. Inspector: magic bytes, limite streaming, paginas, PDF ativo/criptografado, hash.
3. Storage S3: MinIO real via Compose (put/get/delete/presign/SSE).
4. Servico/repositorio: upload valido, compensacao de falha, IDOR.
5. Rotas: 401, 201, 413, 422 problem+json, URL pre-assinada e IDOR 404.
6. Rodar `make check`, `make test-docker`, `make bandit`, `make audit`; atualizar OWASP.

## Riscos e NAO VALIDADO
- Antivirus/malware scanning: **NAO VALIDADO**; porta existe sem implementacao.
- AWS S3 real nao foi exercitado; MinIO local cobre o adaptador. Diferencas de permissao/IAM/SSE-KMS sao NAO VALIDADAS.
- Analise profunda de PDF e sandbox de renderizacao nao existem; a deteccao de conteudo ativo e por marcadores estruturais/brutos e pode gerar falso positivo (tratado como seguro).
- Limite de upload depende de Content-Length + contador de stream; proxies e limites de borda seguem NAO VALIDADOS.
- Bucket lifecycle, versionamento e retencao nao foram configurados.
