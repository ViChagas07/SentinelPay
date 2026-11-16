import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type FeaturePreviewVariant =
  "painel" | "verificacao" | "boletos" | "folha" | "notificacoes" | "inteligencia" | "pagamentos";

type PreviewProps = {
  children: ReactNode;
  className?: string;
};

function PreviewFrame({ children, className }: PreviewProps) {
  return (
    <svg
      viewBox="0 0 320 180"
      className={cn("h-auto w-full", className)}
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="1"
        y="1"
        width="318"
        height="178"
        rx="4"
        fill="var(--surface)"
        stroke="var(--border)"
      />
      {children}
    </svg>
  );
}

function PanelPreview() {
  return (
    <PreviewFrame>
      <path d="M1 9a8 8 0 0 1 8-8h56v178H9a8 8 0 0 1-8-8Z" fill="var(--petrol-sidebar)" />
      <circle cx="20" cy="24" r="4" fill="var(--petrol-primary)" />
      <rect x="30" y="21" width="24" height="6" rx="3" fill="var(--on-petrol)" opacity="0.55" />
      <rect x="16" y="48" width="38" height="6" rx="3" fill="var(--on-petrol)" opacity="0.85" />
      <rect x="16" y="64" width="30" height="5" rx="2.5" fill="var(--on-petrol)" opacity="0.35" />
      <rect x="16" y="80" width="34" height="5" rx="2.5" fill="var(--on-petrol)" opacity="0.35" />
      <rect x="16" y="96" width="26" height="5" rx="2.5" fill="var(--on-petrol)" opacity="0.35" />
      <rect x="82" y="16" width="86" height="7" rx="3.5" fill="var(--foreground)" opacity="0.8" />
      <rect
        x="82"
        y="32"
        width="52"
        height="5"
        rx="2.5"
        fill="var(--text-secondary)"
        opacity="0.7"
      />
      {[82, 162, 242].map((x) => (
        <g key={x}>
          <rect
            x={x}
            y="52"
            width="60"
            height="42"
            rx="4"
            fill="var(--surface-elevated)"
            stroke="var(--border)"
          />
          <rect
            x={x + 10}
            y="62"
            width="24"
            height="4"
            rx="2"
            fill="var(--text-secondary)"
            opacity="0.6"
          />
          <rect
            x={x + 10}
            y="72"
            width="34"
            height="9"
            rx="3"
            fill="var(--foreground)"
            opacity="0.75"
          />
        </g>
      ))}
      <rect
        x="82"
        y="112"
        width="220"
        height="52"
        rx="4"
        fill="var(--surface-elevated)"
        stroke="var(--border)"
      />
      <polyline
        points="94,150 114,140 134,144 154,128 174,134 194,120 214,126 234,116 254,122 274,112 290,118"
        fill="none"
        stroke="var(--petrol-500)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="82"
        y="146"
        width="30"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.5"
      />
    </PreviewFrame>
  );
}

function VerificationPreview() {
  return (
    <PreviewFrame>
      <rect
        x="66"
        y="22"
        width="136"
        height="136"
        rx="4"
        fill="var(--surface-elevated)"
        stroke="var(--border)"
      />
      <rect x="80" y="38" width="58" height="6" rx="3" fill="var(--foreground)" opacity="0.75" />
      <rect
        x="80"
        y="52"
        width="94"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.55"
      />
      {[70, 82, 94, 106, 118, 130].map((y) => (
        <rect
          key={y}
          x="80"
          y={y}
          width={y % 24 === 0 ? 74 : 98}
          height="4"
          rx="2"
          fill="var(--text-secondary)"
          opacity="0.45"
        />
      ))}
      <rect
        x="198"
        y="34"
        width="62"
        height="112"
        rx="4"
        fill="var(--surface)"
        stroke="var(--petrol-500)"
      />
      <path
        d="M212 86a18 18 0 1 1 26 16l10 10-6 6-10-10a18 18 0 0 1-20-22Z"
        fill="none"
        stroke="var(--petrol-500)"
        strokeWidth="2"
      />
      <path
        d="m214 86 4 4 8-9"
        fill="none"
        stroke="var(--petrol-500)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="210"
        y="126"
        width="38"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.5"
      />
      <g stroke="var(--petrol-500)" strokeWidth="2" strokeLinecap="round">
        <path d="M56 14v10M56 14h10" />
        <path d="M212 14v10M212 14h-10" />
        <path d="M56 164v-10M56 164h10" />
        <path d="M212 164v-10M212 164h-10" />
      </g>
    </PreviewFrame>
  );
}

function BoletoPreview() {
  return (
    <PreviewFrame>
      <rect
        x="42"
        y="14"
        width="236"
        height="152"
        rx="4"
        fill="var(--surface-elevated)"
        stroke="var(--border)"
      />
      <rect x="58" y="30" width="62" height="6" rx="3" fill="var(--foreground)" opacity="0.75" />
      <rect
        x="58"
        y="44"
        width="48"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.55"
      />
      <rect
        x="58"
        y="68"
        width="118"
        height="6"
        rx="3"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
      <rect
        x="58"
        y="82"
        width="94"
        height="6"
        rx="3"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
      <rect
        x="58"
        y="104"
        width="86"
        height="6"
        rx="3"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
      <rect
        x="58"
        y="118"
        width="110"
        height="6"
        rx="3"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
      <g fill="var(--foreground)" opacity="0.8">
        {[
          0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
        ].map((index) => (
          <rect
            key={index}
            x={58 + index * 7}
            y={136}
            width={index % 3 === 0 ? 3 : 2}
            height={18}
          />
        ))}
      </g>
      <circle
        cx="248"
        cy="46"
        r="17"
        fill="var(--surface)"
        stroke="var(--petrol-500)"
        strokeWidth="2"
      />
      <path
        d="m241 46 5 5 9-11"
        fill="none"
        stroke="var(--petrol-500)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </PreviewFrame>
  );
}

function PayslipPreview() {
  return (
    <PreviewFrame>
      <rect
        x="40"
        y="14"
        width="240"
        height="152"
        rx="4"
        fill="var(--surface-elevated)"
        stroke="var(--border)"
      />
      <rect x="56" y="28" width="76" height="6" rx="3" fill="var(--foreground)" opacity="0.75" />
      <rect
        x="56"
        y="40"
        width="50"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.55"
      />
      <rect x="56" y="56" width="208" height="7" rx="2" fill="var(--petrol-500)" opacity="0.25" />
      {[74, 90, 106, 122, 138].map((y) => (
        <g key={y}>
          <rect
            x="56"
            y={y}
            width="94"
            height="4"
            rx="2"
            fill="var(--text-secondary)"
            opacity="0.45"
          />
          <rect
            x="176"
            y={y}
            width="38"
            height="4"
            rx="2"
            fill="var(--text-secondary)"
            opacity="0.45"
          />
          <rect
            x="230"
            y={y}
            width="34"
            height="4"
            rx="2"
            fill="var(--foreground)"
            opacity="0.55"
          />
        </g>
      ))}
      <rect x="56" y="152" width="208" height="1" fill="var(--border)" />
      <rect x="186" y="122" width="34" height="4" rx="2" fill="var(--foreground)" opacity="0.7" />
      <circle cx="252" cy="56" r="10" fill="var(--surface)" stroke="var(--petrol-500)" />
      <path
        d="M246 56h12M252 50v12"
        stroke="var(--petrol-500)"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </PreviewFrame>
  );
}

function NotificationsPreview() {
  return (
    <PreviewFrame>
      <path
        d="M146 30a14 14 0 0 1 28 0v10l6 8h-40l6-8Z"
        fill="none"
        stroke="var(--petrol-500)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M155 52h10" stroke="var(--petrol-500)" strokeWidth="2" strokeLinecap="round" />
      {[74, 100, 126].map((y, index) => (
        <g key={y}>
          <rect
            x="62"
            y={y}
            width="196"
            height="20"
            rx="4"
            fill="var(--surface-elevated)"
            stroke="var(--border)"
          />
          <circle
            cx="78"
            cy={y + 10}
            r="3"
            fill={index === 0 ? "var(--petrol-500)" : "var(--text-secondary)"}
            opacity={index === 0 ? 1 : 0.4}
          />
          <rect
            x="90"
            y={y + 6}
            width="92"
            height="4"
            rx="2"
            fill="var(--foreground)"
            opacity="0.65"
          />
          <rect
            x="90"
            y={y + 13}
            width="58"
            height="3"
            rx="1.5"
            fill="var(--text-secondary)"
            opacity="0.45"
          />
          <circle cx="246" cy={y + 10} r="4" fill="var(--text-secondary)" opacity="0.25" />
        </g>
      ))}
      <rect
        x="62"
        y="152"
        width="80"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
    </PreviewFrame>
  );
}

function IntelligencePreview() {
  return (
    <PreviewFrame>
      <path
        d="M160 22 210 42v42c0 32-22 56-50 68-28-12-50-36-50-68V42Z"
        fill="var(--surface-elevated)"
        stroke="var(--petrol-500)"
        strokeWidth="2"
      />
      <path
        d="M160 38v88M160 62l-20-10M160 62l20-10M160 88l-20-10M160 88l20-10"
        stroke="var(--petrol-500)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {[56, 82, 108].map((y, index) => (
        <g key={y}>
          <circle
            cx="252"
            cy={y + 6}
            r="4"
            fill={
              index === 0
                ? "var(--risk-high)"
                : index === 1
                  ? "var(--risk-medium)"
                  : "var(--risk-low)"
            }
          />
          <rect
            x="264"
            y={y + 2}
            width="34"
            height="4"
            rx="2"
            fill="var(--text-secondary)"
            opacity="0.55"
          />
          <rect
            x="264"
            y={y + 10}
            width="22"
            height="3"
            rx="1.5"
            fill="var(--text-secondary)"
            opacity="0.35"
          />
        </g>
      ))}
      <rect x="232" y="126" width="66" height="6" rx="3" fill="var(--petrol-500)" opacity="0.25" />
      <rect
        x="232"
        y="140"
        width="44"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
    </PreviewFrame>
  );
}

function PaymentsPreview() {
  return (
    <PreviewFrame>
      <rect
        x="40"
        y="14"
        width="240"
        height="152"
        rx="4"
        fill="var(--surface-elevated)"
        stroke="var(--border)"
      />
      <rect x="56" y="28" width="72" height="6" rx="3" fill="var(--foreground)" opacity="0.75" />
      <rect x="244" y="26" width="20" height="8" rx="4" fill="var(--petrol-500)" opacity="0.25" />
      {[0, 1, 2, 3, 4, 5, 6].map((column) =>
        [0, 1, 2, 3].map((row) => {
          const x = 56 + column * 30;
          const y = 52 + row * 24;
          const highlighted = column === 3 && row === 1;
          const hasDot = (column * 3 + row * 5) % 4 === 0;

          return (
            <g key={`${column}-${row}`}>
              <rect
                x={x}
                y={y}
                width="20"
                height="16"
                rx="2"
                fill={highlighted ? "var(--petrol-500)" : "var(--surface)"}
                stroke={highlighted ? "var(--petrol-500)" : "var(--border)"}
              />
              {hasDot && !highlighted ? (
                <circle cx={x + 10} cy={y + 8} r="2" fill="var(--text-secondary)" opacity="0.5" />
              ) : null}
            </g>
          );
        }),
      )}
      <path
        d="m151 84 3 3 6-7"
        fill="none"
        stroke="var(--surface)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="56"
        y="148"
        width="90"
        height="4"
        rx="2"
        fill="var(--text-secondary)"
        opacity="0.45"
      />
      <rect x="212" y="148" width="52" height="4" rx="2" fill="var(--petrol-500)" opacity="0.35" />
    </PreviewFrame>
  );
}

const PREVIEWS: Record<FeaturePreviewVariant, () => ReactNode> = {
  painel: PanelPreview,
  verificacao: VerificationPreview,
  boletos: BoletoPreview,
  folha: PayslipPreview,
  notificacoes: NotificationsPreview,
  inteligencia: IntelligencePreview,
  pagamentos: PaymentsPreview,
};

export function FeaturePreview({ variant }: Readonly<{ variant: FeaturePreviewVariant }>) {
  const Preview = PREVIEWS[variant];

  return <Preview />;
}
