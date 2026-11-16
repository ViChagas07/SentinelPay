# ADR 0006: Landing pública

- Status: aceito
- Data: 2026-11-16
- Fase: F05

## Contexto

A F05 precisa de uma landing pública em `/` com i18n, temas, SEO, ilustrações
animadas e conteúdo verificável. A rota não pode depender de API, de dados de
sessão além do cookie, nem de bibliotecas pesadas. O restante do produto usa
Next.js App Router, Tailwind, componentes da F02, `motion` e os cookies de tema
e idioma da F01.

## Decisão

### Renderização

- `app/page.tsx` é um componente de servidor. Ele lê o idioma e a presença do
  cookie de sessão, monta o texto traduzido e entrega o HTML inicial.
- As ilhas de cliente ficam restritas ao header, ao documento animado, à seção
  de rolagem fixa, à régua interativa e ao rodapé.
- Nenhuma chamada de API é feita na landing. O CTA apenas aponta para `/painel`
  e deixa o middleware aplicar a regra de sessão.
- O rótulo do CTA usa a presença do cookie `sp_session`, não uma chamada ao
  backend. Isso evita latência e mantém a landing honesta sobre o que sabe.

### Conteúdo

- Todo texto novo fica nos dicionários `pt`, `es` e `en`.
- Nenhum número, cliente, depoimento, selo ou métrica é criado. A única exceção
  visual é o score ilustrativo da demonstração, sempre rotulado como
  "Exemplo ilustrativo".
- A seção de normas cita apenas o que existe no backend e na base de
  conhecimento: manual FEBRABAN, layouts de boleto, documentos do BACEN, regras
  de contracheque e a marcação de regra não verificável quando falta fonte
  oficial registrada.
- O documento do hero é HTML/SVG, não imagem, e a animação de leitura roda uma
  vez. Com movimento reduzido, o estado final aparece imediatamente.

### Movimento

- O documento usa transições CSS e alguns temporizadores para revelar as
  evidências e o resultado.
- A seção de etapas usa `position: sticky` e um listener de rolagem com
  `requestAnimationFrame` para trocar o visual.
- A régua é um `input[type="range"]` nativo estilizado, com teclado, foco
  visível e `aria-live` para a explicação.
- `prefers-reduced-motion` desliga as animações e mantém o conteúdo final.

### SEO

- `generateMetadata` devolve title, description, canonical, Open Graph e Twitter
  nos três idiomas.
- A imagem Open Graph é gerada por `app/opengraph-image.tsx` com `next/og` e usa
  o idioma do cookie. Crawlers sem cookie recebem a versão em português.
- `NEXT_PUBLIC_SITE_URL` define a base absoluta dos metadados. O fallback local
  é `http://localhost:3000`.

### Apoio e páginas legais

- O rodapé mostra o ano atual, Termos, Privacidade, Suporte e seletor de idioma.
- `NEXT_PUBLIC_SUPPORT_URL` define o canal externo. Sem ele, o link leva a
  `/suporte`, que mostra um estado honesto de canal não configurado.
- As páginas legais existentes ganham comentário de revisão jurídica no código.

## Consequências

- A landing continua dinâmica por causa dos cookies de tema e idioma, mas sem
  dados de servidor. O custo de renderização é baixo e o HTML inicial já contém
  o conteúdo principal.
- O score ilustrativo não representa uma análise real e não deve ser usado como
  promessa de resultado.
- O link de suporte depende de configuração de ambiente. Sem ela, o estado
  vazio é explícito.
- A página de suporte é uma rota pública de apoio, fora das rotas privadas.
