# Model card: classificador de injecao/jailbreak (guardrail-injection-v1)

## Status e cobertura
- **Cobertura limitada.** Treinado apenas em exemplos **sinteticos**; nao houve teste contra ataques reais, adaptativos ou campanhas externas.
- O classificador e uma camada **opcional** (camada 3) de defesa em profundidade. Ele nao substitui a sanitizacao, os padroes, o system prompt nem o judge.
- **NAO VALIDADO** para producao: as metricas abaixo sao sinteticas e nao representam desempenho real.

## Uso pretendido
- Sinalizar texto extraido de documento (OCR/PDF) que se parece com tentativa de injecao/jailbreak.
- Alimentar a analise com uma evidencia `guardrail.classifier_injection` (peso 0) quando a probabilidade passa do limiar configurado (`GUARDRAIL_CLASSIFIER_THRESHOLD`, default 0.5).
- Nunca decide o score, nunca bloqueia a analise sozinho e nunca substitui as camadas 1/2.

## Dados de treino
- Gerador deterministico em `infrastructure/guardrails/synthetic.py` (semente 42).
- Exemplos de injecao: override de instrucoes, mudanca de papel, revelacao de prompt, exfiltracao, alteracao de politica/score, tags falsas de sistema e variacoes com Unicode invisivel/homoglifos, em pt/en/es/fr/de/it.
- Exemplos benignos: linhas de boleto e contracheque sinteticos, instrucoes de pagamento, avisos e classificacao operacional.
- Nenhum documento real, CPF/CNPJ valido, nome real ou dado pessoal foi usado; placeholders sao sinteticos.
- Split estratificado por amostra (75% treino / 25% teste), semente fixa.

## Modelo
- `scikit-learn`: `TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=20000, sublinear_tf=True)` + `LogisticRegression(class_weight="balanced", max_iter=2000)`.
- Texto normalizado (NFKD sem acentos, casefold, espacos colapsados) antes do vetor.
- Artefato: `models/artifacts/guardrail-injection-v1.joblib` (fora do git) + registro JSON com SHA-256. O loader valida hash, versao, `synthetic=true` e `coverage=limited`.
- Treino: `make train-guardrails`.

## Metricas sinteticas (seed 42, 240 amostras, limiar 0.5)
- Execucao local de `make train-guardrails` em 2026-11-14:
  - 180 treino / 60 teste; `precision=1.0`, `recall=1.0`, `f1=1.0`, `roc_auc=1.0`.
  - `dataset_hash=99a02677a19739c718889f9cad0cb6338ae411c0ab1ec9726e5d3e6b9ad69b09`.
  - `sha256` do artefato: `302a74d3220a1d4e77ccf5bca892a1b4f73485b34ccd70072bf91631e9e6b212`.
- A separacao perfeita e esperada porque treino e teste saem do mesmo gerador sintetico; **nao** indica desempenho real. Consulte `models/artifacts/guardrail-injection-v1.json`.
- Com limiar 0.8 o holdout sintetico teve recall 0.17; por isso o default e 0.5, sujeito a calibracao com dados reais.

## Limitacoes e riscos
- **Cobertura limitada**: vocabulario e construcoes sinteticas podem nao cobrir ataques reais, adaptativos, codificados, multimodais ou em idiomas fora do conjunto.
- Falsos positivos podem suprimir a explicacao do LLM (o score deterministico permanece); falsos negativos podem deixar passar texto malicioso que nao altera o score.
- Nao ha avaliacao de robustez contra adversario que conhece o modelo.
- Nao ha calibracao com dados reais; o limiar default e conservador e deve ser revisto com dados de producao.
- O modelo nao inspeciona imagens nem texto que o OCR nao extraiu.

## Privacidade e seguranca
- O texto avaliado nao e logado nem persistido pelo classificador; metricas guardam apenas `(layer, code)`.
- `joblib.load` so ocorre apos validacao de caminho confiavel e SHA-256; ainda assim, trate o diretorio de artefatos como confiavel.
- O sistema **nao e declarado imune**. Esta camada reduz risco e deixa rastro auditavel.
