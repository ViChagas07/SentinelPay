# ADR 0008: Storage S3, chaves e upload seguro

- Status: aceito
- Data: 2026-11-14

## Contexto
Documentos financeiros precisam ser guardados fora do banco, isolados por usuario, sem URL publica permanente e sem confiar em nome/extensao/Content-Type do cliente. O ambiente local usa MinIO; producao usa AWS S3. A stack e Python 3.11/FastAPI assincrona, e a P05 nao implementa antivirus nem geracao de relatorio.

## Decisao
- Cliente: `boto3` executado em `asyncio.to_thread` (operacoes sincronas fora do event loop), com endpoint configuravel, `path` addressing para MinIO e SigV4. Alternativa `aioboto3` foi descartada por adicionar dependencia/abstracao sem necessidade agora.
- Bucket: privado, sem ACL publica. Cada `put` envia `ServerSideEncryption=AES256`; no local o bucket e criado se ausente, sem ACL publica. Presigned GET e curto (TTL configuravel, padrao 300s).
- Chaves sao determinadas pelo sistema: `users/{owner_id}/{kind}/{analysis_id}/original.{ext}` e `.../report.json`. `analysis_id` e gerado no servidor. O nome original nao entra na chave; e sanitizado (sem path/controle) e salvo apenas como metadado/coluna.
- Upload: tamanho validado por Content-Length e por contador de streaming; magic bytes definem PDF/PNG/JPEG e a extensao; `pypdf` conta paginas e detecta criptografia; marcadores de JavaScript/arquivos embutidos sao procurados no stream com sobreposicao e viram `evidence` no problem+json e log estruturado. Hash SHA-256 e calculado durante a leitura.
- Persistencia: `documents` guarda apenas metadados e a chave. Repositorio filtra obrigatoriamente por `owner_id`; IDOR retorna 404.
- Falha do banco apos o `put` remove o objeto (compensacao). Falha do S3 nao deixa linha no banco.
- Antivirus: porta `AntivirusScanner` definida sem implementacao. A fase registra **NAO VALIDADO** para malware scanning.

## Alternativas consideradas
- URL publica ou objeto com ACL publica: descartado; vazamento permanente e sem isolamento.
- Chave derivada do nome enviado: descartado por traversal/colisao e por confiar no cliente.
- Validar apenas extensao/Content-Type: descartado; trivialmente falsificavel.
- Carregar o arquivo inteiro em memoria para validar: descartado por consumo e negacao de servico.
- `aioboto3`: adiado; boto3 + threadpool e suficiente e mais simples de operar.
- Antivirus fake/no-op: descartado; seria uma falsa garantia. A porta fica sem implementacao.

## Consequencias
O adaptador usa uma API sincrona em threadpool; operacoes concorrentes consomem threads, mas o volume atual nao justifica um cliente async. O local e AWS precisam de configuracao de bucket/permissao; AWS real, IAM e SSE-KMS permanecem NAO VALIDADOS. A deteccao de PDF ativo e conservadora e pode rejeitar PDFs legitimos com marcadores suspeitos. Sem antivirus, arquivos validados por estrutura ainda podem conter malware; isso deve ser resolvido antes de expor downloads em producao.
