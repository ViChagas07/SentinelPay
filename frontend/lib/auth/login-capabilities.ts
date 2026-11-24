import { fetchAuthCapabilities, fetchPasswordPolicy } from "@/lib/auth/capabilities";

export type LoginPageCapabilities = {
  passwordEnabled: boolean;
  signupEnabled: boolean;
  passwordResetEnabled: boolean;
  googleEnabled: boolean;
  policy: Awaited<ReturnType<typeof fetchPasswordPolicy>> | null;
};

export async function loadLoginCapabilities(): Promise<LoginPageCapabilities> {
  const [capabilities, policy] = await Promise.all([
    fetchAuthCapabilities(),
    fetchPasswordPolicy(),
  ]);

  return {
    passwordEnabled: capabilities.passwordEnabled,
    signupEnabled: capabilities.signupEnabled,
    passwordResetEnabled: capabilities.passwordResetEnabled,
    googleEnabled: capabilities.googleEnabled,
    policy: capabilities.passwordEnabled ? policy : null,
  };
}
