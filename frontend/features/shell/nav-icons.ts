import {
  Bell,
  FileStack,
  Gauge,
  Landmark,
  Receipt,
  ScanSearch,
  ShieldAlert,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export const SHELL_NAV_ICONS: Record<string, LucideIcon> = {
  "/painel": Gauge,
  "/pagamentos": Receipt,
  "/verificacao": ScanSearch,
  "/inteligencia": ShieldAlert,
  "/folha": Landmark,
  "/boletos": FileStack,
  "/notificacoes": Bell,
  "/account": UserRound,
};
