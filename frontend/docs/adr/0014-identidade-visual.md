# ADR 0014: identidade visual baseada no símbolo oficial

- Status: aceito
- Data: 2026-11-17
- Fase: F13

## Contexto

O front-end usava um SVG desenhado à mão parecido com o símbolo, mas com traço central em cruz, além de favicons aproximados e nenhum manifest. Os arquivos oficiais foram entregues em 1024x1024. O favicon antigo é RGB, sem canal alfa, e traz um xadrez de transparência gravado nos pixels, então não pode ser reutilizado.

## Decisões

1. A fonte oficial é `SentinelPay_logo_transparent.png`, com alfa real. O recorte usa o bounding box do conteúdo, de 745x748 px, e remove a margem vazia que fazia o símbolo parecer pequeno em headers.
2. Os originais ficam intactos em `assets/brand/originals/` e não são servidos ao navegador.
3. Os derivados servidos ficam em `public/brand/`. Cada tamanho é reduzido com LANCZOS a partir do recorte, sem esticar.
4. A cor foi amostrada do original: o losango usa `#2A716D` e os colchetes com o ponto usam `#4D927F`. Os dois tons viram tokens `--brand-frame` e `--brand-mark`.
5. O traço original tem contraste de 3,19:1 sobre o sidebar `#0F4138`, abaixo do mínimo de 3:1 para o losango mais escuro, que fica em 1,90:1. Uma variante clara com o mesmo desenho usa `#7BBCB0` no losango e `#A7D2CA` nos colchetes e no ponto, com 5,27:1 e 6,93:1. O arquivo original não é recolorido.
6. Em 28 px o losango original tem 0,23 px de traço e desaparece. Uma variante compacta mantém os vértices, os colchetes e o ponto, mas engrossa o losango para 30 unidades, os colchetes para 40 e o ponto para 96 no espaço de 1024. Ela é usada de 20 a 64 px. O símbolo completo fica para Open Graph, relatórios e formatos grandes.
7. O logo em tema claro e escuro é resolvido com duas imagens e classes CSS que seguem `data-theme` e `prefers-color-scheme`, sem JavaScript extra. A imagem oculta sai do layout e da árvore de acessibilidade.
8. O favicon é gerado do zero a partir do símbolo, com versão simplificada sem colchetes e traço mais grosso, pois em 16 e 32 px os detalhes finos desaparecem. O `.ico` contém 16, 32 e 48 px; o `apple-icon` tem fundo sólido petróleo e usa a variante clara.
9. O SVG oficial é reconstruído com geometria medida no raster e validado por comparação visual. Ele é usado como favicon vetorial e no alternador de alertas.
10. Os metadados ficam no layout raiz com arquivos do App Router para favicon, icon e apple-icon, além do manifest em `public/`. O Open Graph usa o símbolo real embutido como data URI dentro de `ImageResponse`.
11. O logo em telas usa `next/image` com largura e altura explícitas. O sidebar e o painel de login usam a variante clara porque o fundo é petróleo.

## Consequências

- O header e a sidebar passam a mostrar o símbolo oficial, com texto em HTML ao lado.
- O favicon de risco alto continua existindo, agora com a geometria oficial e um badge vermelho.
- Relatórios PDF e e-mails não existem no front-end. A versão com fundo branco fica disponível para o backend, que não foi alterado.
- O manifest usa as cores do app e ícones 192 e 512, sem service worker.
- Nenhuma lógica de negócio, rota, autenticação ou tela foi redesenhada.
