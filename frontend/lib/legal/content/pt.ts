import type { LegalContent } from "./types";

export const pt: LegalContent = {
  terms: {
    title: "Termos de uso",
    subtitle:
      "Condições para usar o SentinelPay na análise de boletos, contracheques e recibos brasileiros.",
    sections: [
      {
        id: "aceite-e-definicoes",
        title: "Aceite e definições",
        blocks: [
          {
            type: "paragraph",
            text: "Estes Termos regulam o uso do SentinelPay. Ao marcar a caixa de aceite na tela de login e concluir o cadastro ou a autenticação, por Google ou por e-mail e senha, você concorda com estes Termos e com a Política de privacidade.",
          },
          {
            type: "paragraph",
            text: "Para facilitar a leitura, os termos abaixo têm os seguintes significados:",
          },
          {
            type: "list",
            items: [
              "SentinelPay: a plataforma, incluindo o site, a aplicação web, a API e o pipeline de análise.",
              "Usuário: pessoa física maior de 18 anos, autenticada por uma conta Google ou por e-mail e senha.",
              "Documento: arquivo PDF, PNG ou JPG enviado pelo usuário, como boleto, contracheque ou recibo.",
              "Análise: processamento do documento que gera pontuação de risco de 0 a 100, classe de risco, evidências, justificativa e campos extraídos.",
              "Dossiê: conjunto exibido na plataforma com o resultado da análise, as evidências e os campos extraídos.",
              "Conta: registro criado pelo primeiro acesso com Google ou pelo cadastro por e-mail e senha, vinculado a um e-mail verificado.",
            ],
          },
          {
            type: "note",
            text: "Se você não concorda com estes Termos, não use o serviço.",
          },
        ],
      },
      {
        id: "o-que-o-servico-faz",
        title: "O que o serviço faz e o que não faz",
        blocks: [
          {
            type: "paragraph",
            text: "O SentinelPay analisa boletos, contracheques e recibos brasileiros. O resultado combina regras determinísticas baseadas em normas como FEBRABAN para boletos e INSS e CLT para contracheques, um classificador estatístico e uma camada de interpretação por modelo de linguagem. A saída é um parecer de risco com pontuação de 0 a 100, classe (baixo, atenção ou alto), evidências por regra, justificativa em texto e campos extraídos do documento.",
          },
          {
            type: "subheading",
            text: "O que o serviço não faz",
          },
          {
            type: "list",
            items: [
              "Não é perícia técnica nem laudo pericial.",
              "Não substitui a conferência humana do documento.",
              "Não constitui orientação jurídica, contábil ou financeira.",
              "Não decide pagamento, aprovação de crédito ou qualquer ato negocial.",
              "Não garante que o documento seja autêntico ou fraudulento.",
              "Pode produzir falsos positivos e falsos negativos.",
            ],
          },
          {
            type: "note",
            text: "Use o resultado como um sinal adicional de risco. A decisão final é sempre sua ou de quem analisa o documento.",
          },
        ],
      },
      {
        id: "cadastro-e-conta",
        title: "Cadastro e conta",
        blocks: [
          {
            type: "paragraph",
            text: "O acesso pode ser feito com login Google por OpenID Connect ou com e-mail e senha. No acesso por senha, guardamos apenas o hash Argon2id da senha, nunca a senha em texto. Do perfil Google armazenamos o nome, o e-mail verificado e o identificador da conta Google. A foto do perfil não é armazenada.",
          },
          {
            type: "list",
            items: [
              "Você declara ter 18 anos ou mais e que as informações da conta são verdadeiras.",
              "Você é responsável por manter o acesso à sua conta Google e à sua senha seguros.",
              "A senha deve ter entre 10 e 128 caracteres, não pode estar entre as mais usadas e não pode conter seu nome nem seu e-mail.",
              "O cadastro por e-mail e senha só é ativado depois da confirmação do e-mail.",
              "A sessão usa cookies HttpOnly e tokens de curta duração.",
              "O uso é pessoal e intransferível. Cada e-mail corresponde a uma conta no SentinelPay.",
            ],
          },
          {
            type: "paragraph",
            text: "Em caso de uso indevido, o acesso pode ser suspenso conforme a seção 10.",
          },
        ],
      },
      {
        id: "uso-permitido-e-proibido",
        title: "Uso permitido e proibido",
        blocks: [
          {
            type: "subheading",
            text: "É permitido",
          },
          {
            type: "list",
            items: [
              "Enviar documentos que você tem direito de tratar.",
              "Consultar análises, dossiês e vencimentos gerados a partir dos seus envios.",
              "Configurar notificações e lembretes de vencimento.",
              "Usar a plataforma para prevenção e conferência de risco.",
            ],
          },
          {
            type: "subheading",
            text: "É proibido",
          },
          {
            type: "list",
            items: [
              "Enviar documentos sem base legal ou autorização.",
              "Usar o serviço para criar, alterar ou aperfeiçoar documentos fraudulentos.",
              "Tentar burlar limites de uso, autenticação ou limitação de taxa.",
              "Realizar engenharia reversa, raspagem ou extração massiva de dados.",
              "Enviar arquivos maliciosos ou tentar comprometer a segurança da plataforma.",
              "Usar o resultado como única base para decisão que afete direitos de terceiros, sem revisão humana.",
            ],
          },
        ],
      },
      {
        id: "documentos-de-terceiros",
        title: "Documentos de terceiros",
        blocks: [
          {
            type: "paragraph",
            text: "Você pode enviar documentos de terceiros, como boletos emitidos contra outra pessoa ou contracheques de empregados, somente se tiver base legal e autorização para isso. Nesse caso, você atua como controlador desses dados e o SentinelPay atua como operador, tratando os dados apenas para gerar a análise contratada.",
          },
          {
            type: "paragraph",
            text: "Você responde pela licitude do envio e pelas informações prestadas aos titulares. O SentinelPay não verifica a origem de cada documento enviado.",
          },
        ],
      },
      {
        id: "limites-de-arquivo-e-uso",
        title: "Limites de arquivo e de uso",
        blocks: [
          {
            type: "list",
            items: [
              "Formatos aceitos: PDF, PNG e JPG, com as extensões .pdf, .png, .jpg e .jpeg.",
              "Tamanho máximo: 25 MB por arquivo.",
              "PDFs: até 50 páginas. A leitura por OCR processa até 20 páginas por análise.",
              "PDFs protegidos por senha ou criptografados são recusados.",
              "Análises simultâneas: até 2 por usuário.",
              "As requisições passam por limitação de taxa por IP e por usuário. Ao exceder o limite, a API responde com o código 429 e informa o tempo de espera.",
            ],
          },
          {
            type: "note",
            text: "Os limites podem ser ajustados por configuração. O limite vigente aparece na tela de envio.",
          },
        ],
      },
      {
        id: "propriedade-intelectual",
        title: "Propriedade intelectual",
        blocks: [
          {
            type: "paragraph",
            text: "A plataforma, a marca, o código, as regras, os textos e os modelos pertencem ao controlador do SentinelPay ou a seus licenciantes. Concedemos uma licença limitada, revogável, não exclusiva e intransferível para usar o serviço conforme estes Termos.",
          },
          {
            type: "paragraph",
            text: "Os documentos enviados continuam sendo seus. Você nos concede licença limitada para armazenar, processar e gerar a análise e o dossiê, exclusivamente para prestar o serviço.",
          },
        ],
      },
      {
        id: "disponibilidade-e-mudancas",
        title: "Disponibilidade e mudanças no serviço",
        blocks: [
          {
            type: "paragraph",
            text: "Buscamos manter o serviço disponível, mas ele pode ficar indisponível por manutenção, falhas, dependências de terceiros ou eventos fora do nosso controle. Não há garantia de funcionamento ininterrupto.",
          },
          {
            type: "paragraph",
            text: "A análise depende de fila de processamento e de modelos de inteligência artificial. Podemos alterar etapas, versões de regras, modelos e limites, registrando a versão usada no dossiê quando disponível.",
          },
        ],
      },
      {
        id: "limitacao-de-responsabilidade",
        title: "Limitação de responsabilidade",
        blocks: [
          {
            type: "paragraph",
            text: "Na máxima extensão permitida pela lei brasileira, não respondemos por danos indiretos, lucros cessantes ou decisões tomadas exclusivamente com base no parecer de risco. Nada nestes Termos limita direitos do consumidor previstos no Código de Defesa do Consumidor nem afasta a responsabilidade por dolo ou culpa grave.",
          },
          {
            type: "paragraph",
            text: "Você é responsável pelos documentos que envia e pelo uso que faz do resultado.",
          },
        ],
      },
      {
        id: "suspensao-e-encerramento",
        title: "Suspensão e encerramento da conta",
        blocks: [
          {
            type: "list",
            items: [
              "Você pode encerrar o uso a qualquer momento e solicitar a exclusão da conta pelo canal de privacidade.",
              "Podemos suspender ou encerrar o acesso em caso de violação destes Termos, risco à segurança, determinação legal ou uso abusivo.",
              "A exclusão automática de conta, de documentos e de análises ainda não está disponível na API. A solicitação é registrada e tratada pelo canal de privacidade, conforme a Política de privacidade.",
            ],
          },
          {
            type: "links",
            items: [
              { label: "Direitos do titular na conta", href: "/account" },
              { label: "Política de privacidade", href: "/privacidade" },
            ],
          },
        ],
      },
      {
        id: "alteracoes-dos-termos",
        title: "Alterações dos Termos",
        blocks: [
          {
            type: "paragraph",
            text: "Podemos atualizar estes Termos. A versão vigente, a data e o número aparecem no topo desta página. Mudanças relevantes são comunicadas por e-mail ou por aviso no aplicativo com antecedência razoável.",
          },
          {
            type: "paragraph",
            text: "O uso contínuo após a data de vigência representa aceite da nova versão, quando permitido pela lei. Se você não concordar, pode encerrar a conta.",
          },
        ],
      },
      {
        id: "lei-aplicavel-e-foro",
        title: "Lei aplicável e foro",
        blocks: [
          {
            type: "paragraph",
            text: "Estes Termos são regidos pelas leis brasileiras, incluindo a Lei Geral de Proteção de Dados e o Código de Defesa do Consumidor quando aplicável. Fica eleito o foro do domicílio do usuário consumidor, quando assim exigir a lei.",
          },
          {
            type: "links",
            items: [
              { label: "Canal de privacidade", href: "privacy-contact" },
              { label: "Suporte", href: "/suporte" },
              { label: "Política de privacidade", href: "/privacidade" },
            ],
          },
        ],
      },
    ],
  },
  privacy: {
    title: "Política de privacidade",
    subtitle:
      "Como o SentinelPay trata dados pessoais na análise de boletos, contracheques e recibos, conforme a LGPD.",
    sections: [
      {
        id: "quem-somos",
        title: "Quem somos e quem é o controlador",
        blocks: [
          {
            type: "paragraph",
            text: "O SentinelPay é uma plataforma de análise de risco para documentos financeiros brasileiros. O controlador é a pessoa física ou jurídica responsável pelas decisões sobre o tratamento de dados pessoais descrito nesta política.",
          },
          { type: "identity" },
          {
            type: "paragraph",
            text: "O Encarregado pelo tratamento de dados pessoais (DPO) é o canal de comunicação entre você, o controlador e a Autoridade Nacional de Proteção de Dados, conforme o art. 41 da LGPD.",
          },
          {
            type: "note",
            text: "Os campos de identificação aparecem quando configurados. Se algum dado não estiver visível, solicite a identificação do controlador e o contato do Encarregado pelo canal de privacidade.",
          },
          {
            type: "links",
            items: [
              { label: "Direitos do titular na conta", href: "/account" },
              { label: "Canal de privacidade", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "dados-tratados",
        title: "Quais dados tratamos",
        blocks: [
          {
            type: "paragraph",
            text: "Tratamos apenas os dados necessários para autenticar, analisar documentos, montar o dossiê, gerar vencimentos e manter a segurança do serviço.",
          },
          {
            type: "table",
            table: {
              caption: "Categorias de dados pessoais tratados",
              headers: ["Categoria", "Dados"],
              rows: [
                [
                  "Dados de conta (Google)",
                  "Nome, e-mail verificado, identificador da conta Google, papel na plataforma, idioma preferido e fuso horário. A foto do perfil não é armazenada.",
                ],
                [
                  "Dados de conta (e-mail e senha)",
                  "Nome, e-mail normalizado, hash Argon2id da senha (nunca a senha em texto), data da última troca de senha, contador de falhas de login e bloqueio temporário.",
                ],
                [
                  "Tokens de verificação e redefinição",
                  "Hash SHA-256 do token de uso único, finalidade, validade, data de uso, IP e user agent do pedido. O token em texto existe apenas no link enviado por e-mail.",
                ],
                [
                  "Consentimentos",
                  "Documento aceito, versão vigente, data e hora do aceite, origem, IP e user agent, como prova de consentimento.",
                ],
                [
                  "Eventos de segurança",
                  "Cadastro, login, falha de login, bloqueio, verificação de e-mail, pedido de redefinição, redefinição concluída, troca de senha e logout, com data, IP e user agent. Nunca incluem senha, hash ou token.",
                ],
                [
                  "Dados dos documentos enviados",
                  "Arquivo PDF, PNG ou JPG, nome do arquivo sanitizado, tipo, tamanho, hash SHA-256 e data do envio. O conteúdo pode incluir nome, CPF, CNPJ, endereço, dados bancários, salário e descontos.",
                ],
                [
                  "Dados gerados pela análise",
                  "Pontuação de risco, classe, evidências por regra, justificativa, inconsistências, campos extraídos, versões de regra e de modelo, sinalizadores de degradação e datas. CPF e CNPJ aparecem mascarados no dossiê.",
                ],
                [
                  "Dados de uso e técnicos",
                  "Logs de aplicação com data e hora, rota, status e identificador de requisição, endereço IP usado na limitação de taxa, métricas agregadas e eventos de erro do front-end quando o monitoramento está configurado.",
                ],
                [
                  "Dados de preferências",
                  "Tema, idioma, formato de data, canais de notificação, horário e antecedência dos lembretes. Destinos de SMS e WhatsApp ficam cifrados.",
                ],
              ],
            },
          },
        ],
      },
      {
        id: "finalidades",
        title: "Para que usamos cada dado",
        blocks: [
          {
            type: "table",
            table: {
              caption: "Finalidades do tratamento",
              headers: ["Finalidade", "Dados envolvidos"],
              rows: [
                ["Autenticar e manter a sessão", "Dados de conta e cookies de sessão."],
                [
                  "Analisar o documento e gerar o dossiê",
                  "Documento enviado, dados extraídos, evidências, pontuação e justificativa.",
                ],
                [
                  "Criar vencimentos e enviar lembretes",
                  "Valor, data de vencimento, descrição, canais e destinos de notificação.",
                ],
                [
                  "Prevenir fraude, abuso e incidentes de segurança",
                  "Logs, endereço IP, identificador de usuário, métricas e eventos de erro.",
                ],
                [
                  "Monitorar e melhorar o serviço",
                  "Métricas agregadas, traces mascarados e erros sem dados sensíveis.",
                ],
                [
                  "Cumprir obrigações legais e exercer direitos",
                  "Dados necessários para atender ordens legais, responder a titulares e registrar incidentes.",
                ],
                [
                  "Prestar suporte",
                  "Dados de conta e informações fornecidas por você no atendimento.",
                ],
              ],
            },
          },
        ],
      },
      {
        id: "bases-legais",
        title: "Bases legais",
        blocks: [
          {
            type: "paragraph",
            text: "Cada finalidade tem uma base legal prevista no art. 7 da LGPD. Quando a base for o consentimento, você pode revogá-lo a qualquer momento pelos canais indicados nesta política.",
          },
          {
            type: "table",
            table: {
              caption: "Bases legais por finalidade",
              headers: ["Finalidade", "Base legal", "Observação"],
              rows: [
                [
                  "Autenticação e execução do serviço",
                  "Execução de contrato (art. 7, V)",
                  "Necessário para usar a plataforma.",
                ],
                [
                  "Análise de documentos e dossiê",
                  "Execução de contrato (art. 7, V)",
                  "O tratamento é o próprio serviço contratado.",
                ],
                [
                  "Vencimentos e lembretes no aplicativo e por e-mail",
                  "Execução de contrato (art. 7, V)",
                  "Usa o e-mail da conta.",
                ],
                [
                  "SMS e WhatsApp",
                  "Consentimento (art. 7, I)",
                  "Registrado com data e hora no momento da ativação.",
                ],
                [
                  "Segurança, prevenção a fraude e abuso",
                  "Legítimo interesse (art. 7, IX)",
                  "Com medidas para limitar o impacto sobre o titular.",
                ],
                [
                  "Logs, métricas e monitoramento",
                  "Legítimo interesse (art. 7, IX)",
                  "Dados técnicos e mascaramento de dados pessoais.",
                ],
                [
                  "Cumprimento de obrigação legal ou regulatória",
                  "Obrigação legal ou regulatória (art. 7, II)",
                  "Inclui atendimento à ANPD e a autoridades competentes.",
                ],
                [
                  "Exercício regular de direitos",
                  "Exercício regular de direitos (art. 7, VI)",
                  "Inclui defesa em processos administrativos e judiciais.",
                ],
                [
                  "Melhoria do serviço",
                  "Legítimo interesse (art. 7, IX)",
                  "Preferência por dados agregados ou anonimizados.",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "Não usamos os seus documentos para treinar modelos. O classificador estatístico é treinado com dados sintéticos, sem documentos reais.",
          },
        ],
      },
      {
        id: "papeis-controlador-operador",
        title: "Documentos de terceiros e papéis de tratamento",
        blocks: [
          {
            type: "paragraph",
            text: "Nos dados da sua conta e nos documentos que você envia para analisar em nome próprio, o SentinelPay atua como controlador, porque decide como o tratamento ocorre para prestar o serviço.",
          },
          {
            type: "paragraph",
            text: "Quando você envia documentos de terceiros, como boletos de clientes ou contracheques de empregados, você declara ter base legal e autorização para esse envio. Nesse caso, você atua como controlador desses dados e o SentinelPay atua como operador, seguindo as suas instruções para gerar a análise contratada.",
          },
          {
            type: "paragraph",
            text: "Você responde pela licitude do envio e pelas informações prestadas aos titulares desses documentos.",
          },
        ],
      },
      {
        id: "inteligencia-artificial",
        title: "Uso de inteligência artificial",
        blocks: [
          {
            type: "paragraph",
            text: "A análise é apoiada por regras determinísticas, por um classificador estatístico e por um modelo de linguagem. O resultado é um parecer de risco. Não é uma decisão definitiva, não substitui a conferência humana e não constitui orientação jurídica, contábil ou financeira.",
          },
          {
            type: "paragraph",
            text: "Por padrão, o modelo de linguagem é executado na infraestrutura do controlador, por meio de um endpoint compatível com a API da OpenAI. A configuração pode apontar para um provedor externo. Quando isso ocorre, o trecho do documento é mascarado antes do envio.",
          },
          {
            type: "list",
            items: [
              "O modelo recebe o tipo do documento, a pontuação, a classe, os códigos das evidências, trechos da base normativa, o idioma, os sinalizadores de degradação e um trecho mascarado do documento, limitado a 6.000 caracteres.",
              "O mascaramento remove CPF, CNPJ, nomes, valores, e-mail, telefone, endereço, chaves Pix e sequências longas de dígitos.",
              "Não usamos os seus documentos para treinar modelos. Os traces de observabilidade também não são usados para treinamento.",
              "Guardrails verificam tentativas de injeção de prompt, conteúdo da saída e limites de tamanho.",
            ],
          },
          {
            type: "paragraph",
            text: "Você pode solicitar a revisão de uma decisão tomada com base em tratamento automatizado, conforme o art. 20 da LGPD, pelo canal de privacidade.",
          },
        ],
      },
      {
        id: "compartilhamento",
        title: "Compartilhamento e operadores",
        blocks: [
          {
            type: "paragraph",
            text: "Não vendemos dados pessoais. Compartilhamos dados apenas com operadores necessários ao funcionamento do serviço e com autoridades quando houver determinação legal válida.",
          },
          {
            type: "table",
            table: {
              caption: "Operadores utilizados",
              headers: ["Operador", "Finalidade", "Dados envolvidos", "Região ou local"],
              rows: [
                [
                  "Google",
                  "Autenticação por OpenID Connect",
                  "Nome, e-mail verificado e identificador da conta Google",
                  "Infraestrutura global do Google",
                ],
                [
                  "Provedor de e-mail transacional",
                  "Envio dos e-mails de verificação, redefinição, aviso de senha alterada e aviso de e-mail já cadastrado",
                  "Endereço de e-mail do destinatário e conteúdo da mensagem. Definido por configuração de SMTP do controlador.",
                  "A definir conforme o provedor contratado",
                ],
                [
                  "Railway",
                  "Hospedagem da API, do PostgreSQL e do Redis",
                  "Dados de conta, documentos, análises, vencimentos, notificações e logs",
                  "Região definida na configuração do provedor",
                ],
                [
                  "Amazon S3",
                  "Armazenamento dos arquivos enviados e dos relatórios de análise, com cifra AES-256 em repouso",
                  "Arquivos enviados e relatórios JSON",
                  "Região configurada no ambiente, atualmente us-east-2",
                ],
                [
                  "Vercel",
                  "Hospedagem da aplicação web",
                  "Dados de navegação e cookies de sessão no front-end",
                  "Rede global do provedor",
                ],
                [
                  "Langfuse",
                  "Observabilidade das chamadas de inteligência artificial, quando habilitada",
                  "Traces mascarados, com identificadores em hash e sem dados pessoais legíveis",
                  "Ambiente configurado do provedor",
                ],
                [
                  "Servidor SMTP",
                  "Envio de avisos por e-mail",
                  "E-mail da conta e conteúdo do aviso",
                  "Servidor configurado pelo operador",
                ],
                [
                  "Sentry",
                  "Monitoramento de erros do front-end, quando configurado",
                  "Eventos de erro sem dados pessoais, cookies ou cabeçalhos",
                  "Ambiente configurado do provedor",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "SMS e WhatsApp: as preferências e os consentimentos são registrados, mas não há provedor externo de SMS ou WhatsApp integrado nesta configuração. Os avisos ficam disponíveis no aplicativo e por e-mail.",
          },
          {
            type: "paragraph",
            text: "Podemos compartilhar dados com autoridades públicas mediante ordem judicial, requisição administrativa válida ou obrigação legal.",
          },
        ],
      },
      {
        id: "transferencia-internacional",
        title: "Transferência internacional",
        blocks: [
          {
            type: "paragraph",
            text: "Alguns operadores listados na seção anterior processam dados em servidores fora do Brasil, conforme a coluna de região. A transferência ocorre para viabilizar a autenticação, o armazenamento, a hospedagem e a observabilidade do serviço.",
          },
          {
            type: "paragraph",
            text: "Quando a transferência internacional ocorre, o controlador se apoia nas salvaguardas contratuais do provedor. Você pode solicitar informações sobre a transferência e as salvaguardas aplicáveis pelo canal de privacidade, conforme o art. 18 da LGPD.",
          },
        ],
      },
      {
        id: "armazenamento-e-retencao",
        title: "Armazenamento e retenção",
        blocks: [
          {
            type: "paragraph",
            text: "Os dados ficam em banco PostgreSQL, em armazenamento de objetos compatível com S3 para arquivos e relatórios e em Redis para limitação de taxa, estado de login e revogação de tokens. Logs ficam na infraestrutura de hospedagem. Traces de inteligência artificial, quando habilitados, ficam no Langfuse.",
          },
          {
            type: "paragraph",
            text: "Mantemos os dados enquanto a conta existir e enquanto forem necessários às finalidades desta política. Não há prazo automático de expurgo configurado para documentos e análises. Tokens de acesso expiram em 15 minutos, tokens de atualização em 7 dias, estados de login em 10 minutos e chaves de limitação de taxa em segundos.",
          },
          {
            type: "paragraph",
            text: "Tokens de verificação de e-mail expiram em 24 horas e tokens de redefinição de senha em 30 minutos, sempre de uso único. Pedidos de redefinição substituem os pedidos anteriores.",
          },
          {
            type: "paragraph",
            text: "A exclusão automática de conta, de documentos e de análises ainda não está disponível na API. O pedido de exclusão é registrado pelo canal de privacidade e tratado pelo controlador. A exclusão remove o hash da senha, os tokens de verificação e de redefinição e os registros de consentimento. Os eventos de segurança associados ao usuário perdem o vínculo direto com a conta, para preservar a guarda legal dos registros de segurança. O cancelamento de uma análise em andamento remove o relatório parcial gerado até aquele momento.",
          },
          {
            type: "links",
            items: [
              { label: "Solicitar exclusão na conta", href: "/account" },
              { label: "Canal de privacidade", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "seguranca",
        title: "Segurança",
        blocks: [
          {
            type: "paragraph",
            text: "Adotamos medidas técnicas e administrativas para proteger os dados pessoais, entre elas:",
          },
          {
            type: "list",
            items: [
              "HTTPS com HSTS em produção e cookies HttpOnly, SameSite=Lax e Secure.",
              "Política de segurança de conteúdo e cabeçalhos de proteção no front-end.",
              "Senhas guardadas apenas como hash Argon2id, com parâmetros configuráveis e rehash no login.",
              "Tokens de verificação e de redefinição de senha de uso único, guardados apenas como hash SHA-256, com expiração curta.",
              "Tokens de acesso de curta duração, rotação de tokens de atualização e detecção de reuso.",
              "Proteção contra CSRF nas rotas autenticadas.",
              "Controle de acesso por dono em cada consulta de documento, análise e vencimento.",
              "Limitação de taxa por IP e por usuário com resposta 429 e tempo de espera.",
              "Validação do tipo real do arquivo, do tamanho e do número de páginas, com recusa de PDF criptografado.",
              "Cifra AES-256 em repouso no armazenamento de objetos e cifra AES-GCM nos destinos de notificação.",
              "Mascaramento de dados pessoais nos logs e antes do envio de traces de inteligência artificial.",
              "Guardrails contra injeção de prompt e verificação da saída do modelo.",
            ],
          },
          {
            type: "paragraph",
            text: "Nenhum sistema é totalmente imune a incidentes. Não há certificação de segurança declarada nesta política.",
          },
          {
            type: "paragraph",
            text: "Se ocorrer um incidente de segurança relevante, comunicamos a Autoridade Nacional de Proteção de Dados e os titulares afetados quando a lei exigir, com as informações disponíveis e as medidas adotadas, conforme o art. 48 da LGPD.",
          },
        ],
      },
      {
        id: "direitos-do-titular",
        title: "Direitos do titular",
        blocks: [
          {
            type: "paragraph",
            text: "Você pode exercer os direitos previstos no art. 18 da LGPD. A tabela abaixo indica o direito e o caminho para exercê-lo.",
          },
          {
            type: "table",
            table: {
              caption: "Direitos do titular e como exercer",
              headers: ["Direito", "Como exercer"],
              rows: [
                [
                  "Confirmação de tratamento e acesso",
                  "Perfil e análises na conta, quando disponíveis, e canal de privacidade.",
                ],
                [
                  "Correção",
                  "Dados de conta podem ser corrigidos no perfil ou pelo canal de privacidade. Contas Google também podem ser corrigidas na própria conta Google.",
                ],
                [
                  "Anonimização, bloqueio ou eliminação",
                  "Canal de privacidade, com análise de viabilidade técnica e legal.",
                ],
                [
                  "Portabilidade",
                  "Canal de privacidade. A exportação automática ainda não está disponível no aplicativo.",
                ],
                [
                  "Informação sobre compartilhamento",
                  "Seção de compartilhamento desta política e canal de privacidade.",
                ],
                [
                  "Informação sobre a possibilidade de não consentir",
                  "Seções de finalidades e bases legais e canal de privacidade.",
                ],
                [
                  "Revogação do consentimento",
                  "Preferências de notificação na conta para SMS e WhatsApp, e canal de privacidade para os demais casos.",
                ],
                ["Oposição", "Canal de privacidade."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "Respondemos aos pedidos de confirmação de tratamento e de acesso em até 15 dias, contados do recebimento, conforme o art. 19 da LGPD. Os demais pedidos são respondidos no prazo legal aplicável. Podemos solicitar informações para confirmar a sua identidade antes de atender.",
          },
          {
            type: "links",
            items: [
              { label: "Abrir a conta", href: "/account" },
              { label: "Canal de privacidade", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "cookies",
        title: "Cookies e armazenamento local",
        blocks: [
          {
            type: "paragraph",
            text: "Usamos apenas cookies necessários ao serviço e às suas preferências. Não usamos cookies de marketing, de análise de audiência ou rastreadores de terceiros. Não usamos armazenamento local do navegador para dados de sessão ou documentos.",
          },
          {
            type: "table",
            table: {
              caption: "Cookies utilizados",
              headers: ["Cookie", "Finalidade", "Duração"],
              rows: [
                [
                  "sp_session, sp_session_exp, sp_refresh, sp_csrf",
                  "Sessão autenticada e proteção contra CSRF. HttpOnly, SameSite=Lax e Secure.",
                  "Até 7 dias.",
                ],
                ["sp_oidc", "Conclusão do login Google.", "10 minutos."],
                [
                  "refresh_token, csrf_token",
                  "Sessão no backend e proteção contra CSRF.",
                  "Até 7 dias.",
                ],
                ["theme", "Tema escolhido: sistema, claro ou escuro.", "1 ano."],
                ["locale", "Idioma escolhido: português, espanhol ou inglês.", "1 ano."],
                ["date_format", "Formato de data escolhido.", "1 ano."],
                ["sp_sidebar", "Estado da barra lateral.", "1 ano."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "Você pode bloquear ou apagar cookies nas configurações do navegador. Os cookies essenciais são necessários para autenticar e manter a sessão. O monitoramento de erros do front-end, quando configurado, usa o Sentry e envia apenas eventos tratados, sem cookies, cabeçalhos ou dados pessoais.",
          },
        ],
      },
      {
        id: "criancas-e-adolescentes",
        title: "Crianças e adolescentes",
        blocks: [
          {
            type: "paragraph",
            text: "O serviço é destinado a maiores de 18 anos. Não coletamos intencionalmente dados de crianças ou adolescentes. Se identificarmos uma conta nessas condições, o acesso pode ser encerrado e os dados tratados conforme a lei.",
          },
        ],
      },
      {
        id: "alteracoes-da-politica",
        title: "Alterações desta política",
        blocks: [
          {
            type: "paragraph",
            text: "Podemos atualizar esta política. A versão vigente, a data e o número aparecem no topo desta página. Mudanças relevantes são comunicadas por e-mail ou por aviso no aplicativo com antecedência razoável.",
          },
          {
            type: "paragraph",
            text: "Você pode solicitar o histórico de versões pelo canal de privacidade.",
          },
        ],
      },
      {
        id: "contato-e-anpd",
        title: "Contato e canal da ANPD",
        blocks: [
          {
            type: "paragraph",
            text: "Dúvidas, pedidos de titulares e solicitações sobre esta política podem ser enviados pelo canal de privacidade. Quando configurado, o contato do Encarregado aparece na seção 1.",
          },
          {
            type: "paragraph",
            text: "Você também pode apresentar reclamação à Autoridade Nacional de Proteção de Dados (ANPD) pelos canais oficiais em gov.br/anpd.",
          },
          {
            type: "links",
            items: [
              { label: "Canal de privacidade", href: "privacy-contact" },
              { label: "Abrir a conta", href: "/account" },
              { label: "Suporte", href: "/suporte" },
            ],
          },
        ],
      },
    ],
  },
};
