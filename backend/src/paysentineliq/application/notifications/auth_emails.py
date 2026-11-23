from dataclasses import dataclass
from html import escape
from typing import Literal

AuthEmailKind = Literal[
    "verify_email",
    "email_already_registered",
    "password_reset",
    "password_changed",
    "google_account_reset",
]

_SUBJECTS: dict[str, dict[AuthEmailKind, str]] = {
    "pt": {
        "verify_email": "Confirme seu e-mail no SentinelPay",
        "email_already_registered": "Tentativa de cadastro no SentinelPay",
        "password_reset": "Redefinição de senha no SentinelPay",
        "password_changed": "Sua senha foi alterada",
        "google_account_reset": "Sua conta SentinelPay usa o Google",
    },
    "en": {
        "verify_email": "Confirm your e-mail at SentinelPay",
        "email_already_registered": "Sign-up attempt at SentinelPay",
        "password_reset": "Password reset at SentinelPay",
        "password_changed": "Your password was changed",
        "google_account_reset": "Your SentinelPay account uses Google",
    },
    "es": {
        "verify_email": "Confirma tu correo en SentinelPay",
        "email_already_registered": "Intento de registro en SentinelPay",
        "password_reset": "Restablecimiento de contraseña en SentinelPay",
        "password_changed": "Tu contraseña fue cambiada",
        "google_account_reset": "Tu cuenta SentinelPay usa Google",
    },
}

_PARAGRAPHS: dict[str, dict[AuthEmailKind, tuple[str, ...]]] = {
    "pt": {
        "verify_email": (
            "Recebemos um cadastro com este e-mail.",
            "Confirme seu endereço para ativar a conta. O link expira em 24 horas.",
        ),
        "email_already_registered": (
            "Alguém tentou criar uma conta no SentinelPay com este e-mail, "
            "mas ele já está cadastrado.",
            "Se foi você, entre com sua senha ou use o Google. "
            "Se esqueceu a senha, solicite a redefinição.",
        ),
        "password_reset": (
            "Recebemos um pedido para redefinir sua senha.",
            "O link abaixo expira em {minutes} minutos e só pode ser usado uma vez.",
        ),
        "password_changed": (
            "Sua senha foi alterada e todas as sessões ativas foram encerradas.",
            "Se não foi você, solicite a redefinição de senha imediatamente.",
        ),
        "google_account_reset": (
            "Sua conta no SentinelPay foi criada com o Google, então não existe senha local.",
            "Continue entrando com o Google. Se quiser, solicite a redefinição "
            "para cadastrar uma senha.",
        ),
    },
    "en": {
        "verify_email": (
            "We received a sign-up with this e-mail.",
            "Confirm your address to activate the account. The link expires in 24 hours.",
        ),
        "email_already_registered": (
            "Someone tried to create a SentinelPay account with this e-mail, "
            "but it is already registered.",
            "If this was you, sign in with your password or Google. "
            "If you forgot it, request a reset.",
        ),
        "password_reset": (
            "We received a request to reset your password.",
            "The link below expires in {minutes} minutes and can be used once.",
        ),
        "password_changed": (
            "Your password was changed and all active sessions were signed out.",
            "If this was not you, reset your password immediately.",
        ),
        "google_account_reset": (
            "Your SentinelPay account was created with Google, so there is no local password.",
            "Keep signing in with Google. If you want, request a reset to create a password.",
        ),
    },
    "es": {
        "verify_email": (
            "Recibimos un registro con este correo.",
            "Confirma tu dirección para activar la cuenta. El enlace expira en 24 horas.",
        ),
        "email_already_registered": (
            "Alguien intentó crear una cuenta de SentinelPay con este correo, "
            "pero ya está registrado.",
            "Si fuiste tú, entra con tu contraseña o Google. "
            "Si la olvidaste, solicita el restablecimiento.",
        ),
        "password_reset": (
            "Recibimos una solicitud para restablecer tu contraseña.",
            "El enlace expira en {minutes} minutos y solo se puede usar una vez.",
        ),
        "password_changed": (
            "Tu contraseña fue cambiada y todas las sesiones activas se cerraron.",
            "Si no fuiste tú, restablece la contraseña de inmediato.",
        ),
        "google_account_reset": (
            "Tu cuenta de SentinelPay fue creada con Google, "
            "por lo que no existe una contraseña local.",
            "Sigue entrando con Google. Si quieres, solicita el restablecimiento "
            "para crear una contraseña.",
        ),
    },
}

_CTA_LABEL: dict[str, dict[AuthEmailKind, str]] = {
    "pt": {
        "verify_email": "Confirmar e-mail",
        "email_already_registered": "Entrar no SentinelPay",
        "password_reset": "Redefinir senha",
        "password_changed": "Entrar no SentinelPay",
        "google_account_reset": "Entrar no SentinelPay",
    },
    "en": {
        "verify_email": "Confirm e-mail",
        "email_already_registered": "Sign in to SentinelPay",
        "password_reset": "Reset password",
        "password_changed": "Sign in to SentinelPay",
        "google_account_reset": "Sign in to SentinelPay",
    },
    "es": {
        "verify_email": "Confirmar correo",
        "email_already_registered": "Entrar en SentinelPay",
        "password_reset": "Restablecer contraseña",
        "password_changed": "Entrar en SentinelPay",
        "google_account_reset": "Entrar en SentinelPay",
    },
}

_TEXT_CTA: dict[str, dict[AuthEmailKind, str]] = {
    "pt": {
        "verify_email": "Confirme seu e-mail:",
        "email_already_registered": "Acesse sua conta:",
        "password_reset": "Redefina sua senha:",
        "password_changed": "Acesse sua conta:",
        "google_account_reset": "Acesse sua conta:",
    },
    "en": {
        "verify_email": "Confirm your e-mail:",
        "email_already_registered": "Open your account:",
        "password_reset": "Reset your password:",
        "password_changed": "Open your account:",
        "google_account_reset": "Open your account:",
    },
    "es": {
        "verify_email": "Confirma tu correo:",
        "email_already_registered": "Abre tu cuenta:",
        "password_reset": "Restablece tu contraseña:",
        "password_changed": "Abre tu cuenta:",
        "google_account_reset": "Abre tu cuenta:",
    },
}

_FOOTER: dict[str, str] = {
    "pt": "Se você não reconhece esta mensagem, ignore este e-mail.",
    "en": "If you do not recognize this message, ignore this e-mail.",
    "es": "Si no reconoces este mensaje, ignora este correo.",
}


@dataclass(frozen=True, slots=True)
class AuthEmail:
    kind: AuthEmailKind
    to: str
    subject: str
    text_body: str
    html_body: str


def resolve_email_locale(locale: str | None) -> str:
    normalized = (locale or "pt").strip().lower()
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("es"):
        return "es"
    return "pt"


def _layout(
    title: str,
    paragraphs: tuple[str, ...],
    footer: str,
    cta_label: str,
    cta_url: str,
) -> str:
    body_parts = "".join(
        f'<p style="margin:0 0 16px;color:#1b2421;font-size:15px;line-height:1.6">'
        f"{escape(paragraph)}</p>"
        for paragraph in paragraphs
    )
    cta = (
        '<p style="margin:24px 0 0">'
        f'<a href="{escape(cta_url)}" '
        'style="display:inline-block;background:#0f5c5a;color:#f1f5f2;'
        'padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:600">'
        f"{escape(cta_label)}</a></p>"
    )
    return (
        '<!doctype html><html><body style="margin:0;background:#f4f1ea;'
        'padding:32px 16px;font-family:Arial,Helvetica,sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border:1px solid #e2ddd2;'
        'border-radius:8px">'
        '<tr><td style="padding:28px 28px 8px">'
        '<div style="font-family:Georgia,serif;font-size:22px;color:#0f4138">'
        "SentinelPay</div>"
        f'<h1 style="margin:20px 0 16px;font-family:Georgia,serif;font-size:26px;'
        f'color:#13201b">{escape(title)}</h1>'
        f"{body_parts}{cta}"
        '<p style="margin:28px 0 0;padding-top:16px;border-top:1px solid #e2ddd2;'
        'color:#5c6469;font-size:12px;line-height:1.6">'
        f"{escape(footer)}</p>"
        "</td></tr></table></td></tr></table></body></html>"
    )


def render_auth_email(
    *,
    kind: AuthEmailKind,
    to: str,
    locale: str | None,
    link: str | None = None,
    token_minutes: int | None = None,
) -> AuthEmail:
    resolved = resolve_email_locale(locale)
    subject = _SUBJECTS[resolved][kind]
    footer = _FOOTER[resolved]
    minutes = token_minutes or 30
    paragraphs = tuple(
        paragraph.format(minutes=minutes) for paragraph in _PARAGRAPHS[resolved][kind]
    )
    cta_label = _CTA_LABEL[resolved][kind]
    text_cta = _TEXT_CTA[resolved][kind]

    text_lines = [subject, "", *paragraphs]
    if link:
        text_lines.extend(["", text_cta, link])
    text_lines.extend(["", footer])

    return AuthEmail(
        kind=kind,
        to=to,
        subject=subject,
        text_body="\n".join(text_lines),
        html_body=_layout(subject, paragraphs, footer, cta_label, link or ""),
    )
