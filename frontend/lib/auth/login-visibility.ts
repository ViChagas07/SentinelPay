import { LOGIN_MODES, type LoginMode } from "./login-mode";

export type LoginVisibilityInput = {
  passwordEnabled: boolean;
  signupEnabled: boolean;
  policyAvailable: boolean;
  requestedMode: LoginMode;
};

export type LoginVisibility = {
  formsEnabled: boolean;
  tabsVisible: boolean;
  availableModes: readonly LoginMode[];
  mode: LoginMode;
  emailSignupAvailable: boolean;
  passwordFieldsVisible: boolean;
};

export function resolveLoginVisibility({
  passwordEnabled,
  signupEnabled,
  policyAvailable,
  requestedMode,
}: LoginVisibilityInput): LoginVisibility {
  const formsEnabled = passwordEnabled && policyAvailable;
  const tabsVisible = formsEnabled;
  const availableModes: readonly LoginMode[] = tabsVisible ? LOGIN_MODES : (["signin"] as const);
  const mode: LoginMode = availableModes.includes(requestedMode) ? requestedMode : "signin";
  const emailSignupAvailable = formsEnabled && signupEnabled;

  return {
    formsEnabled,
    tabsVisible,
    availableModes,
    mode,
    emailSignupAvailable,
    passwordFieldsVisible: formsEnabled && (mode === "signin" || emailSignupAvailable),
  };
}
