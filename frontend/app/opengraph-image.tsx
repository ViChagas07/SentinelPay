import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ImageResponse } from "next/og";

import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export const alt = "SentinelPay";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

const logo = `data:image/png;base64,${readFileSync(
  join(process.cwd(), "public", "brand", "logo-symbol-light-512.png"),
).toString("base64")}`;

export default async function OpenGraphImage() {
  const locale = await getServerLocale();
  const eyebrow = serverTranslate(locale, "landing.meta.ogEyebrow");
  const tagline = serverTranslate(locale, "landing.meta.ogTagline");

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0F4138",
        color: "#F1F5F2",
        padding: "64px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "100%",
          flex: 1,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={logo} width={208} height={208} alt="SentinelPay" />
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "18px",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: "92px", fontWeight: 600, letterSpacing: "-0.04em", lineHeight: 1 }}>
          SentinelPay
        </div>
        <div style={{ fontSize: "28px", lineHeight: 1.3, color: "#D2E8E4", maxWidth: "840px" }}>
          {tagline}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            fontSize: "18px",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "#A7D2CA",
            marginTop: "12px",
          }}
        >
          <div style={{ width: "40px", height: "1px", backgroundColor: "#7BBCB0" }} />
          {eyebrow}
          <div style={{ width: "40px", height: "1px", backgroundColor: "#7BBCB0" }} />
        </div>
      </div>
    </div>,
    {
      ...size,
    },
  );
}
