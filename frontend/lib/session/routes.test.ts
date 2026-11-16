import { describe, expect, it } from "vitest";

import { decideAuthAction, getRouteKind, isSafeNextPath, resolveNextPath } from "./routes";

describe("getRouteKind", () => {
  it("classifies public routes, including nested paths", () => {
    expect(getRouteKind("/")).toBe("public");
    expect(getRouteKind("/login")).toBe("public");
    expect(getRouteKind("/termos")).toBe("public");
    expect(getRouteKind("/privacidade")).toBe("public");
    expect(getRouteKind("/termos/uso")).toBe("public");
  });

  it("classifies private routes, including nested paths", () => {
    expect(getRouteKind("/painel")).toBe("private");
    expect(getRouteKind("/painel/hoje")).toBe("private");
    expect(getRouteKind("/verificacao")).toBe("private");
    expect(getRouteKind("/boletos/123")).toBe("private");
    expect(getRouteKind("/account/seguranca")).toBe("private");
  });

  it("classifies route prefixes as private even when they only share a prefix substring", () => {
    expect(getRouteKind("/painelizado")).toBe("other");
    expect(getRouteKind("/boletosx")).toBe("other");
    expect(getRouteKind("/desconhecido")).toBe("other");
  });

  it("normalizes trailing slashes and missing leading slash", () => {
    expect(getRouteKind("/painel/")).toBe("private");
    expect(getRouteKind("painel")).toBe("private");
    expect(getRouteKind("")).toBe("public");
  });
});

describe("isSafeNextPath", () => {
  it("accepts private paths with query strings", () => {
    expect(isSafeNextPath("/painel")).toBe(true);
    expect(isSafeNextPath("/boletos?page=2")).toBe(true);
    expect(isSafeNextPath("/notificacoes?type=high_risk_detected")).toBe(true);
  });

  it("rejects external, protocol-relative and login destinations", () => {
    expect(isSafeNextPath("https://evil.example")).toBe(false);
    expect(isSafeNextPath("//evil.example")).toBe(false);
    expect(isSafeNextPath("/login")).toBe(false);
    expect(isSafeNextPath("/login?next=/painel")).toBe(false);
    expect(isSafeNextPath(null)).toBe(false);
    expect(isSafeNextPath("")).toBe(false);
  });

  it("rejects public and unknown destinations", () => {
    expect(isSafeNextPath("/")).toBe(false);
    expect(isSafeNextPath("/termos")).toBe(false);
    expect(isSafeNextPath("/desconhecido")).toBe(false);
  });

  it("rejects control characters and backslashes", () => {
    expect(isSafeNextPath("/painel\\..\\admin")).toBe(false);
    expect(isSafeNextPath("/painel\nSet-Cookie: x")).toBe(false);
  });

  it("falls back when the candidate is unsafe", () => {
    expect(resolveNextPath("/boletos", "/painel")).toBe("/boletos");
    expect(resolveNextPath("https://evil.example", "/painel")).toBe("/painel");
    expect(resolveNextPath(undefined, "/painel")).toBe("/painel");
  });
});

describe("decideAuthAction", () => {
  it("redirects anonymous users from private routes to login with next", () => {
    expect(
      decideAuthAction({ pathname: "/boletos", search: "?page=2", hasSession: false }),
    ).toEqual({
      action: "redirect",
      location: "/login?next=%2Fboletos%3Fpage%3D2",
    });
  });

  it("allows anonymous users on public routes", () => {
    expect(decideAuthAction({ pathname: "/", search: "", hasSession: false })).toEqual({
      action: "next",
    });
    expect(decideAuthAction({ pathname: "/login", search: "", hasSession: false })).toEqual({
      action: "next",
    });
  });

  it("redirects authenticated users away from login to next or painel", () => {
    expect(
      decideAuthAction({
        pathname: "/login",
        search: "?next=%2Fvencimentos",
        hasSession: true,
      }),
    ).toEqual({ action: "redirect", location: "/painel" });

    expect(
      decideAuthAction({ pathname: "/login", search: "?next=%2Ffolha", hasSession: true }),
    ).toEqual({ action: "redirect", location: "/folha" });
  });

  it("allows authenticated users on private routes", () => {
    expect(decideAuthAction({ pathname: "/painel", search: "", hasSession: true })).toEqual({
      action: "next",
    });
  });

  it("does not protect unknown routes", () => {
    expect(decideAuthAction({ pathname: "/qualquer", search: "", hasSession: false })).toEqual({
      action: "next",
    });
  });
});
