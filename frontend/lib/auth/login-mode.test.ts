import { describe, expect, it } from "vitest";

import { buildLoginModeUrl, parseLoginMode } from "./login-mode";

describe("parseLoginMode", () => {
  it("opens the sign-in tab by default", () => {
    expect(parseLoginMode(undefined)).toBe("signin");
    expect(parseLoginMode(null)).toBe("signin");
    expect(parseLoginMode("")).toBe("signin");
    expect(parseLoginMode("entrar")).toBe("signin");
  });

  it("opens the sign-up tab only for the documented value", () => {
    expect(parseLoginMode("cadastro")).toBe("signup");
    expect(parseLoginMode("CADASTRO")).toBe("signin");
    expect(parseLoginMode("signup")).toBe("signin");
  });
});

describe("buildLoginModeUrl", () => {
  it("adds the sign-up parameter and keeps the other query values", () => {
    expect(
      buildLoginModeUrl(
        { pathname: "/login", search: "?next=%2Fpainel&reason=expired", hash: "" },
        "signup",
      ),
    ).toBe("/login?next=%2Fpainel&reason=expired&modo=cadastro");
  });

  it("removes the sign-up parameter when returning to sign in", () => {
    expect(
      buildLoginModeUrl(
        { pathname: "/login", search: "?modo=cadastro&next=%2Fboletos", hash: "" },
        "signin",
      ),
    ).toBe("/login?next=%2Fboletos");
  });

  it("keeps a clean path and the hash when there is nothing else to preserve", () => {
    expect(buildLoginModeUrl({ pathname: "/login", search: "", hash: "" }, "signin")).toBe(
      "/login",
    );
    expect(buildLoginModeUrl({ pathname: "/login", search: "", hash: "#acesso" }, "signin")).toBe(
      "/login#acesso",
    );
  });
});
