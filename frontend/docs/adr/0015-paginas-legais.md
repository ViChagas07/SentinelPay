# ADR 0015: Paginas legais em conteudo tipado por idioma

Data: 2026-11-23.
Status: aceito.

## Contexto

`/termos` e `/privacidade` tinham dois paragrafos vindos do dicionario de rotulos. O produto trata documentos com dados pessoais sensiveis (boletos, contracheques e recibos podem conter CPF, CNPJ, endereco, dados bancarios e salario), entao os documentos precisam cobrir LGPD com profundidade e afirmar apenas o que o codigo confirma.

## Decisao

1. O texto juridico fica em `lib/legal/content/{pt,es,en}.ts`, com estrutura tipada (secoes, paragrafos, listas, tabelas, avisos). O dicionario de i18n continua responsavel apenas por rotulos de interface.
2. `LEGAL_VERSION` e `LEGAL_UPDATED_AT` vivem em `lib/legal/version.ts` e sao a unica fonte para as duas paginas.
3. Dados institucionais vem de variaveis `NEXT_PUBLIC_LEGAL_*`. Campo sem variavel e omitido da interface. Nenhum valor padrao e inventado; quando nao ha e-mail de encarregado, cai para o canal de privacidade configurado e, se ele tambem faltar, para `/suporte`.
4. O layout usa um componente de documento (`features/legal/components/legal-document.tsx`) com sumario sticky no desktop e recolhivel no mobile, ancoras copiaveis, botao de voltar ao topo e CSS de impressao.
5. O idioma PT e a referencia. ES e EN exibem aviso de que a versao em portugues prevalece em caso de divergencia.

## Consequencias

- Texto juridico e rotulos evoluem em ritmos diferentes sem quebrar `check-i18n`.
- O teste de paridade garante que os tres idiomas tenham o mesmo numero de secoes e as mesmas ancoras.
- Toda afirmacao juridica precisa de evidencia no codigo; o inventario da Fase 0 fica no PROGRESS.md e no relatorio da entrega.
- Alterar a versao vigente exige atualizar apenas `lib/legal/version.ts` e os textos de conteudo.

## Alternativas descartadas

- MDX por idioma: exigiria dependencia nova e pipeline de build extra para conteudo estatico e curto.
- Texto no dicionario de rotulos: inviabiliza paragrafos longos, tabelas e revisao juridica por secao, e mistura rotulo de interface com clausula legal.
- CMS externo: adiciona operador e superficie de risco sem necessidade nesta fase.
