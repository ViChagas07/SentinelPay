from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SyntheticPayslip:
    employer_name: str = "PAGAMENTOS SINTETICOS LTDA"
    employer_cnpj: str = "11.222.333/0001-81"
    employee_name: str = "CLIENTE SINTETICO"
    employee_cpf: str = "123.456.789-09"
    competency: str = "05/2024"
    base_salary: str = "2.000,00"
    overtime_percent: str = "50%"
    overtime_amount: str = "100,00"
    total_earnings: str = "2.100,00"
    inss: str = "330,00"
    irrf: str = "77,00"
    total_deductions: str = "407,00"
    net: str = "1.693,00"
    irrf_base: str = "1.770,00"

    def ocr_text(self) -> str:
        return "\n".join(
            [
                f"EMPRESA: {self.employer_name}",
                f"CNPJ: {self.employer_cnpj}",
                f"FUNCIONARIO: {self.employee_name}",
                f"CPF: {self.employee_cpf}",
                f"COMPETENCIA: {self.competency}",
                "PROVENTOS",
                f"001 SALARIO BASE {self.base_salary}",
                f"002 HORAS EXTRAS {self.overtime_percent} {self.overtime_amount}",
                f"TOTAL PROVENTOS {self.total_earnings}",
                "DESCONTOS",
                f"101 INSS {self.inss}",
                f"102 IRRF {self.irrf}",
                f"TOTAL DESCONTOS {self.total_deductions}",
                f"BASE IRRF {self.irrf_base}",
                f"LIQUIDO {self.net}",
            ],
        )
