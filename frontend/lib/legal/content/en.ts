import type { LegalContent } from "./types";

export const en: LegalContent = {
  terms: {
    title: "Terms of use",
    subtitle:
      "Conditions for using SentinelPay to analyze Brazilian payment slips, payslips and receipts.",
    notice:
      "Notice: this is an informational translation. In case of divergence, the Portuguese version prevails.",
    sections: [
      {
        id: "aceite-e-definicoes",
        title: "Acceptance and definitions",
        blocks: [
          {
            type: "paragraph",
            text: "These Terms govern the use of SentinelPay. By checking the acceptance box on the login screen and completing registration or authentication, with Google or with e-mail and password, you agree to these Terms and to the Privacy Policy.",
          },
          {
            type: "paragraph",
            text: "To make reading easier, the terms below have the following meanings:",
          },
          {
            type: "list",
            items: [
              "SentinelPay: the platform, including the website, web application, API and analysis pipeline.",
              "User: an individual aged 18 or older, authenticated with a Google account or with e-mail and password.",
              "Document: a PDF, PNG or JPG file uploaded by the user, such as a payment slip, payslip or receipt.",
              "Analysis: processing of the document that generates a risk score from 0 to 100, risk band, evidence, justification and extracted fields.",
              "Dossier: the set displayed in the platform with the analysis result, evidence and extracted fields.",
              "Account: a record created on the first Google sign-in or by the e-mail and password sign-up, linked to a verified e-mail address.",
            ],
          },
          {
            type: "note",
            text: "If you do not agree to these Terms, do not use the service.",
          },
        ],
      },
      {
        id: "o-que-o-servico-faz",
        title: "What the service does and does not do",
        blocks: [
          {
            type: "paragraph",
            text: "SentinelPay analyzes Brazilian payment slips, payslips and receipts. The result combines deterministic rules based on standards such as FEBRABAN for payment slips and INSS and CLT for payslips, a statistical classifier and an interpretation layer powered by a language model. The output is a risk opinion with a score from 0 to 100, a band (low, attention or high), evidence per rule, a written justification and fields extracted from the document.",
          },
          {
            type: "subheading",
            text: "What the service does not do",
          },
          {
            type: "list",
            items: [
              "It is not a technical examination or an expert report.",
              "It does not replace human review of the document.",
              "It does not constitute legal, accounting or financial advice.",
              "It does not decide payments, credit approval or any business act.",
              "It does not guarantee that the document is authentic or fraudulent.",
              "It may produce false positives and false negatives.",
            ],
          },
          {
            type: "note",
            text: "Use the result as an additional risk signal. The final decision is always yours or that of whoever reviews the document.",
          },
        ],
      },
      {
        id: "cadastro-e-conta",
        title: "Registration and account",
        blocks: [
          {
            type: "paragraph",
            text: "Access can be done with Google sign-in through OpenID Connect or with e-mail and password. With a password, we store only the Argon2id hash, never the plain password. From the Google profile we store the name, verified email and Google account identifier. The profile picture is not stored.",
          },
          {
            type: "list",
            items: [
              "You declare that you are 18 or older and that the account information is accurate.",
              "You are responsible for keeping access to your Google account and to your password secure.",
              "The password must have between 10 and 128 characters, cannot be among the most used ones and cannot contain your name or e-mail.",
              "Sign-up with e-mail and password only becomes active after the e-mail confirmation.",
              "The session uses HttpOnly cookies and short-lived tokens.",
              "Use is personal and non-transferable. Each e-mail corresponds to one SentinelPay account.",
            ],
          },
          {
            type: "paragraph",
            text: "In case of misuse, access may be suspended as described in section 10.",
          },
        ],
      },
      {
        id: "uso-permitido-e-proibido",
        title: "Permitted and prohibited use",
        blocks: [
          {
            type: "subheading",
            text: "Permitted",
          },
          {
            type: "list",
            items: [
              "Uploading documents you have the right to process.",
              "Viewing analyses, dossiers and due dates generated from your uploads.",
              "Configuring notifications and due date reminders.",
              "Using the platform for risk prevention and verification.",
            ],
          },
          {
            type: "subheading",
            text: "Prohibited",
          },
          {
            type: "list",
            items: [
              "Uploading documents without a legal basis or authorization.",
              "Using the service to create, alter or improve fraudulent documents.",
              "Attempting to bypass usage limits, authentication or rate limiting.",
              "Reverse engineering, scraping or mass data extraction.",
              "Uploading malicious files or attempting to compromise platform security.",
              "Using the result as the sole basis for a decision affecting third-party rights, without human review.",
            ],
          },
        ],
      },
      {
        id: "documentos-de-terceiros",
        title: "Third-party documents",
        blocks: [
          {
            type: "paragraph",
            text: "You may upload third-party documents, such as payment slips issued to another person or employee payslips, only if you have a legal basis and authorization to do so. In that case, you act as the controller of that data and SentinelPay acts as the operator, processing the data solely to generate the contracted analysis.",
          },
          {
            type: "paragraph",
            text: "You are responsible for the lawfulness of the upload and for the information provided to data subjects. SentinelPay does not verify the origin of each uploaded document.",
          },
        ],
      },
      {
        id: "limites-de-arquivo-e-uso",
        title: "File and usage limits",
        blocks: [
          {
            type: "list",
            items: [
              "Accepted formats: PDF, PNG and JPG, with the .pdf, .png, .jpg and .jpeg extensions.",
              "Maximum size: 25 MB per file.",
              "PDF files: up to 50 pages. OCR reads up to 20 pages per analysis.",
              "Password-protected or encrypted PDF files are rejected.",
              "Concurrent analyses: up to 2 per user.",
              "Requests are subject to rate limiting by IP and by user. When the limit is exceeded, the API responds with status 429 and informs the wait time.",
            ],
          },
          {
            type: "note",
            text: "Limits may be adjusted through configuration. The current limit is shown on the upload screen.",
          },
        ],
      },
      {
        id: "propriedade-intelectual",
        title: "Intellectual property",
        blocks: [
          {
            type: "paragraph",
            text: "The platform, brand, code, rules, texts and models belong to the SentinelPay controller or its licensors. We grant you a limited, revocable, non-exclusive and non-transferable license to use the service under these Terms.",
          },
          {
            type: "paragraph",
            text: "Uploaded documents remain yours. You grant us a limited license to store, process and generate the analysis and dossier, exclusively to provide the service.",
          },
        ],
      },
      {
        id: "disponibilidade-e-mudancas",
        title: "Availability and service changes",
        blocks: [
          {
            type: "paragraph",
            text: "We aim to keep the service available, but it may be unavailable due to maintenance, failures, third-party dependencies or events beyond our control. We do not guarantee uninterrupted operation.",
          },
          {
            type: "paragraph",
            text: "Analysis depends on a processing queue and artificial intelligence models. We may change stages, rule versions, models and limits, recording the version used in the dossier when available.",
          },
        ],
      },
      {
        id: "limitacao-de-responsabilidade",
        title: "Limitation of liability",
        blocks: [
          {
            type: "paragraph",
            text: "To the maximum extent permitted by Brazilian law, we are not liable for indirect damages, lost profits or decisions made exclusively based on the risk opinion. Nothing in these Terms limits consumer rights under the Brazilian Consumer Protection Code or excludes liability for intent or gross negligence.",
          },
          {
            type: "paragraph",
            text: "You are responsible for the documents you upload and for how you use the result.",
          },
        ],
      },
      {
        id: "suspensao-e-encerramento",
        title: "Account suspension and termination",
        blocks: [
          {
            type: "list",
            items: [
              "You may stop using the service at any time and request account deletion through the privacy channel.",
              "We may suspend or terminate access in case of violation of these Terms, security risk, legal determination or abusive use.",
              "Automatic deletion of accounts, documents and analyses is not yet available in the API. Requests are recorded and handled through the privacy channel, in accordance with the Privacy Policy.",
            ],
          },
          {
            type: "links",
            items: [
              { label: "Data subject rights in your account", href: "/account" },
              { label: "Privacy Policy", href: "/privacidade" },
            ],
          },
        ],
      },
      {
        id: "alteracoes-dos-termos",
        title: "Changes to the Terms",
        blocks: [
          {
            type: "paragraph",
            text: "We may update these Terms. The current version, date and number appear at the top of this page. Material changes are communicated by email or in-app notice with reasonable advance notice.",
          },
          {
            type: "paragraph",
            text: "Continued use after the effective date represents acceptance of the new version, where permitted by law. If you do not agree, you may close your account.",
          },
        ],
      },
      {
        id: "lei-aplicavel-e-foro",
        title: "Applicable law and jurisdiction",
        blocks: [
          {
            type: "paragraph",
            text: "These Terms are governed by Brazilian law, including the General Data Protection Law and the Consumer Protection Code where applicable. The forum of the consumer's domicile is elected where required by law.",
          },
          {
            type: "links",
            items: [
              { label: "Privacy channel", href: "privacy-contact" },
              { label: "Support", href: "/suporte" },
              { label: "Privacy Policy", href: "/privacidade" },
            ],
          },
        ],
      },
    ],
  },
  privacy: {
    title: "Privacy Policy",
    subtitle:
      "How SentinelPay processes personal data when analyzing payment slips, payslips and receipts, in accordance with the LGPD.",
    notice:
      "Notice: this is an informational translation. In case of divergence, the Portuguese version prevails.",
    sections: [
      {
        id: "quem-somos",
        title: "Who we are and who the controller is",
        blocks: [
          {
            type: "paragraph",
            text: "SentinelPay is a risk analysis platform for Brazilian financial documents. The controller is the individual or legal entity responsible for decisions regarding the processing of personal data described in this policy.",
          },
          { type: "identity" },
          {
            type: "paragraph",
            text: "The Data Protection Officer (DPO) is the communication channel between you, the controller and the Brazilian National Data Protection Authority, under article 41 of the LGPD.",
          },
          {
            type: "note",
            text: "Identification fields appear when configured. If any data is not visible, request the controller identification and the DPO contact through the privacy channel.",
          },
          {
            type: "links",
            items: [
              { label: "Data subject rights in your account", href: "/account" },
              { label: "Privacy channel", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "dados-tratados",
        title: "What data we process",
        blocks: [
          {
            type: "paragraph",
            text: "We process only the data necessary to authenticate, analyze documents, build the dossier, create due dates and keep the service secure.",
          },
          {
            type: "table",
            table: {
              caption: "Categories of personal data processed",
              headers: ["Category", "Data"],
              rows: [
                [
                  "Account data (Google)",
                  "Name, verified email, Google account identifier, platform role, preferred language and time zone. The profile picture is not stored.",
                ],
                [
                  "Account data (e-mail and password)",
                  "Name, normalized e-mail, Argon2id password hash (never the plain password), date of the last password change, failed login counter and temporary lock.",
                ],
                [
                  "Verification and reset tokens",
                  "SHA-256 hash of the single-use token, purpose, validity, use date, IP and user agent of the request. The plain token exists only in the link sent by e-mail.",
                ],
                [
                  "Consents",
                  "Accepted document, current version, acceptance date and time, origin, IP and user agent, as proof of consent.",
                ],
                [
                  "Security events",
                  "Sign-up, sign-in, failed sign-in, lock, e-mail verification, reset request, completed reset, password change and sign-out, with date, IP and user agent. They never include password, hash or token.",
                ],
                [
                  "Uploaded document data",
                  "PDF, PNG or JPG file, sanitized file name, type, size, SHA-256 hash and upload date. The content may include name, CPF, CNPJ, address, bank details, salary and deductions.",
                ],
                [
                  "Data generated by the analysis",
                  "Risk score, band, evidence per rule, justification, inconsistencies, extracted fields, rule and model versions, degradation flags and dates. CPF and CNPJ are masked in the dossier.",
                ],
                [
                  "Usage and technical data",
                  "Application logs with date and time, route, status and request identifier, IP address used for rate limiting, aggregated metrics and front-end error events when monitoring is configured.",
                ],
                [
                  "Preference data",
                  "Theme, language, date format, notification channels, reminder time and advance notice. SMS and WhatsApp destinations are encrypted.",
                ],
              ],
            },
          },
        ],
      },
      {
        id: "finalidades",
        title: "What we use each type of data for",
        blocks: [
          {
            type: "table",
            table: {
              caption: "Processing purposes",
              headers: ["Purpose", "Data involved"],
              rows: [
                ["Authenticate and keep the session", "Account data and session cookies."],
                [
                  "Analyze the document and build the dossier",
                  "Uploaded document, extracted data, evidence, score and justification.",
                ],
                [
                  "Create due dates and send reminders",
                  "Amount, due date, description, notification channels and destinations.",
                ],
                [
                  "Prevent fraud, abuse and security incidents",
                  "Logs, IP address, user identifier, metrics and error events.",
                ],
                [
                  "Monitor and improve the service",
                  "Aggregated metrics, masked traces and errors without sensitive data.",
                ],
                [
                  "Comply with legal obligations and exercise rights",
                  "Data necessary to respond to legal orders, data subject requests and incident records.",
                ],
                ["Provide support", "Account data and information provided by you during support."],
              ],
            },
          },
        ],
      },
      {
        id: "bases-legais",
        title: "Legal bases",
        blocks: [
          {
            type: "paragraph",
            text: "Each purpose has a legal basis under article 7 of the LGPD. When the basis is consent, you may revoke it at any time through the channels indicated in this policy.",
          },
          {
            type: "table",
            table: {
              caption: "Legal bases by purpose",
              headers: ["Purpose", "Legal basis", "Note"],
              rows: [
                [
                  "Authentication and service delivery",
                  "Performance of a contract (art. 7, V)",
                  "Necessary to use the platform.",
                ],
                [
                  "Document analysis and dossier",
                  "Performance of a contract (art. 7, V)",
                  "The processing is the contracted service itself.",
                ],
                [
                  "Due dates and reminders in the app and by email",
                  "Performance of a contract (art. 7, V)",
                  "Uses the account email.",
                ],
                [
                  "SMS and WhatsApp",
                  "Consent (art. 7, I)",
                  "Recorded with date and time when enabled.",
                ],
                [
                  "Security, fraud and abuse prevention",
                  "Legitimate interest (art. 7, IX)",
                  "With measures to limit the impact on the data subject.",
                ],
                [
                  "Logs, metrics and monitoring",
                  "Legitimate interest (art. 7, IX)",
                  "Technical data and masking of personal data.",
                ],
                [
                  "Compliance with legal or regulatory obligations",
                  "Legal or regulatory obligation (art. 7, II)",
                  "Includes responding to the ANPD and competent authorities.",
                ],
                [
                  "Regular exercise of rights",
                  "Regular exercise of rights (art. 7, VI)",
                  "Includes defense in administrative and judicial proceedings.",
                ],
                [
                  "Service improvement",
                  "Legitimate interest (art. 7, IX)",
                  "Preference for aggregated or anonymized data.",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "We do not use your documents to train models. The statistical classifier is trained on synthetic data, with no real documents.",
          },
        ],
      },
      {
        id: "papeis-controlador-operador",
        title: "Third-party documents and processing roles",
        blocks: [
          {
            type: "paragraph",
            text: "For the data in your account and for documents you upload to analyze on your own behalf, SentinelPay acts as the controller, because it decides how processing occurs to provide the service.",
          },
          {
            type: "paragraph",
            text: "When you upload third-party documents, such as customer payment slips or employee payslips, you declare that you have a legal basis and authorization for that upload. In that case, you act as the controller of that data and SentinelPay acts as the operator, following your instructions to generate the contracted analysis.",
          },
          {
            type: "paragraph",
            text: "You are responsible for the lawfulness of the upload and for the information provided to the data subjects of those documents.",
          },
        ],
      },
      {
        id: "inteligencia-artificial",
        title: "Use of artificial intelligence",
        blocks: [
          {
            type: "paragraph",
            text: "The analysis is supported by deterministic rules, a statistical classifier and a language model. The result is a risk opinion. It is not a final decision, does not replace human review and does not constitute legal, accounting or financial advice.",
          },
          {
            type: "paragraph",
            text: "By default, the language model runs on the controller's infrastructure through an endpoint compatible with the OpenAI API. The configuration may point to an external provider. When that happens, the document excerpt is masked before being sent.",
          },
          {
            type: "list",
            items: [
              "The model receives the document type, score, band, evidence codes, excerpts from the regulatory knowledge base, language, degradation flags and a masked excerpt of the document, limited to 6,000 characters.",
              "Masking removes CPF, CNPJ, names, amounts, email, phone, address, Pix keys and long digit sequences.",
              "We do not use your documents to train models. Observability traces are also not used for training.",
              "Guardrails check for prompt injection attempts, output content and size limits.",
            ],
          },
          {
            type: "paragraph",
            text: "You may request review of a decision based on automated processing, under article 20 of the LGPD, through the privacy channel.",
          },
        ],
      },
      {
        id: "compartilhamento",
        title: "Sharing and operators",
        blocks: [
          {
            type: "paragraph",
            text: "We do not sell personal data. We share data only with operators necessary for the service and with authorities when there is a valid legal requirement.",
          },
          {
            type: "table",
            table: {
              caption: "Operators used",
              headers: ["Operator", "Purpose", "Data involved", "Region or location"],
              rows: [
                [
                  "Google",
                  "OpenID Connect authentication",
                  "Name, verified email and Google account identifier",
                  "Google global infrastructure",
                ],
                [
                  "Transactional e-mail provider",
                  "Delivery of verification, reset, password changed and already registered e-mail notices",
                  "Recipient e-mail address and message content. Defined by the controller SMTP configuration.",
                  "To be defined with the contracted provider",
                ],
                [
                  "Railway",
                  "Hosting of the API, PostgreSQL and Redis",
                  "Account data, documents, analyses, due dates, notifications and logs",
                  "Region defined in the provider configuration",
                ],
                [
                  "Amazon S3",
                  "Storage of uploaded files and analysis reports, with AES-256 encryption at rest",
                  "Uploaded files and JSON reports",
                  "Region configured in the environment, currently us-east-2",
                ],
                [
                  "Vercel",
                  "Hosting of the web application",
                  "Navigation data and session cookies in the front-end",
                  "Provider global network",
                ],
                [
                  "Langfuse",
                  "Observability of artificial intelligence calls, when enabled",
                  "Masked traces, with hashed identifiers and no readable personal data",
                  "Configured provider environment",
                ],
                [
                  "SMTP server",
                  "Sending email notices",
                  "Account email and notice content",
                  "Server configured by the operator",
                ],
                [
                  "Sentry",
                  "Front-end error monitoring, when configured",
                  "Error events without personal data, cookies or headers",
                  "Configured provider environment",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "SMS and WhatsApp: preferences and consents are recorded, but no external SMS or WhatsApp provider is integrated in this configuration. Notices are available in the app and by email.",
          },
          {
            type: "paragraph",
            text: "We may share data with public authorities upon court order, valid administrative request or legal obligation.",
          },
        ],
      },
      {
        id: "transferencia-internacional",
        title: "International transfer",
        blocks: [
          {
            type: "paragraph",
            text: "Some operators listed in the previous section process data on servers outside Brazil, according to the region column. The transfer occurs to enable authentication, storage, hosting and observability of the service.",
          },
          {
            type: "paragraph",
            text: "When international transfer occurs, the controller relies on the provider's contractual safeguards. You may request information about the transfer and the applicable safeguards through the privacy channel, under article 18 of the LGPD.",
          },
        ],
      },
      {
        id: "armazenamento-e-retencao",
        title: "Storage and retention",
        blocks: [
          {
            type: "paragraph",
            text: "Data is stored in a PostgreSQL database, in S3-compatible object storage for files and reports, and in Redis for rate limiting, login state and token revocation. Logs remain in the hosting infrastructure. Artificial intelligence traces, when enabled, remain in Langfuse.",
          },
          {
            type: "paragraph",
            text: "We keep data while the account exists and while necessary for the purposes of this policy. No automatic purge period is configured for documents and analyses. Access tokens expire in 15 minutes, refresh tokens in 7 days, login states in 10 minutes and rate limit keys in seconds.",
          },
          {
            type: "paragraph",
            text: "E-mail verification tokens expire in 24 hours and password reset tokens in 30 minutes, always single-use. New reset requests replace previous ones.",
          },
          {
            type: "paragraph",
            text: "Automatic deletion of accounts, documents and analyses is not yet available in the API. Deletion requests are recorded through the privacy channel and handled by the controller. Deletion removes the password hash, verification and reset tokens and consent records. Security events tied to the user lose the direct link to the account, preserving the legal retention of security records. Cancelling an ongoing analysis removes the partial report generated up to that point.",
          },
          {
            type: "links",
            items: [
              { label: "Request deletion in your account", href: "/account" },
              { label: "Privacy channel", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "seguranca",
        title: "Security",
        blocks: [
          {
            type: "paragraph",
            text: "We adopt technical and administrative measures to protect personal data, including:",
          },
          {
            type: "list",
            items: [
              "HTTPS with HSTS in production and HttpOnly, SameSite=Lax and Secure cookies.",
              "Content Security Policy and protective headers in the front-end.",
              "Passwords stored only as Argon2id hashes, with configurable parameters and rehash on sign-in.",
              "Single-use verification and password reset tokens, stored only as SHA-256 hashes, with short expiration.",
              "Short-lived access tokens, refresh token rotation and reuse detection.",
              "CSRF protection on authenticated routes.",
              "Owner-based access control on every document, analysis and due date query.",
              "Rate limiting by IP and by user with a 429 response and wait time.",
              "Validation of the actual file type, size and page count, with rejection of encrypted PDFs.",
              "AES-256 encryption at rest in object storage and AES-GCM encryption for notification destinations.",
              "Masking of personal data in logs and before sending artificial intelligence traces.",
              "Guardrails against prompt injection and verification of model output.",
            ],
          },
          {
            type: "paragraph",
            text: "No system is entirely immune to incidents. This policy does not claim any security certification.",
          },
          {
            type: "paragraph",
            text: "If a relevant security incident occurs, we notify the Brazilian National Data Protection Authority and affected data subjects when required by law, with the available information and measures taken, under article 48 of the LGPD.",
          },
        ],
      },
      {
        id: "direitos-do-titular",
        title: "Data subject rights",
        blocks: [
          {
            type: "paragraph",
            text: "You may exercise the rights provided in article 18 of the LGPD. The table below indicates each right and how to exercise it.",
          },
          {
            type: "table",
            table: {
              caption: "Data subject rights and how to exercise them",
              headers: ["Right", "How to exercise"],
              rows: [
                [
                  "Confirmation of processing and access",
                  "Profile and analyses in your account, when available, and the privacy channel.",
                ],
                [
                  "Correction",
                  "Account data can be corrected in your profile or through the privacy channel. Google accounts can also be corrected in the Google account itself.",
                ],
                [
                  "Anonymization, blocking or deletion",
                  "Privacy channel, with analysis of technical and legal feasibility.",
                ],
                [
                  "Portability",
                  "Privacy channel. Automatic export is not yet available in the application.",
                ],
                [
                  "Information about sharing",
                  "Sharing section of this policy and the privacy channel.",
                ],
                [
                  "Information about the possibility of not consenting",
                  "Purposes and legal bases sections and the privacy channel.",
                ],
                [
                  "Revocation of consent",
                  "Notification preferences in the account for SMS and WhatsApp, and the privacy channel for other cases.",
                ],
                ["Objection", "Privacy channel."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "We respond to requests for confirmation of processing and access within 15 days of receipt, under article 19 of the LGPD. Other requests are answered within the applicable legal period. We may request information to confirm your identity before responding.",
          },
          {
            type: "links",
            items: [
              { label: "Open your account", href: "/account" },
              { label: "Privacy channel", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "cookies",
        title: "Cookies and local storage",
        blocks: [
          {
            type: "paragraph",
            text: "We use only cookies necessary for the service and your preferences. We do not use marketing cookies, audience analytics or third-party trackers. We do not use browser local storage for session data or documents.",
          },
          {
            type: "table",
            table: {
              caption: "Cookies used",
              headers: ["Cookie", "Purpose", "Duration"],
              rows: [
                [
                  "sp_session, sp_session_exp, sp_refresh, sp_csrf",
                  "Authenticated session and CSRF protection. HttpOnly, SameSite=Lax and Secure.",
                  "Up to 7 days.",
                ],
                ["sp_oidc", "Completing Google sign-in.", "10 minutes."],
                [
                  "refresh_token, csrf_token",
                  "Backend session and CSRF protection.",
                  "Up to 7 days.",
                ],
                ["theme", "Chosen theme: system, light or dark.", "1 year."],
                ["locale", "Chosen language: Portuguese, Spanish or English.", "1 year."],
                ["date_format", "Chosen date format.", "1 year."],
                ["sp_sidebar", "Sidebar state.", "1 year."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "You can block or delete cookies in your browser settings. Essential cookies are required to authenticate and keep the session. Front-end error monitoring, when configured, uses Sentry and sends only sanitized events, without cookies, headers or personal data.",
          },
        ],
      },
      {
        id: "criancas-e-adolescentes",
        title: "Children and adolescents",
        blocks: [
          {
            type: "paragraph",
            text: "The service is intended for people aged 18 or older. We do not intentionally collect data from children or adolescents. If we identify an account in these conditions, access may be terminated and the data handled in accordance with the law.",
          },
        ],
      },
      {
        id: "alteracoes-da-politica",
        title: "Changes to this policy",
        blocks: [
          {
            type: "paragraph",
            text: "We may update this policy. The current version, date and number appear at the top of this page. Material changes are communicated by email or in-app notice with reasonable advance notice.",
          },
          {
            type: "paragraph",
            text: "You may request the version history through the privacy channel.",
          },
        ],
      },
      {
        id: "contato-e-anpd",
        title: "Contact and ANPD channel",
        blocks: [
          {
            type: "paragraph",
            text: "Questions, data subject requests and inquiries about this policy can be sent through the privacy channel. When configured, the DPO contact appears in section 1.",
          },
          {
            type: "paragraph",
            text: "You may also file a complaint with the Brazilian National Data Protection Authority (ANPD) through the official channels at gov.br/anpd.",
          },
          {
            type: "links",
            items: [
              { label: "Privacy channel", href: "privacy-contact" },
              { label: "Open your account", href: "/account" },
              { label: "Support", href: "/suporte" },
            ],
          },
        ],
      },
    ],
  },
};
