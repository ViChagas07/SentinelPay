import type { LegalContent } from "./types";

export const es: LegalContent = {
  terms: {
    title: "Términos de uso",
    subtitle:
      "Condiciones para usar SentinelPay en el análisis de boletos, nóminas y recibos brasileños.",
    notice:
      "Aviso: esta es una traducción informativa. En caso de divergencia, prevalece la versión en portugués.",
    sections: [
      {
        id: "aceite-e-definicoes",
        title: "Aceptación y definiciones",
        blocks: [
          {
            type: "paragraph",
            text: "Estos Términos regulan el uso de SentinelPay. Al marcar la casilla de aceptación en la pantalla de inicio de sesión y completar el registro o la autenticación, con Google o con correo y contraseña, usted acepta estos Términos y la Política de privacidad.",
          },
          {
            type: "paragraph",
            text: "Para facilitar la lectura, los términos siguientes tienen estos significados:",
          },
          {
            type: "list",
            items: [
              "SentinelPay: la plataforma, incluidos el sitio, la aplicación web, la API y el pipeline de análisis.",
              "Usuario: persona física mayor de 18 años, autenticada con una cuenta de Google o con correo y contraseña.",
              "Documento: archivo PDF, PNG o JPG enviado por el usuario, como boleto, nómina o recibo.",
              "Análisis: procesamiento del documento que genera una puntuación de riesgo de 0 a 100, clase de riesgo, evidencias, justificación y campos extraídos.",
              "Dosier: conjunto mostrado en la plataforma con el resultado del análisis, las evidencias y los campos extraídos.",
              "Cuenta: registro creado en el primer acceso con Google o en el registro con correo y contraseña, vinculado a un correo verificado.",
            ],
          },
          {
            type: "note",
            text: "Si no está de acuerdo con estos Términos, no use el servicio.",
          },
        ],
      },
      {
        id: "o-que-o-servico-faz",
        title: "Qué hace y qué no hace el servicio",
        blocks: [
          {
            type: "paragraph",
            text: "SentinelPay analiza boletos, nóminas y recibos brasileños. El resultado combina reglas deterministas basadas en normas como FEBRABAN para boletos e INSS y CLT para nóminas, un clasificador estadístico y una capa de interpretación por modelo de lenguaje. La salida es un dictamen de riesgo con puntuación de 0 a 100, clase (bajo, atención o alto), evidencias por regla, justificación en texto y campos extraídos del documento.",
          },
          {
            type: "subheading",
            text: "Lo que el servicio no hace",
          },
          {
            type: "list",
            items: [
              "No es una pericia técnica ni un laudo pericial.",
              "No sustituye la revisión humana del documento.",
              "No constituye asesoría jurídica, contable o financiera.",
              "No decide pagos, aprobación de crédito ni ningún acto negocial.",
              "No garantiza que el documento sea auténtico o fraudulento.",
              "Puede producir falsos positivos y falsos negativos.",
            ],
          },
          {
            type: "note",
            text: "Use el resultado como una señal adicional de riesgo. La decisión final siempre es suya o de quien analiza el documento.",
          },
        ],
      },
      {
        id: "cadastro-e-conta",
        title: "Registro y cuenta",
        blocks: [
          {
            type: "paragraph",
            text: "El acceso puede realizarse con inicio de sesión de Google mediante OpenID Connect o con correo y contraseña. Con contraseña, almacenamos solo el hash Argon2id, nunca la contraseña en texto. Del perfil de Google almacenamos el nombre, el correo verificado y el identificador de la cuenta de Google. La foto del perfil no se almacena.",
          },
          {
            type: "list",
            items: [
              "Usted declara tener 18 años o más y que la información de la cuenta es veraz.",
              "Usted es responsable de mantener seguros el acceso a su cuenta de Google y su contraseña.",
              "La contraseña debe tener entre 10 y 128 caracteres, no puede estar entre las más usadas y no puede contener su nombre ni su correo.",
              "El registro con correo y contraseña solo se activa después de la confirmación del correo.",
              "La sesión usa cookies HttpOnly y tokens de corta duración.",
              "El uso es personal e intransferible. Cada correo corresponde a una cuenta en SentinelPay.",
            ],
          },
          {
            type: "paragraph",
            text: "En caso de uso indebido, el acceso puede suspenderse conforme a la sección 10.",
          },
        ],
      },
      {
        id: "uso-permitido-e-proibido",
        title: "Uso permitido y prohibido",
        blocks: [
          {
            type: "subheading",
            text: "Está permitido",
          },
          {
            type: "list",
            items: [
              "Enviar documentos que usted tenga derecho a tratar.",
              "Consultar análisis, dosieres y vencimientos generados a partir de sus envíos.",
              "Configurar notificaciones y recordatorios de vencimiento.",
              "Usar la plataforma para prevención y verificación de riesgo.",
            ],
          },
          {
            type: "subheading",
            text: "Está prohibido",
          },
          {
            type: "list",
            items: [
              "Enviar documentos sin base legal o autorización.",
              "Usar el servicio para crear, alterar o perfeccionar documentos fraudulentos.",
              "Intentar eludir límites de uso, autenticación o limitación de tasa.",
              "Realizar ingeniería inversa, raspado o extracción masiva de datos.",
              "Enviar archivos maliciosos o intentar comprometer la seguridad de la plataforma.",
              "Usar el resultado como única base para decisiones que afecten derechos de terceros, sin revisión humana.",
            ],
          },
        ],
      },
      {
        id: "documentos-de-terceiros",
        title: "Documentos de terceros",
        blocks: [
          {
            type: "paragraph",
            text: "Usted puede enviar documentos de terceros, como boletos emitidos contra otra persona o nóminas de empleados, solo si tiene base legal y autorización para ello. En ese caso, usted actúa como controlador de esos datos y SentinelPay actúa como operador, tratando los datos únicamente para generar el análisis contratado.",
          },
          {
            type: "paragraph",
            text: "Usted responde por la licitud del envío y por la información proporcionada a los titulares. SentinelPay no verifica el origen de cada documento enviado.",
          },
        ],
      },
      {
        id: "limites-de-arquivo-e-uso",
        title: "Límites de archivo y de uso",
        blocks: [
          {
            type: "list",
            items: [
              "Formatos aceptados: PDF, PNG y JPG, con las extensiones .pdf, .png, .jpg y .jpeg.",
              "Tamaño máximo: 25 MB por archivo.",
              "PDF: hasta 50 páginas. La lectura por OCR procesa hasta 20 páginas por análisis.",
              "Los PDF protegidos con contraseña o cifrados son rechazados.",
              "Análisis simultáneos: hasta 2 por usuario.",
              "Las solicitudes pasan por limitación de tasa por IP y por usuario. Al superar el límite, la API responde con el código 429 e indica el tiempo de espera.",
            ],
          },
          {
            type: "note",
            text: "Los límites pueden ajustarse por configuración. El límite vigente aparece en la pantalla de envío.",
          },
        ],
      },
      {
        id: "propriedade-intelectual",
        title: "Propiedad intelectual",
        blocks: [
          {
            type: "paragraph",
            text: "La plataforma, la marca, el código, las reglas, los textos y los modelos pertenecen al controlador de SentinelPay o a sus licenciantes. Le concedemos una licencia limitada, revocable, no exclusiva e intransferible para usar el servicio conforme a estos Términos.",
          },
          {
            type: "paragraph",
            text: "Los documentos enviados siguen siendo suyos. Usted nos concede una licencia limitada para almacenar, procesar y generar el análisis y el dosier, exclusivamente para prestar el servicio.",
          },
        ],
      },
      {
        id: "disponibilidade-e-mudancas",
        title: "Disponibilidad y cambios en el servicio",
        blocks: [
          {
            type: "paragraph",
            text: "Buscamos mantener el servicio disponible, pero puede quedar fuera de línea por mantenimiento, fallas, dependencias de terceros o eventos fuera de nuestro control. No hay garantía de funcionamiento ininterrumpido.",
          },
          {
            type: "paragraph",
            text: "El análisis depende de una cola de procesamiento y de modelos de inteligencia artificial. Podemos cambiar etapas, versiones de reglas, modelos y límites, registrando la versión usada en el dosier cuando esté disponible.",
          },
        ],
      },
      {
        id: "limitacao-de-responsabilidade",
        title: "Limitación de responsabilidad",
        blocks: [
          {
            type: "paragraph",
            text: "En la máxima medida permitida por la ley brasileña, no respondemos por daños indirectos, lucro cesante o decisiones tomadas exclusivamente con base en el dictamen de riesgo. Nada en estos Términos limita los derechos del consumidor previstos en el Código de Defensa del Consumidor ni excluye la responsabilidad por dolo o culpa grave.",
          },
          {
            type: "paragraph",
            text: "Usted es responsable de los documentos que envía y del uso que hace del resultado.",
          },
        ],
      },
      {
        id: "suspensao-e-encerramento",
        title: "Suspensión y cierre de la cuenta",
        blocks: [
          {
            type: "list",
            items: [
              "Usted puede dejar de usar el servicio en cualquier momento y solicitar la eliminación de la cuenta por el canal de privacidad.",
              "Podemos suspender o cerrar el acceso en caso de violación de estos Términos, riesgo de seguridad, determinación legal o uso abusivo.",
              "La eliminación automática de cuenta, documentos y análisis aún no está disponible en la API. La solicitud se registra y se atiende por el canal de privacidad, conforme a la Política de privacidad.",
            ],
          },
          {
            type: "links",
            items: [
              { label: "Derechos del titular en la cuenta", href: "/account" },
              { label: "Política de privacidad", href: "/privacidade" },
            ],
          },
        ],
      },
      {
        id: "alteracoes-dos-termos",
        title: "Cambios en los Términos",
        blocks: [
          {
            type: "paragraph",
            text: "Podemos actualizar estos Términos. La versión vigente, la fecha y el número aparecen en la parte superior de esta página. Los cambios relevantes se comunican por correo electrónico o por aviso en la aplicación con antelación razonable.",
          },
          {
            type: "paragraph",
            text: "El uso continuo después de la fecha de vigencia representa la aceptación de la nueva versión, cuando la ley lo permita. Si no está de acuerdo, puede cerrar la cuenta.",
          },
        ],
      },
      {
        id: "lei-aplicavel-e-foro",
        title: "Ley aplicable y jurisdicción",
        blocks: [
          {
            type: "paragraph",
            text: "Estos Términos se rigen por las leyes brasileñas, incluida la Ley General de Protección de Datos y el Código de Defensa del Consumidor cuando sea aplicable. Se elige el fuero del domicilio del consumidor, cuando así lo exija la ley.",
          },
          {
            type: "links",
            items: [
              { label: "Canal de privacidad", href: "privacy-contact" },
              { label: "Soporte", href: "/suporte" },
              { label: "Política de privacidad", href: "/privacidade" },
            ],
          },
        ],
      },
    ],
  },
  privacy: {
    title: "Política de privacidad",
    subtitle:
      "Cómo SentinelPay trata los datos personales en el análisis de boletos, nóminas y recibos, conforme a la LGPD.",
    notice:
      "Aviso: esta es una traducción informativa. En caso de divergencia, prevalece la versión en portugués.",
    sections: [
      {
        id: "quem-somos",
        title: "Quiénes somos y quién es el controlador",
        blocks: [
          {
            type: "paragraph",
            text: "SentinelPay es una plataforma de análisis de riesgo para documentos financieros brasileños. El controlador es la persona física o jurídica responsable de las decisiones sobre el tratamiento de datos personales descrito en esta política.",
          },
          { type: "identity" },
          {
            type: "paragraph",
            text: "El Encargado del tratamiento de datos personales (DPO) es el canal de comunicación entre usted, el controlador y la Autoridad Nacional de Protección de Datos, conforme al art. 41 de la LGPD.",
          },
          {
            type: "note",
            text: "Los campos de identificación aparecen cuando están configurados. Si algún dato no está visible, solicite la identificación del controlador y el contacto del Encargado por el canal de privacidad.",
          },
          {
            type: "links",
            items: [
              { label: "Derechos del titular en la cuenta", href: "/account" },
              { label: "Canal de privacidad", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "dados-tratados",
        title: "Qué datos tratamos",
        blocks: [
          {
            type: "paragraph",
            text: "Tratamos solo los datos necesarios para autenticar, analizar documentos, generar el dosier, crear vencimientos y mantener la seguridad del servicio.",
          },
          {
            type: "table",
            table: {
              caption: "Categorías de datos personales tratados",
              headers: ["Categoría", "Datos"],
              rows: [
                [
                  "Datos de cuenta (Google)",
                  "Nombre, correo verificado, identificador de la cuenta de Google, rol en la plataforma, idioma preferido y zona horaria. La foto del perfil no se almacena.",
                ],
                [
                  "Datos de cuenta (correo y contraseña)",
                  "Nombre, correo normalizado, hash Argon2id de la contraseña (nunca la contraseña en texto), fecha del último cambio de contraseña, contador de fallos de acceso y bloqueo temporal.",
                ],
                [
                  "Tokens de verificación y restablecimiento",
                  "Hash SHA-256 del token de uso único, finalidad, validez, fecha de uso, IP y user agent de la solicitud. El token en texto existe solo en el enlace enviado por correo.",
                ],
                [
                  "Consentimientos",
                  "Documento aceptado, versión vigente, fecha y hora de la aceptación, origen, IP y user agent, como prueba de consentimiento.",
                ],
                [
                  "Eventos de seguridad",
                  "Registro, inicio de sesión, fallo de inicio de sesión, bloqueo, verificación de correo, solicitud de restablecimiento, restablecimiento completado, cambio de contraseña y salida, con fecha, IP y user agent. Nunca incluyen contraseña, hash ni token.",
                ],
                [
                  "Datos de los documentos enviados",
                  "Archivo PDF, PNG o JPG, nombre del archivo saneado, tipo, tamaño, hash SHA-256 y fecha de envío. El contenido puede incluir nombre, CPF, CNPJ, dirección, datos bancarios, salario y descuentos.",
                ],
                [
                  "Datos generados por el análisis",
                  "Puntuación de riesgo, clase, evidencias por regla, justificación, inconsistencias, campos extraídos, versiones de regla y de modelo, indicadores de degradación y fechas. CPF y CNPJ aparecen enmascarados en el dosier.",
                ],
                [
                  "Datos de uso y técnicos",
                  "Registros de aplicación con fecha y hora, ruta, estado e identificador de solicitud, dirección IP usada en la limitación de tasa, métricas agregadas y eventos de error del front-end cuando el monitoreo está configurado.",
                ],
                [
                  "Datos de preferencias",
                  "Tema, idioma, formato de fecha, canales de notificación, hora y antelación de los recordatorios. Los destinos de SMS y WhatsApp están cifrados.",
                ],
              ],
            },
          },
        ],
      },
      {
        id: "finalidades",
        title: "Para qué usamos cada dato",
        blocks: [
          {
            type: "table",
            table: {
              caption: "Finalidades del tratamiento",
              headers: ["Finalidad", "Datos involucrados"],
              rows: [
                ["Autenticar y mantener la sesión", "Datos de cuenta y cookies de sesión."],
                [
                  "Analizar el documento y generar el dosier",
                  "Documento enviado, datos extraídos, evidencias, puntuación y justificación.",
                ],
                [
                  "Crear vencimientos y enviar recordatorios",
                  "Valor, fecha de vencimiento, descripción, canales y destinos de notificación.",
                ],
                [
                  "Prevenir fraude, abuso e incidentes de seguridad",
                  "Registros, dirección IP, identificador de usuario, métricas y eventos de error.",
                ],
                [
                  "Monitorear y mejorar el servicio",
                  "Métricas agregadas, trazas enmascaradas y errores sin datos sensibles.",
                ],
                [
                  "Cumplir obligaciones legales y ejercer derechos",
                  "Datos necesarios para atender órdenes legales, responder a titulares y registrar incidentes.",
                ],
                [
                  "Prestar soporte",
                  "Datos de cuenta e información proporcionada por usted en la atención.",
                ],
              ],
            },
          },
        ],
      },
      {
        id: "bases-legais",
        title: "Bases legales",
        blocks: [
          {
            type: "paragraph",
            text: "Cada finalidad tiene una base legal prevista en el art. 7 de la LGPD. Cuando la base sea el consentimiento, usted puede revocarlo en cualquier momento por los canales indicados en esta política.",
          },
          {
            type: "table",
            table: {
              caption: "Bases legales por finalidad",
              headers: ["Finalidad", "Base legal", "Observación"],
              rows: [
                [
                  "Autenticación y ejecución del servicio",
                  "Ejecución de contrato (art. 7, V)",
                  "Necesario para usar la plataforma.",
                ],
                [
                  "Análisis de documentos y dosier",
                  "Ejecución de contrato (art. 7, V)",
                  "El tratamiento es el propio servicio contratado.",
                ],
                [
                  "Vencimientos y recordatorios en la aplicación y por correo",
                  "Ejecución de contrato (art. 7, V)",
                  "Usa el correo de la cuenta.",
                ],
                [
                  "SMS y WhatsApp",
                  "Consentimiento (art. 7, I)",
                  "Registrado con fecha y hora en el momento de la activación.",
                ],
                [
                  "Seguridad, prevención de fraude y abuso",
                  "Interés legítimo (art. 7, IX)",
                  "Con medidas para limitar el impacto sobre el titular.",
                ],
                [
                  "Registros, métricas y monitoreo",
                  "Interés legítimo (art. 7, IX)",
                  "Datos técnicos y enmascaramiento de datos personales.",
                ],
                [
                  "Cumplimiento de obligación legal o regulatoria",
                  "Obligación legal o regulatoria (art. 7, II)",
                  "Incluye la atención a la ANPD y a autoridades competentes.",
                ],
                [
                  "Ejercicio regular de derechos",
                  "Ejercicio regular de derechos (art. 7, VI)",
                  "Incluye la defensa en procesos administrativos y judiciales.",
                ],
                [
                  "Mejora del servicio",
                  "Interés legítimo (art. 7, IX)",
                  "Preferencia por datos agregados o anonimizados.",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "No usamos sus documentos para entrenar modelos. El clasificador estadístico se entrena con datos sintéticos, sin documentos reales.",
          },
        ],
      },
      {
        id: "papeis-controlador-operador",
        title: "Documentos de terceros y roles de tratamiento",
        blocks: [
          {
            type: "paragraph",
            text: "En los datos de su cuenta y en los documentos que usted envía para analizar en nombre propio, SentinelPay actúa como controlador, porque decide cómo ocurre el tratamiento para prestar el servicio.",
          },
          {
            type: "paragraph",
            text: "Cuando usted envía documentos de terceros, como boletos de clientes o nóminas de empleados, declara tener base legal y autorización para ese envío. En ese caso, usted actúa como controlador de esos datos y SentinelPay actúa como operador, siguiendo sus instrucciones para generar el análisis contratado.",
          },
          {
            type: "paragraph",
            text: "Usted responde por la licitud del envío y por la información proporcionada a los titulares de esos documentos.",
          },
        ],
      },
      {
        id: "inteligencia-artificial",
        title: "Uso de inteligencia artificial",
        blocks: [
          {
            type: "paragraph",
            text: "El análisis se apoya en reglas deterministas, un clasificador estadístico y un modelo de lenguaje. El resultado es un dictamen de riesgo. No es una decisión definitiva, no sustituye la revisión humana ni constituye asesoría jurídica, contable o financiera.",
          },
          {
            type: "paragraph",
            text: "Por defecto, el modelo de lenguaje se ejecuta en la infraestructura del controlador, mediante un endpoint compatible con la API de OpenAI. La configuración puede apuntar a un proveedor externo. Cuando eso ocurre, el fragmento del documento se enmascara antes del envío.",
          },
          {
            type: "list",
            items: [
              "El modelo recibe el tipo de documento, la puntuación, la clase, los códigos de las evidencias, fragmentos de la base normativa, el idioma, los indicadores de degradación y un fragmento enmascarado del documento, limitado a 6.000 caracteres.",
              "El enmascaramiento elimina CPF, CNPJ, nombres, valores, correo, teléfono, dirección, claves Pix y secuencias largas de dígitos.",
              "No usamos sus documentos para entrenar modelos. Las trazas de observabilidad tampoco se usan para entrenamiento.",
              "Los guardrails verifican intentos de inyección de prompt, el contenido de la salida y los límites de tamaño.",
            ],
          },
          {
            type: "paragraph",
            text: "Usted puede solicitar la revisión de una decisión tomada con base en tratamiento automatizado, conforme al art. 20 de la LGPD, por el canal de privacidad.",
          },
        ],
      },
      {
        id: "compartilhamento",
        title: "Compartición y operadores",
        blocks: [
          {
            type: "paragraph",
            text: "No vendemos datos personales. Compartimos datos solo con operadores necesarios para el funcionamiento del servicio y con autoridades cuando exista una determinación legal válida.",
          },
          {
            type: "table",
            table: {
              caption: "Operadores utilizados",
              headers: ["Operador", "Finalidad", "Datos involucrados", "Región o ubicación"],
              rows: [
                [
                  "Google",
                  "Autenticación por OpenID Connect",
                  "Nombre, correo verificado e identificador de la cuenta de Google",
                  "Infraestructura global de Google",
                ],
                [
                  "Proveedor de correo transaccional",
                  "Envío de los correos de verificación, restablecimiento, aviso de contraseña cambiada y aviso de correo ya registrado",
                  "Dirección de correo del destinatario y contenido del mensaje. Definido por la configuración SMTP del controlador.",
                  "A definir según el proveedor contratado",
                ],
                [
                  "Railway",
                  "Alojamiento de la API, PostgreSQL y Redis",
                  "Datos de cuenta, documentos, análisis, vencimientos, notificaciones y registros",
                  "Región definida en la configuración del proveedor",
                ],
                [
                  "Amazon S3",
                  "Almacenamiento de los archivos enviados y de los informes de análisis, con cifrado AES-256 en reposo",
                  "Archivos enviados e informes JSON",
                  "Región configurada en el entorno, actualmente us-east-2",
                ],
                [
                  "Vercel",
                  "Alojamiento de la aplicación web",
                  "Datos de navegación y cookies de sesión en el front-end",
                  "Red global del proveedor",
                ],
                [
                  "Langfuse",
                  "Observabilidad de las llamadas de inteligencia artificial, cuando está habilitada",
                  "Trazas enmascaradas, con identificadores en hash y sin datos personales legibles",
                  "Entorno configurado del proveedor",
                ],
                [
                  "Servidor SMTP",
                  "Envío de avisos por correo electrónico",
                  "Correo de la cuenta y contenido del aviso",
                  "Servidor configurado por el operador",
                ],
                [
                  "Sentry",
                  "Monitoreo de errores del front-end, cuando está configurado",
                  "Eventos de error sin datos personales, cookies ni encabezados",
                  "Entorno configurado del proveedor",
                ],
              ],
            },
          },
          {
            type: "note",
            text: "SMS y WhatsApp: las preferencias y los consentimientos se registran, pero no hay un proveedor externo de SMS o WhatsApp integrado en esta configuración. Los avisos están disponibles en la aplicación y por correo electrónico.",
          },
          {
            type: "paragraph",
            text: "Podemos compartir datos con autoridades públicas mediante orden judicial, requerimiento administrativo válido u obligación legal.",
          },
        ],
      },
      {
        id: "transferencia-internacional",
        title: "Transferencia internacional",
        blocks: [
          {
            type: "paragraph",
            text: "Algunos operadores listados en la sección anterior procesan datos en servidores fuera de Brasil, conforme a la columna de región. La transferencia ocurre para viabilizar la autenticación, el almacenamiento, el alojamiento y la observabilidad del servicio.",
          },
          {
            type: "paragraph",
            text: "Cuando ocurre la transferencia internacional, el controlador se apoya en las salvaguardas contractuales del proveedor. Usted puede solicitar información sobre la transferencia y las salvaguardas aplicables por el canal de privacidad, conforme al art. 18 de la LGPD.",
          },
        ],
      },
      {
        id: "armazenamento-e-retencao",
        title: "Almacenamiento y retención",
        blocks: [
          {
            type: "paragraph",
            text: "Los datos se guardan en una base PostgreSQL, en almacenamiento de objetos compatible con S3 para archivos e informes, y en Redis para limitación de tasa, estado de inicio de sesión y revocación de tokens. Los registros permanecen en la infraestructura de alojamiento. Las trazas de inteligencia artificial, cuando están habilitadas, permanecen en Langfuse.",
          },
          {
            type: "paragraph",
            text: "Conservamos los datos mientras exista la cuenta y mientras sean necesarios para las finalidades de esta política. No hay un plazo automático de purga configurado para documentos y análisis. Los tokens de acceso expiran en 15 minutos, los tokens de actualización en 7 días, los estados de inicio de sesión en 10 minutos y las claves de limitación de tasa en segundos.",
          },
          {
            type: "paragraph",
            text: "Los tokens de verificación de correo expiran en 24 horas y los de restablecimiento de contraseña en 30 minutos, siempre de uso único. Las nuevas solicitudes de restablecimiento sustituyen a las anteriores.",
          },
          {
            type: "paragraph",
            text: "La eliminación automática de cuenta, documentos y análisis aún no está disponible en la API. La solicitud de eliminación se registra por el canal de privacidad y la atiende el controlador. La eliminación borra el hash de la contraseña, los tokens de verificación y restablecimiento y los registros de consentimiento. Los eventos de seguridad vinculados al usuario pierden el vínculo directo con la cuenta, para preservar la guarda legal de los registros de seguridad. La cancelación de un análisis en curso elimina el informe parcial generado hasta ese momento.",
          },
          {
            type: "links",
            items: [
              { label: "Solicitar eliminación en la cuenta", href: "/account" },
              { label: "Canal de privacidad", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "seguranca",
        title: "Seguridad",
        blocks: [
          {
            type: "paragraph",
            text: "Adoptamos medidas técnicas y administrativas para proteger los datos personales, entre ellas:",
          },
          {
            type: "list",
            items: [
              "HTTPS con HSTS en producción y cookies HttpOnly, SameSite=Lax y Secure.",
              "Política de seguridad de contenido y encabezados de protección en el front-end.",
              "Contraseñas guardadas solo como hash Argon2id, con parámetros configurables y rehash en el inicio de sesión.",
              "Tokens de verificación y restablecimiento de contraseña de uso único, guardados solo como hash SHA-256, con expiración corta.",
              "Tokens de acceso de corta duración, rotación de tokens de actualización y detección de reutilización.",
              "Protección contra CSRF en las rutas autenticadas.",
              "Control de acceso por propietario en cada consulta de documento, análisis y vencimiento.",
              "Limitación de tasa por IP y por usuario con respuesta 429 y tiempo de espera.",
              "Validación del tipo real del archivo, del tamaño y del número de páginas, con rechazo de PDF cifrado.",
              "Cifrado AES-256 en reposo en el almacenamiento de objetos y cifrado AES-GCM en los destinos de notificación.",
              "Enmascaramiento de datos personales en los registros y antes del envío de trazas de inteligencia artificial.",
              "Guardrails contra inyección de prompt y verificación de la salida del modelo.",
            ],
          },
          {
            type: "paragraph",
            text: "Ningún sistema es totalmente inmune a incidentes. No hay una certificación de seguridad declarada en esta política.",
          },
          {
            type: "paragraph",
            text: "Si ocurre un incidente de seguridad relevante, comunicamos a la Autoridad Nacional de Protección de Datos y a los titulares afectados cuando la ley lo exija, con la información disponible y las medidas adoptadas, conforme al art. 48 de la LGPD.",
          },
        ],
      },
      {
        id: "direitos-do-titular",
        title: "Derechos del titular",
        blocks: [
          {
            type: "paragraph",
            text: "Usted puede ejercer los derechos previstos en el art. 18 de la LGPD. La tabla siguiente indica el derecho y el camino para ejercerlo.",
          },
          {
            type: "table",
            table: {
              caption: "Derechos del titular y cómo ejercerlos",
              headers: ["Derecho", "Cómo ejercer"],
              rows: [
                [
                  "Confirmación de tratamiento y acceso",
                  "Perfil y análisis en la cuenta, cuando estén disponibles, y canal de privacidad.",
                ],
                [
                  "Corrección",
                  "Los datos de cuenta pueden corregirse en el perfil o por el canal de privacidad. Las cuentas de Google también pueden corregirse en la propia cuenta de Google.",
                ],
                [
                  "Anonimización, bloqueo o eliminación",
                  "Canal de privacidad, con análisis de viabilidad técnica y legal.",
                ],
                [
                  "Portabilidad",
                  "Canal de privacidad. La exportación automática aún no está disponible en la aplicación.",
                ],
                [
                  "Información sobre compartición",
                  "Sección de compartición de esta política y canal de privacidad.",
                ],
                [
                  "Información sobre la posibilidad de no consentir",
                  "Secciones de finalidades y bases legales y canal de privacidad.",
                ],
                [
                  "Revocación del consentimiento",
                  "Preferencias de notificación en la cuenta para SMS y WhatsApp, y canal de privacidad para los demás casos.",
                ],
                ["Oposición", "Canal de privacidad."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "Respondemos a las solicitudes de confirmación de tratamiento y de acceso en hasta 15 días, contados desde la recepción, conforme al art. 19 de la LGPD. Las demás solicitudes se responden en el plazo legal aplicable. Podemos solicitar información para confirmar su identidad antes de atender.",
          },
          {
            type: "links",
            items: [
              { label: "Abrir la cuenta", href: "/account" },
              { label: "Canal de privacidad", href: "privacy-contact" },
            ],
          },
        ],
      },
      {
        id: "cookies",
        title: "Cookies y almacenamiento local",
        blocks: [
          {
            type: "paragraph",
            text: "Usamos solo cookies necesarias para el servicio y sus preferencias. No usamos cookies de marketing, de análisis de audiencia ni rastreadores de terceros. No usamos almacenamiento local del navegador para datos de sesión o documentos.",
          },
          {
            type: "table",
            table: {
              caption: "Cookies utilizadas",
              headers: ["Cookie", "Finalidad", "Duración"],
              rows: [
                [
                  "sp_session, sp_session_exp, sp_refresh, sp_csrf",
                  "Sesión autenticada y protección contra CSRF. HttpOnly, SameSite=Lax y Secure.",
                  "Hasta 7 días.",
                ],
                ["sp_oidc", "Finalización del inicio de sesión de Google.", "10 minutos."],
                [
                  "refresh_token, csrf_token",
                  "Sesión en el backend y protección contra CSRF.",
                  "Hasta 7 días.",
                ],
                ["theme", "Tema elegido: sistema, claro u oscuro.", "1 año."],
                ["locale", "Idioma elegido: portugués, español o inglés.", "1 año."],
                ["date_format", "Formato de fecha elegido.", "1 año."],
                ["sp_sidebar", "Estado de la barra lateral.", "1 año."],
              ],
            },
          },
          {
            type: "paragraph",
            text: "Usted puede bloquear o eliminar cookies en la configuración del navegador. Las cookies esenciales son necesarias para autenticar y mantener la sesión. El monitoreo de errores del front-end, cuando está configurado, usa Sentry y envía solo eventos tratados, sin cookies, encabezados ni datos personales.",
          },
        ],
      },
      {
        id: "criancas-e-adolescentes",
        title: "Niños y adolescentes",
        blocks: [
          {
            type: "paragraph",
            text: "El servicio está destinado a mayores de 18 años. No recopilamos intencionalmente datos de niños o adolescentes. Si identificamos una cuenta en esas condiciones, el acceso puede cerrarse y los datos tratarse conforme a la ley.",
          },
        ],
      },
      {
        id: "alteracoes-da-politica",
        title: "Cambios en esta política",
        blocks: [
          {
            type: "paragraph",
            text: "Podemos actualizar esta política. La versión vigente, la fecha y el número aparecen en la parte superior de esta página. Los cambios relevantes se comunican por correo electrónico o por aviso en la aplicación con antelación razonable.",
          },
          {
            type: "paragraph",
            text: "Usted puede solicitar el historial de versiones por el canal de privacidad.",
          },
        ],
      },
      {
        id: "contato-e-anpd",
        title: "Contacto y canal de la ANPD",
        blocks: [
          {
            type: "paragraph",
            text: "Las dudas, solicitudes de titulares y consultas sobre esta política pueden enviarse por el canal de privacidad. Cuando está configurado, el contacto del Encargado aparece en la sección 1.",
          },
          {
            type: "paragraph",
            text: "Usted también puede presentar una reclamación ante la Autoridad Nacional de Protección de Datos (ANPD) por los canales oficiales en gov.br/anpd.",
          },
          {
            type: "links",
            items: [
              { label: "Canal de privacidad", href: "privacy-contact" },
              { label: "Abrir la cuenta", href: "/account" },
              { label: "Soporte", href: "/suporte" },
            ],
          },
        ],
      },
    ],
  },
};
