from dataclasses import dataclass
from enum import StrEnum

from paysentineliq.domain.notification import NotificationType


@dataclass(frozen=True, slots=True)
class NotificationTemplate:
    subject: str
    body: str


class _Locale(StrEnum):
    PT_BR = "pt-BR"
    EN = "en"
    FR = "fr"
    JA = "ja"
    ES = "es"
    DE = "de"
    AR = "ar"
    KO = "ko"
    ZH = "zh"


_T = NotificationType
_TEMPLATES: dict[_Locale, dict[NotificationType, NotificationTemplate]] = {
    _Locale.PT_BR: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "Análise concluída",
            "Sua análise foi concluída. Abra o app para ver o resultado.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "Risco alto detectado",
            "Um documento analisado apresenta risco alto. Abra o app para ver os detalhes.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "Recibo analisado",
            "Seu recibo foi analisado. Abra o app para ver os detalhes.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "Conta a vencer",
            "Uma conta vence em {days} dia(s). Abra o app para ver os detalhes.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "Conta vence hoje",
            "Uma conta vence hoje. Abra o app para ver os detalhes.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "Conta vencida",
            "Uma conta está vencida. Abra o app para ver os detalhes.",
        ),
    },
    _Locale.EN: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "Analysis completed",
            "Your analysis is complete. Open the app to see the result.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "High risk detected",
            "A document you analyzed shows high risk. Open the app for details.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "Receipt analyzed",
            "Your receipt was analyzed. Open the app for details.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "Bill due soon",
            "A bill is due in {days} day(s). Open the app for details.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "Bill due today",
            "A bill is due today. Open the app for details.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "Bill overdue",
            "A bill is overdue. Open the app for details.",
        ),
    },
    _Locale.FR: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "Analyse terminée",
            "Votre analyse est terminée. Ouvrez l'application pour voir le résultat.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "Risque élevé détecté",
            "Un document analysé présente un risque élevé. Ouvrez l'application pour les détails.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "Reçu analysé",
            "Votre reçu a été analysé. Ouvrez l'application pour les détails.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "Facture à échéance",
            "Une facture arrive à échéance dans {days} jour(s). Ouvrez l'application.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "Facture due aujourd'hui",
            "Une facture arrive à échéance aujourd'hui. Ouvrez l'application.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "Facture en retard",
            "Une facture est en retard. Ouvrez l'application pour les détails.",
        ),
    },
    _Locale.JA: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "分析が完了しました",
            "分析が完了しました。アプリを開いて結果を確認してください。",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "高リスクを検出",
            "分析した書類に高リスクが検出されました。アプリを開いて詳細を確認してください。",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "領収書を分析しました",
            "領収書を分析しました。アプリを開いて詳細を確認してください。",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "支払期限が近づいています",
            "請求書の支払期限まであと{days}日です。アプリを開いて確認してください。",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "本日が支払期限です",
            "本日が支払期限の請求書があります。アプリを開いて確認してください。",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "支払期限を過ぎています",
            "支払期限を過ぎた請求書があります。アプリを開いて確認してください。",
        ),
    },
    _Locale.ES: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "Análisis completado",
            "Tu análisis ha finalizado. Abre la app para ver el resultado.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "Riesgo alto detectado",
            "Un documento analizado presenta riesgo alto. Abre la app para ver los detalles.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "Recibo analizado",
            "Tu recibo fue analizado. Abre la app para ver los detalles.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "Factura por vencer",
            "Una factura vence en {days} día(s). Abre la app para ver los detalles.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "Factura vence hoy",
            "Una factura vence hoy. Abre la app para ver los detalles.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "Factura vencida",
            "Una factura está vencida. Abre la app para ver los detalles.",
        ),
    },
    _Locale.DE: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "Analyse abgeschlossen",
            "Ihre Analyse ist abgeschlossen. Öffnen Sie die App, um das Ergebnis zu sehen.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "Hohes Risiko erkannt",
            "Ein analysiertes Dokument weist ein hohes Risiko auf. Öffnen Sie die App für Details.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "Beleg analysiert",
            "Ihr Beleg wurde analysiert. Öffnen Sie die App für Details.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "Rechnung fällig",
            "Eine Rechnung ist in {days} Tag(en) fällig. Öffnen Sie die App für Details.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "Rechnung heute fällig",
            "Eine Rechnung ist heute fällig. Öffnen Sie die App für Details.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "Rechnung überfällig",
            "Eine Rechnung ist überfällig. Öffnen Sie die App für Details.",
        ),
    },
    _Locale.AR: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "اكتمل التحليل",
            "اكتمل تحليل المستند. افتح التطبيق لعرض النتيجة.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "تم اكتشاف خطر مرتفع",
            "أظهر مستند تم تحليله خطرًا مرتفعًا. افتح التطبيق لعرض التفاصيل.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "تم تحليل الإيصال",
            "تم تحليل الإيصال. افتح التطبيق لعرض التفاصيل.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "فاتورة تستحق قريبًا",
            "تستحق فاتورة خلال {days} يوم. افتح التطبيق لعرض التفاصيل.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "فاتورة تستحق اليوم",
            "تستحق فاتورة اليوم. افتح التطبيق لعرض التفاصيل.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "فاتورة متأخرة",
            "هناك فاتورة متأخرة. افتح التطبيق لعرض التفاصيل.",
        ),
    },
    _Locale.KO: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "분석 완료",
            "분석이 완료되었습니다. 앱을 열어 결과를 확인하세요.",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "높은 위험 감지",
            "분석한 문서에서 높은 위험이 감지되었습니다. 앱을 열어 자세히 확인하세요.",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "영수증 분석 완료",
            "영수증이 분석되었습니다. 앱을 열어 자세히 확인하세요.",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "납부 기한 임박",
            "청구서 납부 기한이 {days}일 남았습니다. 앱을 열어 확인하세요.",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "오늘 납부 기한",
            "오늘 납부 기한인 청구서가 있습니다. 앱을 열어 확인하세요.",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "납부 기한 경과",
            "납부 기한이 지난 청구서가 있습니다. 앱을 열어 확인하세요.",
        ),
    },
    _Locale.ZH: {
        _T.ANALYSIS_COMPLETED: NotificationTemplate(
            "分析完成",
            "您的分析已完成。请打开应用查看结果。",
        ),
        _T.HIGH_RISK_DETECTED: NotificationTemplate(
            "检测到高风险",
            "已分析的文档存在高风险。请打开应用查看详情。",
        ),
        _T.RECEIPT_ANALYZED: NotificationTemplate(
            "收据已分析",
            "您的收据已分析。请打开应用查看详情。",
        ),
        _T.PAYABLE_DUE_SOON: NotificationTemplate(
            "账单即将到期",
            "有一张账单将在 {days} 天后到期。请打开应用查看详情。",
        ),
        _T.PAYABLE_DUE_TODAY: NotificationTemplate(
            "账单今天到期",
            "有一张账单今天到期。请打开应用查看详情。",
        ),
        _T.PAYABLE_OVERDUE: NotificationTemplate(
            "账单已逾期",
            "有一张账单已逾期。请打开应用查看详情。",
        ),
    },
}


def normalize_locale(locale: str) -> str:
    primary = locale.strip().lower().split("-", 1)[0]
    if primary == "pt":
        return _Locale.PT_BR.value
    if primary in {item.value for item in _Locale}:
        return primary
    return _Locale.EN.value


def render_notification(
    *,
    locale: str,
    notification_type: NotificationType,
    days: int | None = None,
) -> NotificationTemplate:
    resolved = _Locale(normalize_locale(locale))
    effective_type = notification_type
    if notification_type is _T.PAYABLE_DUE_REMINDER:
        effective_type = (
            _T.PAYABLE_DUE_TODAY if days is not None and days <= 0 else _T.PAYABLE_DUE_SOON
        )
    template = _TEMPLATES[resolved][effective_type]
    if effective_type is _T.PAYABLE_DUE_SOON:
        safe_days = days if days is not None and days > 0 else 1
        return NotificationTemplate(
            subject=template.subject,
            body=template.body.format(days=safe_days),
        )
    return template
