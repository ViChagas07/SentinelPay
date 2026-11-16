import { ImageResponse } from "next/og";

import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export const alt = "SentinelPay";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const locale = await getServerLocale();
  const eyebrow = serverTranslate(locale, "landing.meta.ogEyebrow");
  const title = serverTranslate(locale, "landing.meta.ogTitle");
  const description = serverTranslate(locale, "landing.meta.ogDescription");
  const tagline = serverTranslate(locale, "landing.meta.ogTagline");

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        backgroundColor: "#0E413A",
        color: "#F1F5F2",
        padding: "72px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <div
          style={{
            width: "44px",
            height: "44px",
            border: "2px solid #499484",
            transform: "rotate(45deg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ width: "18px", height: "2px", backgroundColor: "#499484" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ fontSize: "28px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            SentinelPay
          </div>
          <div
            style={{
              fontSize: "16px",
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "#A7D2CA",
            }}
          >
            {eyebrow}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <div
          style={{
            fontSize: "72px",
            lineHeight: 1.02,
            letterSpacing: "-0.03em",
            maxWidth: "940px",
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: "28px",
            lineHeight: 1.3,
            color: "#D2E8E4",
            maxWidth: "820px",
          }}
        >
          {description}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid rgba(241,245,242,0.22)",
          paddingTop: "24px",
        }}
      >
        <div style={{ fontSize: "18px", color: "#A7D2CA" }}>{tagline}</div>
        <div style={{ fontSize: "18px", color: "#A7D2CA" }}>SentinelPay</div>
      </div>
    </div>,
    {
      ...size,
    },
  );
}
