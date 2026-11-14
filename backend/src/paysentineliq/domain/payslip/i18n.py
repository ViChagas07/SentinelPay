SUPPORTED_LOCALES = ("pt", "es", "en")

MESSAGES: dict[str, dict[str, str]] = {
    "payslip.earnings_total_mismatch": {
        "pt": "A soma dos proventos nao confere com o total de proventos.",
        "es": "La suma de los haberes no coincide con el total de haberes.",
        "en": "Earnings do not add up to the declared earnings total.",
    },
    "payslip.deductions_total_mismatch": {
        "pt": "A soma dos descontos nao confere com o total de descontos.",
        "es": "La suma de los descuentos no coincide con el total de descuentos.",
        "en": "Deductions do not add up to the declared deductions total.",
    },
    "payslip.net_mismatch": {
        "pt": "O liquido nao e igual a proventos menos descontos.",
        "es": "El neto no es igual a haberes menos descuentos.",
        "en": "Net pay does not equal earnings minus deductions.",
    },
    "payslip.net_exceeds_earnings": {
        "pt": "O liquido e maior que os proventos, o que e matematicamente impossivel.",
        "es": "El neto es mayor que los haberes, lo que es matematicamente imposible.",
        "en": "Net pay is greater than earnings, which is mathematically impossible.",
    },
    "payslip.inss_mismatch": {
        "pt": "O desconto de INSS nao corresponde a tabela da competencia.",
        "es": "El descuento de INSS no corresponde a la tabla de la competencia.",
        "en": "INSS deduction does not match the table for the competency.",
    },
    "payslip.irrf_mismatch": {
        "pt": "O desconto de IRRF nao corresponde a tabela da competencia.",
        "es": "El descuento de IRRF no corresponde a la tabla de la competencia.",
        "en": "IRRF deduction does not match the table for the competency.",
    },
    "payslip.base_below_minimum": {
        "pt": "O salario base esta abaixo do minimo vigente.",
        "es": "El salario base esta por debajo del minimo vigente.",
        "en": "Base salary is below the applicable minimum wage.",
    },
    "payslip.overtime_below_minimum": {
        "pt": "O adicional de horas extras esta abaixo do minimo da fonte.",
        "es": "El adicional de horas extras esta por debajo del minimo de la fuente.",
        "en": "Overtime premium is below the minimum stated in the source.",
    },
    "payslip.competency_implausible": {
        "pt": "A competencia e invalida ou esta no futuro.",
        "es": "La competencia es invalida o esta en el futuro.",
        "en": "Competency is invalid or in the future.",
    },
    "payslip.employer_cnpj_invalid": {
        "pt": "O CNPJ do empregador tem digitos verificadores invalidos.",
        "es": "El CNPJ del empleador tiene digitos verificadores invalidos.",
        "en": "Employer CNPJ has invalid check digits.",
    },
    "payslip.employee_cpf_invalid": {
        "pt": "O CPF do funcionario tem digitos verificadores invalidos.",
        "es": "El CPF del empleado tiene digitos verificadores invalidos.",
        "en": "Employee CPF has invalid check digits.",
    },
    "payslip.duplicate_item": {
        "pt": "Ha itens duplicados no contracheque.",
        "es": "Hay items duplicados en la nomina.",
        "en": "There are duplicate items in the payslip.",
    },
    "payslip.rounding_incoherent": {
        "pt": "Ha valores monetarios com arredondamento incoerente.",
        "es": "Hay valores monetarios con redondeo incoherente.",
        "en": "There are monetary values with inconsistent rounding.",
    },
    "payslip.field_illegible": {
        "pt": "Campos obrigatorios estao ausentes, ilegiveis ou com baixa confianca.",
        "es": "Campos obligatorios estan ausentes, ilegibles o con baja confianza.",
        "en": "Required fields are missing, illegible or have low confidence.",
    },
    "payslip.not_verifiable": {
        "pt": "Regra nao verificavel com os dados regulatorios disponiveis.",
        "es": "Regla no verificable con los datos regulatorios disponibles.",
        "en": "Rule not verifiable with the available regulatory data.",
    },
}

LABELS: dict[str, dict[str, str]] = {
    "employer": {"pt": "Empregador", "es": "Empleador", "en": "Employer"},
    "employee": {"pt": "Funcionario", "es": "Empleado", "en": "Employee"},
    "cpf": {"pt": "CPF", "es": "CPF", "en": "CPF"},
    "cnpj": {"pt": "CNPJ", "es": "CNPJ", "en": "CNPJ"},
    "competency": {"pt": "Competencia", "es": "Competencia", "en": "Competency"},
    "earnings": {"pt": "Proventos", "es": "Haberes", "en": "Earnings"},
    "deductions": {"pt": "Descontos", "es": "Descuentos", "en": "Deductions"},
    "net": {"pt": "Liquido", "es": "Neto", "en": "Net pay"},
    "inss": {"pt": "INSS", "es": "INSS", "en": "INSS"},
    "irrf": {"pt": "IRRF", "es": "IRRF", "en": "IRRF"},
    "base_salary": {"pt": "Salario base", "es": "Salario base", "en": "Base salary"},
    "overtime": {"pt": "Horas extras", "es": "Horas extras", "en": "Overtime"},
    "not_verifiable": {
        "pt": "Nao verificavel",
        "es": "No verificable",
        "en": "Not verifiable",
    },
}


def translate(key: str, locale: str) -> str:
    translations = MESSAGES[key]
    return translations.get(locale, translations["pt"])
