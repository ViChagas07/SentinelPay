"use client";

import { Command as CommandIcon } from "lucide-react";
import Image from "next/image";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Logo, Wordmark } from "@/components/brand/logo";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { DataTable, type DataTableColumn, type DataTableState } from "@/components/ui/data-table";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EvidenceItem } from "@/components/ui/evidence-item";
import { Eyebrow } from "@/components/ui/eyebrow";
import { CountUp } from "@/components/ui/motion/count-up";
import { PageTransition } from "@/components/ui/motion/page-transition";
import { Presence } from "@/components/ui/motion/presence";
import { Stagger, StaggerItem } from "@/components/ui/motion/stagger";
import { ClassDot, RiskBadge } from "@/components/ui/risk-badge";
import { RiskRuler, type RiskRulerVariant } from "@/components/ui/risk-ruler";
import { RiskStamp } from "@/components/ui/risk-stamp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/ui/sparkline";
import { StatBlock } from "@/components/ui/stat-block";
import { StripChart, type StripChartPoint } from "@/components/ui/strip-chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { EvidenceSeverity, RiskBand } from "@/lib/api/schemas";
import { LOCALES, type TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { useTheme } from "@/lib/theme/provider";

type DemoRow = {
  id: string;
  type: "boleto" | "payslip" | "receipt";
  status: "queued" | "processing" | "ready";
  score: number;
  band: RiskBand;
};

const RISK_BANDS: readonly RiskBand[] = ["low", "attention", "high"];

const RULER_DEMOS: ReadonlyArray<{
  variant: RiskRulerVariant;
  score: number;
  band: RiskBand;
}> = [
  { variant: "compact", score: 18, band: "low" },
  { variant: "medium", score: 54, band: "attention" },
  { variant: "large", score: 86, band: "high" },
];

const DEMO_ROWS: readonly DemoRow[] = [
  { id: "doc_0107", type: "boleto", status: "ready", score: 18, band: "low" },
  { id: "doc_0106", type: "payslip", status: "processing", score: 54, band: "attention" },
  { id: "doc_0105", type: "receipt", status: "queued", score: 86, band: "high" },
];

const TYPE_KEYS: Record<DemoRow["type"], TranslationKey> = {
  boleto: "design.dataTable.typeBoleto",
  payslip: "design.dataTable.typePayslip",
  receipt: "design.dataTable.typeReceipt",
};

const STATUS_KEYS: Record<DemoRow["status"], TranslationKey> = {
  queued: "design.dataTable.statusQueued",
  processing: "design.dataTable.statusProcessing",
  ready: "design.dataTable.statusReady",
};

const TABLE_STATES: ReadonlyArray<{ value: DataTableState; labelKey: TranslationKey }> = [
  { value: "ready", labelKey: "design.dataTable.stateReady" },
  { value: "loading", labelKey: "design.dataTable.stateLoading" },
  { value: "empty", labelKey: "design.dataTable.stateEmpty" },
  { value: "error", labelKey: "design.dataTable.stateError" },
];

const EVIDENCE_DEMOS: ReadonlyArray<{
  key: string;
  severity: EvidenceSeverity;
  framework: "FEBRABAN" | "INSS" | "CLT";
  ruleKey: TranslationKey;
  excerptKey: TranslationKey;
}> = [
  {
    key: "febraban",
    severity: "high",
    framework: "FEBRABAN",
    ruleKey: "design.evidence.ruleDV",
    excerptKey: "design.evidence.excerptDV",
  },
  {
    key: "inss",
    severity: "medium",
    framework: "INSS",
    ruleKey: "design.evidence.ruleINSS",
    excerptKey: "design.evidence.excerptINSS",
  },
  {
    key: "clt",
    severity: "low",
    framework: "CLT",
    ruleKey: "design.evidence.ruleCLT",
    excerptKey: "design.evidence.excerptCLT",
  },
];

const STRIP_DATA: readonly StripChartPoint[] = [
  { date: "2026-11-09", low: 3, attention: 1, high: 0 },
  { date: "2026-11-10", low: 4, attention: 2, high: 1 },
  { date: "2026-11-11", low: 2, attention: 1, high: 0 },
  { date: "2026-11-12", low: 5, attention: 3, high: 1 },
  { date: "2026-11-13", low: 4, attention: 2, high: 2 },
  { date: "2026-11-14", low: 6, attention: 2, high: 1 },
  { date: "2026-11-15", low: 5, attention: 4, high: 2 },
];

const SPARK_DATA = [12, 18, 14, 26, 24, 31, 29] as const;

const SECTIONS = [
  { id: "brand", label: "Brand" },
  { id: "typography", label: "StatBlock" },
  { id: "risk", label: "Risk" },
  { id: "data", label: "DataTable" },
  { id: "evidence", label: "EvidenceItem" },
  { id: "charts", label: "Charts" },
  { id: "motion", label: "Motion" },
  { id: "primitives", label: "Primitives" },
] as const;

function ShowcaseSection({
  id,
  index,
  title,
  children,
}: Readonly<{ id: string; index: string; title: string; children: ReactNode }>) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-border pt-10">
      <Eyebrow number={index} label={title} as="h2" />
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function DesignShowcase() {
  const { t, locale, setLocale, formatNumber } = useI18n();
  const { mode, setMode } = useTheme();
  const [tableState, setTableState] = useState<DataTableState>("ready");
  const [highlighted, setHighlighted] = useState<string | null>("febraban");
  const [presenceOpen, setPresenceOpen] = useState(true);
  const [countKey, setCountKey] = useState(0);
  const [selectedOption, setSelectedOption] = useState("a");
  const [commandOpen, setCommandOpen] = useState(false);
  const selectedLabel =
    selectedOption === "b"
      ? t("design.select.optionB")
      : selectedOption === "c"
        ? t("design.select.optionC")
        : t("design.select.optionA");

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function goToSection(id: string) {
    setCommandOpen(false);
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  }

  function cycleLocale() {
    const currentIndex = LOCALES.indexOf(locale);
    const nextLocale = LOCALES[(currentIndex + 1) % LOCALES.length] ?? "pt";
    setLocale(nextLocale);
  }

  function toggleTheme() {
    setMode(mode === "dark" ? "light" : "dark");
  }

  const columns: readonly DataTableColumn<DemoRow>[] = [
    {
      id: "id",
      header: "ID",
      mono: true,
      cell: (row) => row.id,
      sortValue: (row) => row.id,
    },
    {
      id: "type",
      header: t("design.dataTable.columnType"),
      cell: (row) => t(TYPE_KEYS[row.type]),
      sortValue: (row) => row.type,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => t(STATUS_KEYS[row.status]),
      sortValue: (row) => row.status,
    },
    {
      id: "score",
      header: "Score",
      mono: true,
      align: "right",
      cell: (row) => row.score,
      sortValue: (row) => row.score,
    },
    {
      id: "class",
      header: t("design.dataTable.columnClass"),
      cell: (row) => <RiskBadge band={row.band} showIcon={false} />,
      sortValue: (row) => row.band,
    },
  ];

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="conteudo" className="flex-1">
        <PageTransition>
          <section className="border-b border-border bg-landing">
            <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
              <Eyebrow number="00" label={t("design.page.eyebrow")} />
              <h1 className="mt-5 max-w-4xl font-serif text-5xl leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
                {t("design.page.title")}
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">
                {t("design.page.description")}
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-2">
                <Badge variant="outline">{t("design.page.productionBlocked")}</Badge>
                <Badge variant="secondary">{t("design.page.demoNotice")}</Badge>
              </div>
              <p className="mt-4 font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
                {t("design.page.hint")}
              </p>
              <nav aria-label={t("design.page.nav")} className="mt-8 flex flex-wrap gap-2">
                {SECTIONS.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="rounded-[6px] border border-border px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
                  >
                    {section.label}
                  </a>
                ))}
              </nav>
            </div>
          </section>

          <div className="mx-auto flex max-w-6xl flex-col gap-12 px-5 py-12 sm:px-8">
            <ShowcaseSection id="brand" index="01" title="Brand">
              <div className="grid gap-3 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Wordmark</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Wordmark name={t("app.name")} className="text-2xl" />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Logo</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap items-end gap-6">
                    <Logo className="size-14 text-primary" title={t("app.name")} />
                    <div className="flex items-end gap-4">
                      <Image
                        src="/icon.svg"
                        alt={t("design.brand.faviconDefault")}
                        width={64}
                        height={64}
                        unoptimized
                      />
                      <Image
                        src="/favicon-alert.svg"
                        alt={t("design.brand.faviconAlert")}
                        width={64}
                        height={64}
                        unoptimized
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </ShowcaseSection>

            <ShowcaseSection id="typography" index="02" title="Eyebrow / StatBlock">
              <div className="grid gap-3 lg:grid-cols-[0.7fr_1.3fr]">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Eyebrow</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Eyebrow number="01" label={t("design.page.eyebrowExample")} />
                  </CardContent>
                </Card>
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatBlock
                    label={t("design.page.statLanguages")}
                    value="3"
                    change={{
                      value: "0",
                      direction: "flat",
                      label: t("design.page.changeStable"),
                    }}
                  />
                  <StatBlock
                    label={t("design.page.statRadius")}
                    value="6px"
                    change={{
                      value: "0",
                      direction: "flat",
                      label: t("design.page.changeStable"),
                    }}
                  />
                  <StatBlock
                    label={t("design.page.statLine")}
                    value="1px"
                    change={{
                      value: "0",
                      direction: "flat",
                      label: t("design.page.changeStable"),
                    }}
                  />
                  <StatBlock
                    label={t("design.page.sample")}
                    value="24"
                    sparkline={SPARK_DATA}
                    change={{
                      value: "+6",
                      direction: "up",
                      label: t("design.page.chartSample"),
                    }}
                  />
                </div>
              </div>
            </ShowcaseSection>

            <ShowcaseSection id="risk" index="03" title="RiskRuler / RiskStamp / RiskBadge">
              <div className="grid gap-3 lg:grid-cols-2">
                {RULER_DEMOS.map((demo) => (
                  <Card
                    key={demo.variant}
                    className={demo.variant === "large" ? "lg:col-span-2" : undefined}
                  >
                    <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
                      <CardTitle className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        RiskRuler {demo.variant}
                      </CardTitle>
                      <RiskBadge band={demo.band} showIcon={false} />
                    </CardHeader>
                    <CardContent>
                      <RiskRuler score={demo.score} band={demo.band} variant={demo.variant} />
                    </CardContent>
                  </Card>
                ))}
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">RiskStamp</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-3">
                    {RISK_BANDS.map((band) => (
                      <RiskStamp key={band} band={band} />
                    ))}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">RiskBadge / ClassDot</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    {RISK_BANDS.map((band) => {
                      const presentation = getRiskPresentation(band);

                      return (
                        <div key={band} className="flex items-center gap-3">
                          <RiskBadge band={band} />
                          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                            <ClassDot band={band} />
                            {t(presentation.labelKey)}
                          </span>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              </div>
            </ShowcaseSection>

            <ShowcaseSection id="data" index="04" title="DataTable">
              <div className="mb-3 flex flex-wrap gap-2">
                {TABLE_STATES.map((state) => (
                  <Button
                    key={state.value}
                    type="button"
                    size="sm"
                    variant={tableState === state.value ? "default" : "outline"}
                    onClick={() => setTableState(state.value)}
                  >
                    {t(state.labelKey)}
                  </Button>
                ))}
              </div>
              <DataTable
                columns={columns}
                rows={DEMO_ROWS}
                getRowId={(row) => row.id}
                ariaLabel={t("design.dataTable.aria")}
                state={tableState}
                initialSort={{ columnId: "score", direction: "desc" }}
                onRetry={() => setTableState("ready")}
              />
            </ShowcaseSection>

            <ShowcaseSection id="evidence" index="05" title="EvidenceItem">
              <div className="grid gap-3 lg:grid-cols-3">
                {EVIDENCE_DEMOS.map((evidence) => (
                  <EvidenceItem
                    key={evidence.key}
                    severity={evidence.severity}
                    framework={evidence.framework}
                    rule={t(evidence.ruleKey)}
                    excerpt={t(evidence.excerptKey)}
                    highlighted={highlighted === evidence.key}
                    onToggleHighlight={() =>
                      setHighlighted((current) => (current === evidence.key ? null : evidence.key))
                    }
                  />
                ))}
              </div>
            </ShowcaseSection>

            <ShowcaseSection id="charts" index="06" title="StripChart / Sparkline">
              <div className="grid gap-3 lg:grid-cols-[1.4fr_0.6fr]">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">StripChart</CardTitle>
                    <CardDescription>{t("design.page.chartSample")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <StripChart data={STRIP_DATA} height={180} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Sparkline</CardTitle>
                    <CardDescription>{t("design.page.chartSample")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Sparkline
                      data={SPARK_DATA}
                      width={240}
                      height={48}
                      className="w-full text-primary"
                    />
                  </CardContent>
                </Card>
              </div>
            </ShowcaseSection>

            <ShowcaseSection
              id="motion"
              index="07"
              title="PageTransition / Stagger / CountUp / Presence"
            >
              <div className="grid gap-3 lg:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">CountUp</CardTitle>
                    <CardDescription>{t("design.motion.reduced")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <CountUp
                      key={countKey}
                      value={100}
                      format={(value) => formatNumber(value)}
                      className="font-serif text-5xl leading-none tracking-tight"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setCountKey((key) => key + 1)}
                    >
                      {t("design.motion.replay")}
                    </Button>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Stagger</CardTitle>
                    <CardDescription>{t("design.motion.reduced")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Stagger className="grid grid-cols-4 gap-1">
                      {[0, 1, 2, 3].map((item) => (
                        <StaggerItem
                          key={item}
                          className="rounded-[6px] border border-border p-2 text-center font-mono text-xs tabular-nums text-muted-foreground"
                        >
                          0{item + 1}
                        </StaggerItem>
                      ))}
                    </Stagger>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Presence</CardTitle>
                    <CardDescription>{t("design.motion.reduced")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setPresenceOpen((open) => !open)}
                    >
                      {presenceOpen ? t("design.motion.hide") : t("design.motion.show")}
                    </Button>
                    <Presence show={presenceOpen}>
                      <div className="rounded-[6px] border border-border bg-surface-elevated p-3 text-sm text-muted-foreground">
                        {t("design.motion.reduced")}
                      </div>
                    </Presence>
                  </CardContent>
                </Card>
              </div>
            </ShowcaseSection>

            <ShowcaseSection
              id="primitives"
              index="08"
              title="Toast / Skeleton / Tooltip / Dialog / Sheet / Tabs / Select / Command"
            >
              <div className="grid gap-3 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Toast / Skeleton</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        toast(t("design.toast.title"), {
                          description: t("design.toast.description"),
                        })
                      }
                    >
                      {t("design.toast.trigger")}
                    </Button>
                    <div className="space-y-2">
                      <Skeleton className="h-3 w-2/3" />
                      <Skeleton className="h-3 w-1/2" />
                      <Skeleton className="h-3 w-3/4" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Tooltip</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button type="button" variant="outline">
                            {t("design.tooltip.trigger")}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{t("design.tooltip.content")}</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Dialog</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button type="button" variant="outline">
                          {t("design.dialog.trigger")}
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>{t("design.dialog.title")}</DialogTitle>
                          <DialogDescription>{t("design.dialog.description")}</DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                          <DialogClose asChild>
                            <Button type="button" variant="outline">
                              {t("design.dialog.cancel")}
                            </Button>
                          </DialogClose>
                          <DialogClose asChild>
                            <Button type="button">{t("design.dialog.confirm")}</Button>
                          </DialogClose>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Sheet</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Sheet>
                      <SheetTrigger asChild>
                        <Button type="button" variant="outline">
                          {t("design.sheet.trigger")}
                        </Button>
                      </SheetTrigger>
                      <SheetContent>
                        <SheetHeader>
                          <SheetTitle>{t("design.sheet.title")}</SheetTitle>
                          <SheetDescription>{t("design.sheet.description")}</SheetDescription>
                        </SheetHeader>
                        <SheetFooter>
                          <SheetClose asChild>
                            <Button type="button" variant="outline">
                              {t("design.dialog.cancel")}
                            </Button>
                          </SheetClose>
                          <SheetClose asChild>
                            <Button type="button">{t("design.dialog.confirm")}</Button>
                          </SheetClose>
                        </SheetFooter>
                      </SheetContent>
                    </Sheet>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Tabs / Select</CardTitle>
                    <CardDescription>{t("design.page.demoNotice")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Tabs defaultValue="a">
                      <TabsList aria-label={t("design.tabs.label")}>
                        <TabsTrigger value="a">{t("design.tabs.triggerA")}</TabsTrigger>
                        <TabsTrigger value="b">{t("design.tabs.triggerB")}</TabsTrigger>
                      </TabsList>
                      <TabsContent value="a">{t("design.tabs.contentA")}</TabsContent>
                      <TabsContent value="b">{t("design.tabs.contentB")}</TabsContent>
                    </Tabs>
                    <div className="space-y-1.5">
                      <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                        {t("design.select.label")}
                      </p>
                      <Select value={selectedOption} onValueChange={setSelectedOption}>
                        <SelectTrigger aria-label={`${t("design.select.label")}: ${selectedLabel}`}>
                          <SelectValue placeholder={t("design.select.placeholder")} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="a">{t("design.select.optionA")}</SelectItem>
                          <SelectItem value="b">{t("design.select.optionB")}</SelectItem>
                          <SelectItem value="c">{t("design.select.optionC")}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="font-serif text-2xl">Command</CardTitle>
                    <CardDescription>{t("design.command.description")}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap items-center gap-2">
                    <Button type="button" variant="outline" onClick={() => setCommandOpen(true)}>
                      <CommandIcon aria-hidden="true" />
                      {t("design.command.trigger")}
                    </Button>
                    <span className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                      {t("design.command.shortcut")}
                    </span>
                  </CardContent>
                </Card>
              </div>
            </ShowcaseSection>

            <ShowcaseSection id="empty" index="09" title="EmptyState">
              <Card>
                <CardContent className="pt-6">
                  <EmptyState
                    title={t("design.emptyState.title")}
                    description={t("design.emptyState.description")}
                    action={{
                      label: t("design.emptyState.action"),
                      onClick: () => goToSection("data"),
                    }}
                  />
                </CardContent>
              </Card>
            </ShowcaseSection>
          </div>
        </PageTransition>
      </main>
      <SiteFooter />

      <CommandDialog
        open={commandOpen}
        onOpenChange={setCommandOpen}
        title={t("design.command.title")}
        description={t("design.command.description")}
      >
        <CommandInput
          aria-label={t("design.command.placeholder")}
          placeholder={t("design.command.placeholder")}
        />
        <CommandList>
          <CommandEmpty>{t("design.command.empty")}</CommandEmpty>
          <CommandGroup heading={t("design.command.groupNavigate")}>
            <CommandItem onSelect={() => goToSection("risk")}>
              {t("design.command.goRisk")}
              <CommandShortcut>01</CommandShortcut>
            </CommandItem>
            <CommandItem onSelect={() => goToSection("data")}>
              {t("design.command.goTable")}
              <CommandShortcut>02</CommandShortcut>
            </CommandItem>
            <CommandItem onSelect={() => goToSection("brand")}>
              {t("design.command.goBrand")}
              <CommandShortcut>03</CommandShortcut>
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading={t("design.command.groupAppearance")}>
            <CommandItem
              onSelect={() => {
                setCommandOpen(false);
                toggleTheme();
              }}
            >
              {t("design.command.toggleTheme")}
              <CommandShortcut>{mode}</CommandShortcut>
            </CommandItem>
            <CommandItem
              onSelect={() => {
                setCommandOpen(false);
                cycleLocale();
              }}
            >
              {t("design.command.toggleLanguage")}
              <CommandShortcut>{locale}</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </div>
  );
}
