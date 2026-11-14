import re
import unicodedata
from dataclasses import dataclass, field

from paysentineliq.application.ports.guardrails import InjectionClassifierPort
from paysentineliq.application.security.redaction import (
    contains_sensitive_term,
    find_sensitive_patterns,
)
from paysentineliq.domain.analysis import AnalysisEvidence
from paysentineliq.domain.scoring import SeverityLevel

GUARDRAIL_RULE_SET_VERSION = "guardrails-v1"

GUARDRAIL_LAYER_INPUT = "input_sanitization"
GUARDRAIL_LAYER_PATTERNS = "injection_patterns"
GUARDRAIL_LAYER_CLASSIFIER = "classifier"
GUARDRAIL_LAYER_OUTPUT = "output_validation"
GUARDRAIL_LAYER_JUDGE = "judge"

_INVISIBLE_CHARS = frozenset(
    {
        "\u00ad",
        "\u180e",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2060",
        "\u2061",
        "\u2062",
        "\u2063",
        "\u2064",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\ufeff",
    },
)

_HOMOGLYPHS = {
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
    "\u0458": "j",
    "\u0455": "s",
    "\u04bb": "h",
    "\u0501": "d",
    "\u051b": "q",
    "\u051d": "w",
    "\u0410": "A",
    "\u0415": "E",
    "\u041e": "O",
    "\u0420": "P",
    "\u0421": "C",
    "\u0423": "Y",
    "\u0425": "X",
    "\u0406": "I",
    "\u0408": "J",
    "\u0405": "S",
    "\u03b1": "a",
    "\u03bf": "o",
    "\u03b5": "e",
    "\u03b9": "i",
    "\u03ba": "k",
    "\u03bd": "v",
    "\u03c1": "p",
    "\u03c4": "t",
    "\u03c5": "u",
    "\u03c7": "x",
    "\u0391": "A",
    "\u0392": "B",
    "\u0395": "E",
    "\u0396": "Z",
    "\u0397": "H",
    "\u0399": "I",
    "\u039a": "K",
    "\u039c": "M",
    "\u039d": "N",
    "\u039f": "O",
    "\u03a1": "P",
    "\u03a4": "T",
    "\u03a5": "Y",
    "\u03a7": "X",
}

_OVERRIDE_VERBS = (
    r"(?:ignore|ignorar|ignora|ignorieren|ignorez|desconsidere|desconsiderar|olvide|olvida|"
    r"olvidar|disregard|forget|esqueca|esquece|no siga|nao siga|nao aplique|no apliques|"
    r"non applicare|ne pas suivre)"
)
_OVERRIDE_TARGETS = (
    r"(?:previous|prior|above|earlier|anteriores?|previas?|precedentes?|precedenti|"
    r"vorherigen|bisherigen|instrucoes|instrucciones|istruzioni|anweisungen|instructions|"
    r"regras|rules|reglas|regole|regeln)"
)

_PATTERNS: tuple[tuple[str, SeverityLevel, re.Pattern[str], str], ...] = (
    (
        "instruction_override",
        SeverityLevel.HIGH,
        re.compile(rf"\b{_OVERRIDE_VERBS}\b.{{0,80}}?\b{_OVERRIDE_TARGETS}\b", re.DOTALL),
        "guardrail.prompt_injection",
    ),
    (
        "policy_override",
        SeverityLevel.HIGH,
        re.compile(
            r"\b(?:classifique|classify|clasifique|classifica|classificar|marque|mark|marcar|"
            r"set|defina|definir)\b.{0,60}?\b(?:baixo risco|low risk|bajo riesgo|risco baixo|"
            r"safe|seguro|aprovado|approved|zero|0)\b",
            re.DOTALL,
        ),
        "guardrail.policy_override",
    ),
    (
        "policy_override",
        SeverityLevel.HIGH,
        re.compile(
            r"\b(?:aprove|aprovar|approve|apruebe|aprova)\b.{0,40}?\b(?:documento|document|"
            r"boleto|payslip|contracheque|este|this)\b",
            re.DOTALL,
        ),
        "guardrail.policy_override",
    ),
    (
        "prompt_disclosure",
        SeverityLevel.HIGH,
        re.compile(
            r"\b(?:revele|revelar|reveal|mostre|mostrar|show|imprima|imprimir|print|repita|"
            r"repetir|repeat|exiba|display|revela|muestra|zeige|affiche|mostra)\b.{0,50}?\b"
            r"(?:prompt|instrucoes|instructions|instrucciones|istruzioni|anweisungen)\b",
            re.DOTALL,
        ),
        "guardrail.prompt_disclosure",
    ),
    (
        "role_change",
        SeverityLevel.HIGH,
        re.compile(
            r"(?:\ba partir de agora\b|\bfrom now on\b|\bdesde ahora\b|\bab jetzt\b|"
            r"\bdesormais\b).{0,60}?\b(?:voce|you|tu|sie|vous|voi)\b|"
            r"\byou are now\b|"
            r"\b(?:voce|you|tu|sie|vous)\s+(?:agora\s+)?(?:e|is|eres|es|bist|etes)\s+"
            r"(?:o|a|the|un|um)?\s*(?:administrador|admin|root|sistema|system)\b|"
            r"\b(?:act as|aja como|finja que|pretend to be|developer mode|modo desenvolvedor|"
            r"jailbreak|dan mode)\b",
            re.DOTALL,
        ),
        "guardrail.role_change",
    ),
    (
        "exfiltration",
        SeverityLevel.HIGH,
        re.compile(
            r"\b(?:envie|enviar|send|upload|post|forward|compartilhe|compartilhar|exfiltre|"
            r"exfiltrate)\b.{0,80}?\b(?:dados|data|informacoes|information|cpf|cnpj|documento|"
            r"document|arquivo|file)\b.{0,80}?\b(?:para|to|for)\b",
            re.DOTALL,
        ),
        "guardrail.exfiltration",
    ),
    (
        "fake_system",
        SeverityLevel.HIGH,
        re.compile(r"<system>|</system>|\[inst\]|###\s*instruction\b|\bsystem\s*prompt\s*:"),
        "guardrail.fake_system",
    ),
)

_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
_URL_TRAILING = ".,;:!?)]}'\""

_SECRET_PATTERNS = frozenset(
    {"jwt", "bearer_token", "secret_assignment", "aws_access_key", "private_key"},
)
_PII_PATTERNS = frozenset({"cpf", "cnpj", "email", "phone"})

_SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 0,
    SeverityLevel.HIGH: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.LOW: 3,
    SeverityLevel.INFO: 4,
}


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    layer: str
    code: str
    severity: SeverityLevel
    rule_id: str
    message_key: str

    def __post_init__(self) -> None:
        if not self.layer.strip():
            raise ValueError("layer is required")
        if not self.code.strip():
            raise ValueError("code is required")
        if not self.rule_id.startswith("guardrail."):
            raise ValueError("rule_id must start with guardrail.")


@dataclass(frozen=True, slots=True)
class TextSanitization:
    text: str
    original_length: int
    removed_control: int
    removed_invisible: int
    replaced_homoglyphs: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class InputGuardResult:
    sanitized: TextSanitization
    findings: tuple[GuardrailFinding, ...] = ()
    classifier_version: str | None = None
    classifier_unavailable: bool = False

    @property
    def triggered(self) -> bool:
        return any(
            finding.severity in {SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM}
            for finding in self.findings
        )


@dataclass(frozen=True, slots=True)
class OutputGuardResult:
    text: str
    findings: tuple[GuardrailFinding, ...] = ()
    blocked: bool = False
    removed_urls: int = 0


@dataclass(frozen=True, slots=True)
class ToolAllowlist:
    allowed: frozenset[str] = field(default_factory=frozenset)

    def is_allowed(self, name: str) -> bool:
        stripped = name.strip()
        return bool(stripped) and stripped in self.allowed

    def denied(self, requested: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(name for name in requested if not self.is_allowed(name))


def sanitize_text(text: str, *, max_chars: int) -> TextSanitization:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    original_length = len(text)
    fullwidth = sum(1 for character in text if "\uff01" <= character <= "\uff5e")
    normalized = unicodedata.normalize("NFKC", text)
    cleaned: list[str] = []
    removed_control = 0
    removed_invisible = 0
    replaced_homoglyphs = fullwidth
    for character in normalized:
        if character in "\n\t":
            cleaned.append(character)
            continue
        category = unicodedata.category(character)
        if character in _INVISIBLE_CHARS or category == "Cf":
            removed_invisible += 1
            continue
        if category in {"Cc", "Cs", "Co", "Cn"}:
            removed_control += 1
            continue
        mapped = _HOMOGLYPHS.get(character, character)
        if mapped != character:
            replaced_homoglyphs += 1
        cleaned.append(mapped)
    result = "".join(cleaned)
    truncated = len(result) > max_chars
    return TextSanitization(
        text=result[:max_chars],
        original_length=original_length,
        removed_control=removed_control,
        removed_invisible=removed_invisible,
        replaced_homoglyphs=replaced_homoglyphs,
        truncated=truncated,
    )


def normalize_for_matching(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_marks.casefold().split())


def detect_injection_patterns(text: str) -> tuple[GuardrailFinding, ...]:
    normalized = normalize_for_matching(text)
    findings: list[GuardrailFinding] = []
    seen: set[str] = set()
    for code, severity, pattern, rule_id in _PATTERNS:
        if code in seen or pattern.search(normalized) is None:
            continue
        seen.add(code)
        findings.append(
            GuardrailFinding(
                layer=GUARDRAIL_LAYER_PATTERNS,
                code=code,
                severity=severity,
                rule_id=rule_id,
                message_key=rule_id,
            ),
        )
    return tuple(findings)


class InputGuardrailService:
    def __init__(
        self,
        *,
        max_chars: int,
        classifier: InjectionClassifierPort | None = None,
        threshold: float = 0.8,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self._max_chars = max_chars
        self._classifier = classifier
        self._threshold = threshold

    def inspect(self, text: str) -> InputGuardResult:
        sanitized = sanitize_text(text, max_chars=self._max_chars)
        findings: list[GuardrailFinding] = []
        if sanitized.removed_invisible:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_INPUT,
                    code="invisible_unicode",
                    severity=SeverityLevel.MEDIUM,
                    rule_id="guardrail.invisible_unicode",
                    message_key="guardrail.invisible_unicode",
                ),
            )
        if sanitized.replaced_homoglyphs:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_INPUT,
                    code="homoglyph",
                    severity=SeverityLevel.MEDIUM,
                    rule_id="guardrail.homoglyph",
                    message_key="guardrail.homoglyph",
                ),
            )
        if sanitized.truncated:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_INPUT,
                    code="input_truncated",
                    severity=SeverityLevel.LOW,
                    rule_id="guardrail.input_truncated",
                    message_key="guardrail.input_truncated",
                ),
            )
        findings.extend(detect_injection_patterns(sanitized.text))
        classifier_version: str | None = None
        classifier_unavailable = False
        if self._classifier is not None:
            if not self._classifier.available:
                classifier_unavailable = True
            else:
                try:
                    score = self._max_classifier_score(sanitized.text)
                except Exception:
                    classifier_unavailable = True
                else:
                    classifier_version = self._classifier.model_version
                    if score >= self._threshold:
                        findings.append(
                            GuardrailFinding(
                                layer=GUARDRAIL_LAYER_CLASSIFIER,
                                code="classifier_injection",
                                severity=SeverityLevel.HIGH,
                                rule_id="guardrail.classifier_injection",
                                message_key="guardrail.classifier_injection",
                            ),
                        )
        unique = dedupe_findings(findings)
        return InputGuardResult(
            sanitized=sanitized,
            findings=unique,
            classifier_version=classifier_version,
            classifier_unavailable=classifier_unavailable,
        )

    def _max_classifier_score(self, text: str) -> float:
        if self._classifier is None:
            return 0.0
        segments = [line.strip() for line in text.splitlines() if line.strip()]
        if not segments:
            return self._classifier.score(text)
        scores = [self._classifier.score(segment[:2000]) for segment in segments[:200]]
        return max(scores)


class OutputGuardrailService:
    def __init__(self, *, allowed_urls: frozenset[str] = frozenset()) -> None:
        self._allowed_urls = allowed_urls

    def inspect(
        self,
        text: str,
        *,
        sensitive_terms: tuple[str, ...] = (),
    ) -> OutputGuardResult:
        findings: list[GuardrailFinding] = []
        detected = set(find_sensitive_patterns(text))
        pii = bool(detected & _PII_PATTERNS) or contains_sensitive_term(text, sensitive_terms)
        secret = bool(detected & _SECRET_PATTERNS)
        if pii:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_OUTPUT,
                    code="output_pii",
                    severity=SeverityLevel.CRITICAL,
                    rule_id="guardrail.output_pii",
                    message_key="guardrail.output_pii",
                ),
            )
        if secret:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_OUTPUT,
                    code="output_secret",
                    severity=SeverityLevel.CRITICAL,
                    rule_id="guardrail.output_secret",
                    message_key="guardrail.output_secret",
                ),
            )
        cleaned, removed_urls = self._strip_urls(text)
        if removed_urls:
            findings.append(
                GuardrailFinding(
                    layer=GUARDRAIL_LAYER_OUTPUT,
                    code="output_url",
                    severity=SeverityLevel.LOW,
                    rule_id="guardrail.output_url",
                    message_key="guardrail.output_url",
                ),
            )
        return OutputGuardResult(
            text=cleaned,
            findings=tuple(findings),
            blocked=pii or secret,
            removed_urls=removed_urls,
        )

    def _strip_urls(self, text: str) -> tuple[str, int]:
        removed = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal removed
            raw = match.group(0)
            url = raw.rstrip(_URL_TRAILING)
            trailing = raw[len(url) :]
            if any(
                url == allowed or url.startswith(f"{allowed.rstrip('/')}/")
                for allowed in self._allowed_urls
            ):
                return raw
            removed += 1
            return f"[REMOVED_URL]{trailing}"

        return _URL_RE.sub(replace, text), removed


def findings_to_evidence(
    findings: tuple[GuardrailFinding, ...],
) -> tuple[AnalysisEvidence, ...]:
    evidence: list[AnalysisEvidence] = []
    seen: set[str] = set()
    for finding in findings:
        if finding.rule_id in seen:
            continue
        seen.add(finding.rule_id)
        evidence.append(
            AnalysisEvidence(
                rule_id=finding.rule_id,
                severity=finding.severity.value,
                weight=0,
                message_key=finding.message_key,
                source=GUARDRAIL_RULE_SET_VERSION,
            ),
        )
    return tuple(evidence[:12])


def dedupe_findings(findings: list[GuardrailFinding]) -> tuple[GuardrailFinding, ...]:
    unique: list[GuardrailFinding] = []
    seen: set[tuple[str, str]] = set()
    for finding in sorted(findings, key=lambda item: _SEVERITY_ORDER[item.severity]):
        key = (finding.layer, finding.code)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return tuple(unique)
