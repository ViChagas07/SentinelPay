import type { PasswordPolicy } from "@/lib/auth/capabilities";

export type PasswordIssue = "too_short" | "too_long" | "too_common" | "contains_identifier";

export type PasswordStrength = "weak" | "fair" | "good" | "strong";

const COMMON_PASSWORDS = new Set([
  "1234567890",
  "123456789",
  "12345678",
  "123456",
  "password",
  "password1",
  "password123",
  "senha123",
  "senha1234",
  "senha12345",
  "senhaforte",
  "senhasegura",
  "admin123",
  "admin1234",
  "qwerty",
  "qwerty123",
  "qwertyuiop",
  "1q2w3e4r",
  "1qaz2wsx",
  "asdfghjkl",
  "asdf1234",
  "brasil123",
  "familia123",
  "felicidade",
  "meuamor123",
  "teste12345",
  "teste1234",
  "teste123",
  "temporary",
  "changeme",
  "mudar123",
  "acesso123",
  "conta1234",
  "usuario123",
  "usuario1234",
]);

export function normalizeIdentifier(value: string | null | undefined): string[] {
  if (!value) {
    return [];
  }

  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((part) => part.length >= 4);
}

export function passwordIssues(
  password: string,
  policy: PasswordPolicy,
  identifiers: readonly string[] = [],
): PasswordIssue[] {
  const issues: PasswordIssue[] = [];

  if (password.length < policy.minLength) {
    issues.push("too_short");
  }

  if (password.length > policy.maxLength) {
    issues.push("too_long");
  }

  const compact = password
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, "");

  if (COMMON_PASSWORDS.has(compact)) {
    issues.push("too_common");
  }

  if (identifiers.some((identifier) => compact.includes(identifier))) {
    issues.push("contains_identifier");
  }

  return issues;
}

export function passwordStrength(password: string, policy: PasswordPolicy): PasswordStrength {
  if (password.length === 0) {
    return "weak";
  }

  const classes =
    Number(/[a-z]/.test(password)) +
    Number(/[A-Z]/.test(password)) +
    Number(/\d/.test(password)) +
    Number(/[^A-Za-z0-9]/.test(password));
  const longEnough = password.length >= policy.minLength;
  const generous = password.length >= policy.minLength + 6;
  const commonSet = COMMON_PASSWORDS.has(password.toLowerCase().replace(/\s+/g, ""));

  if (commonSet) {
    return "weak";
  }

  if (!longEnough) {
    return password.length >= Math.max(6, policy.minLength - 4) ? "fair" : "weak";
  }

  if (password.length >= policy.minLength + 12 || (generous && classes >= 3)) {
    return "strong";
  }

  if (generous || classes >= 3) {
    return "good";
  }

  return "fair";
}

export function identifierFragments(email: string, name: string): string[] {
  return [...normalizeIdentifier(email.split("@", 1)[0]), ...normalizeIdentifier(name)];
}
