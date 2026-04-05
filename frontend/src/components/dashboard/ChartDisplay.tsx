import { motion } from "framer-motion";
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  Area, AreaChart,
} from "recharts";
import { FileText } from "lucide-react";
import type { ChartConfig } from "./ChatPanel";

interface ChartDisplayProps {
  chart: ChartConfig | null;
  onGenerateReport: () => void;
}

const COLORS = {
  blue: "hsl(199, 89%, 48%)",
  green: "hsl(160, 84%, 39%)",
  amber: "hsl(38, 92%, 50%)",
  red: "hsl(0, 72%, 51%)",
};

const DEFAULT_FORCE_STRAIN = [
  { strain: 0, force: 0 },
  { strain: 0.5, force: 120 },
  { strain: 1.0, force: 310 },
  { strain: 1.5, force: 480 },
  { strain: 2.0, force: 590 },
  { strain: 2.5, force: 650 },
  { strain: 3.0, force: 680 },
  { strain: 3.5, force: 695 },
  { strain: 4.0, force: 700 },
  { strain: 4.5, force: 690 },
  { strain: 5.0, force: 620 },
  { strain: 5.5, force: 480 },
  { strain: 6.0, force: 0 },
];

const DEFAULT_COMPARISON = [
  { name: "Sample 1", machineA: 710, machineB: 695 },
  { name: "Sample 2", machineA: 725, machineB: 680 },
  { name: "Sample 3", machineA: 698, machineB: 710 },
  { name: "Sample 4", machineA: 740, machineB: 700 },
  { name: "Sample 5", machineA: 715, machineB: 720 },
];

const DEFAULT_TREND = [
  { month: "Oct", strength: 710 },
  { month: "Nov", strength: 718 },
  { month: "Dec", strength: 705 },
  { month: "Jan", strength: 725 },
  { month: "Feb", strength: 730 },
  { month: "Mar", strength: 738 },
];

function flattenRow(row: Record<string, unknown>, index: number): Record<string, unknown> {
  const out: Record<string, unknown> = { _index: index };
  for (const [k, v] of Object.entries(row)) {
    if (k === "_id") {
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        const nested = v as Record<string, unknown>;
        if (nested.date !== undefined) out.date = String(nested.date);
        if (nested.group !== undefined) out.group = String(nested.group);
      } else {
        out._id = String(v ?? index);
      }
    } else if (typeof v === "number" || typeof v === "string") {
      out[k] = v;
    }
  }
  return out;
}

function getChartData(chart: ChartConfig): { data: Record<string, unknown>[]; xKey: string; yKey: string } {
  const rows = chart.data ?? [];
  if (!rows.length) {
    const defaults = chart.type === "bar" ? DEFAULT_COMPARISON : chart.type === "line" ? DEFAULT_TREND : DEFAULT_FORCE_STRAIN;
    return {
      data: defaults as Record<string, unknown>[],
      xKey: chart.xKey ?? "name",
      yKey: chart.yKey ?? "force",
    };
  }
  const flat = rows.map(flattenRow);

  // Resolve xKey: prefer chart.xKey if it exists in data, otherwise auto-detect
  const X_FALLBACK_ORDER = ["date", "group", "_id", "_index"] as const;
  let xKey = chart.xKey ?? "_index";
  if (flat.length > 0 && flat[0][xKey] === undefined) {
    // chart.xKey doesn't exist in data — pick first key that does
    xKey = X_FALLBACK_ORDER.find(k => flat[0][k] !== undefined) ?? "_index";
  } else if (xKey === "_id" && flat.length > 0) {
    // "_id" is valid but prefer "date" or "group" if they exist
    if (flat[0].date !== undefined) xKey = "date";
    else if (flat[0].group !== undefined) xKey = "group";
  }

  // Resolve yKey: prefer chart.yKey if it exists in data, otherwise auto-detect from known fields
  const Y_FALLBACK_ORDER = ["avg_value", "mean", "doc_avg", "force", "total"];
  let yKey = chart.yKey ?? "";
  if (!yKey || (flat.length > 0 && flat[0][yKey] === undefined)) {
    yKey = Y_FALLBACK_ORDER.find(k => flat.length > 0 && flat[0][k] !== undefined) ?? "";
  }

  // If no meaningful y-axis data found, fall through to static default chart
  if (!yKey) {
    const defaults = chart.type === "bar" ? DEFAULT_COMPARISON : chart.type === "line" ? DEFAULT_TREND : DEFAULT_FORCE_STRAIN;
    return { data: defaults as Record<string, unknown>[], xKey: chart.xKey ?? "name", yKey: chart.yKey ?? "force" };
  }

  // Filter out rows with null/invalid x values for line/area charts
  const filteredFlat = chart.type === "line" || chart.type === "area"
    ? flat.filter(r => r[xKey] !== undefined && r[xKey] !== "null" && r[xKey] !== null && r[xKey] !== "")
    : flat;

  // If filtering removed all rows (e.g. no valid dates), fall back to static default
  if (!filteredFlat.length) {
    const defaults = chart.type === "bar" ? DEFAULT_COMPARISON : chart.type === "line" ? DEFAULT_TREND : DEFAULT_FORCE_STRAIN;
    return { data: defaults as Record<string, unknown>[], xKey: chart.xKey ?? "name", yKey: chart.yKey ?? "force" };
  }

  return { data: filteredFlat, xKey, yKey };
}

export function ChartDisplay({ chart, onGenerateReport }: ChartDisplayProps) {
  const activeChart = chart || {
    type: "line" as const,
    title: "Force vs Strain Curve",
    data: DEFAULT_FORCE_STRAIN,
    xKey: "strain",
    yKey: "force",
  };

  const tooltipStyle = {
    contentStyle: {
      backgroundColor: "hsl(220, 18%, 12%)",
      border: "1px solid hsl(220, 16%, 18%)",
      borderRadius: "8px",
      fontSize: "12px",
      color: "hsl(220, 15%, 90%)",
    },
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 space-y-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{activeChart.title}</h3>
        <button
          onClick={onGenerateReport}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
        >
          <FileText className="w-3.5 h-3.5" />
          Generate Report
        </button>
      </div>

      {/* Main Chart */}
      <div className="h-[280px]">
        {activeChart.type === "table" ? (
          <div className="h-full overflow-auto rounded-md border border-border scrollbar-thin">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="text-xs uppercase bg-secondary/50 sticky top-0 z-10 backdrop-blur-sm">
                <tr>
                  {Object.keys(activeChart.data?.[0] || {}).map((k) => (
                    <th key={k} className="px-4 py-3 font-medium text-muted-foreground">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(activeChart.data || []).slice(0, 50).map((row, i) => (
                  <tr key={i} className="hover:bg-muted/20 transition-colors">
                    {Object.values(row).map((val: unknown, j) => (
                      <td key={j} className="px-4 py-2 text-foreground truncate max-w-[250px]">
                        {typeof val === "number" ? parseFloat(val.toFixed(4)).toString() : String(val ?? "-")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {(!activeChart.data || activeChart.data.length === 0) && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No data available to display in table.
              </div>
            )}
          </div>
        ) : (
          (() => {
            const { data, xKey, yKey } = getChartData(activeChart);
            return (
              <ResponsiveContainer width="100%" height="100%">
                {activeChart.type === "scatter" ? (
                  <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                    <XAxis dataKey={xKey} name={xKey} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <YAxis dataKey={yKey} name={yKey} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <Tooltip {...tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
                    <Scatter name="Data" data={data} fill={COLORS.amber} />
                  </ScatterChart>
                ) : activeChart.type === "bar" ? (
                  <BarChart data={data} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                    <XAxis dataKey={xKey} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <YAxis tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <Tooltip {...tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey={yKey} fill={COLORS.blue} radius={[4, 4, 0, 0]} />
                  </BarChart>
                ) : (
                  <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                    <defs>
                      <linearGradient id="fillPrimary" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS.blue} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={COLORS.blue} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                    <XAxis dataKey={xKey} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <YAxis tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                    <Tooltip {...tooltipStyle} />
                    <Area type="monotone" dataKey={yKey} stroke={COLORS.blue} fill="url(#fillPrimary)" strokeWidth={2} dot={{ fill: COLORS.blue, r: 3 }} />
                  </AreaChart>
                )}
              </ResponsiveContainer>
            );
          })()
        )}
      </div>

      {/* Secondary charts — only shown for demo fallback (no live data from backend) */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-muted/50 rounded-lg p-3">
          <p className="text-xs font-medium text-muted-foreground mb-2">Max Force Comparison</p>
          <div className="h-[120px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={DEFAULT_COMPARISON}>
                <XAxis dataKey="name" tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Bar dataKey="machineA" fill={COLORS.blue} radius={[3, 3, 0, 0]} />
                <Bar dataKey="machineB" fill={COLORS.green} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-muted/50 rounded-lg p-3">
          <p className="text-xs font-medium text-muted-foreground mb-2">Tensile Strength Trend</p>
          <div className="h-[120px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={DEFAULT_TREND}>
                <XAxis dataKey="month" tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis hide domain={["dataMin - 10", "dataMax + 10"]} />
                <Line type="monotone" dataKey="strength" stroke={COLORS.amber} strokeWidth={2} dot={{ fill: COLORS.amber, r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
