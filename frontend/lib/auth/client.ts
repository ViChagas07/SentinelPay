import {
  emailRequestSchema,
  emailSchema,
  passwordLoginSchema,
  registerSchema,
  resetPasswordSchema,
  verifyEmailSchema,
} from "@/lib/auth/schemas";
import { authErrorKey, parseAuthProblem, readRetryAfter } from "@/lib/auth/errors";

export type AuthRequestResult =
  | { ok: true }
  | {
      ok: false;
      code: string;
      messageKey: ReturnType<typeof authErrorKey>;
      retryAfter: number | null;
    };

async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
}

async function interpret(response: Response): Promise<AuthRequestResult> {
  if (response.ok) {
    await response.body?.cancel().catch(() => undefined);
    return { ok: true };
  }

  const payload: unknown = await response.json().catch(() => null);
  const problem = parseAuthProblem(payload, response.status);
  const retryAfter = problem.retryAfterSeconds ?? readRetryAfter(response);

  return {
    ok: false,
    code: problem.code,
    messageKey: authErrorKey(problem.code),
    retryAfter,
  };
}

export async function requestPasswordLogin(input: {
  email: string;
  password: string;
}): Promise<AuthRequestResult> {
  const parsed = passwordLoginSchema.safeParse({ email: input.email, senha: input.password });

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_request",
      messageKey: authErrorKey("invalid_request"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/login", parsed.data).catch(() => null);

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}

export async function requestRegister(input: {
  name: string;
  email: string;
  password: string;
  acceptedTerms: boolean;
  acceptedPrivacy: boolean;
}): Promise<AuthRequestResult> {
  const parsed = registerSchema.safeParse({
    nome_completo: input.name,
    email: input.email,
    senha: input.password,
    aceite_termos: input.acceptedTerms,
    aceite_privacidade: input.acceptedPrivacy,
  });

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_request",
      messageKey: authErrorKey("invalid_request"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/register", parsed.data).catch(() => null);

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}

export async function requestEmailVerification(token: string): Promise<AuthRequestResult> {
  const parsed = verifyEmailSchema.safeParse({ token });

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_auth_token",
      messageKey: authErrorKey("invalid_auth_token"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/verify-email", parsed.data).catch(() => null);

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}

export async function requestVerificationResend(email: string): Promise<AuthRequestResult> {
  const parsed = emailRequestSchema.safeParse({ email });

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_request",
      messageKey: authErrorKey("invalid_request"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/resend-verification", parsed.data).catch(
    () => null,
  );

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}

export async function requestPasswordForgot(email: string): Promise<AuthRequestResult> {
  const parsed = emailSchema.safeParse(email);

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_request",
      messageKey: authErrorKey("invalid_request"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/forgot-password", {
    email: parsed.data,
  }).catch(() => null);

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}

export async function requestPasswordReset(input: {
  token: string;
  password: string;
}): Promise<AuthRequestResult> {
  const parsed = resetPasswordSchema.safeParse({
    token: input.token,
    nova_senha: input.password,
  });

  if (!parsed.success) {
    return {
      ok: false,
      code: "invalid_auth_token",
      messageKey: authErrorKey("invalid_auth_token"),
      retryAfter: null,
    };
  }

  const response = await postJson("/api/v1/auth/reset-password", parsed.data).catch(() => null);

  if (response === null) {
    return {
      ok: false,
      code: "network_error",
      messageKey: authErrorKey("network_error"),
      retryAfter: null,
    };
  }

  return interpret(response);
}
