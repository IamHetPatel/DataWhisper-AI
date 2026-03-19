import { motion, AnimatePresence } from "framer-motion";
import { X, Download, FileText, AlertTriangle, Lightbulb, BarChart3, ClipboardList } from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { ReasoningData, ChartConfig } from "./ChatPanel";

interface ReportModalProps {
  open: boolean;
  onClose: () => void;
  reasoning: ReasoningData | null;
  chart: ChartConfig | null;
}

const COLORS = {
  blue: "hsl(199, 89%, 48%)",
  green: "hsl(160, 84%, 39%)",
  amber: "hsl(38, 92%, 50%)",
};

export function ReportModal({ open, onClose, reasoning, chart }: ReportModalProps) {
  const stats = reasoning?.stats || {};
  const anomalies = reasoning?.anomalies || [];
  const recommendation = reasoning?.recommendations || "No recommendations generated.";
  
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
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3 }}
            className="w-full max-w-4xl max-h-[90vh] overflow-y-auto scrollbar-thin bg-card border border-border rounded-2xl shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-8 py-5 border-b border-border sticky top-0 bg-card z-10">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-primary/15 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Material Analysis Report</h2>
                  <p className="text-xs text-muted-foreground">Generated {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition-opacity">
                  <Download className="w-3.5 h-3.5" />
                  Export PDF
                </button>
                <button onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="px-8 py-6 space-y-8">
              {/* Summary */}
              <section>
                <h3 className="text-sm font-semibold text-foreground mb-3">Summary</h3>
                <div className="bg-muted/30 rounded-xl p-4 space-y-2 text-sm text-muted-foreground leading-relaxed">
                  <p>Analysis of 847 tensile test records collected between October 2025 and March 2026 across Machine A and Machine B.</p>
                  <p>Mean maximum force is 714.2 N with a standard deviation of 18.7 N, indicating consistent material performance within acceptable tolerance.</p>
                  <p>A positive trend of +0.8% per month in tensile strength suggests improving specimen preparation quality over time.</p>
                </div>
              </section>

              {/* Chart */}
              {chart && (
                <section>
                  <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary" />
                    {chart.title}
                  </h3>
                  <div className="bg-muted/20 rounded-xl p-4 h-[300px]">
                    {chart.type === "table" ? (
                      <div className="h-full overflow-auto rounded-md border border-border scrollbar-thin">
                        <table className="w-full text-sm text-left whitespace-nowrap">
                          <thead className="text-xs uppercase bg-secondary/50 sticky top-0 z-10 backdrop-blur-sm">
                            <tr>
                              {Object.keys(chart.data?.[0] || {}).map((k) => (
                                <th key={k} className="px-4 py-3 font-medium text-muted-foreground">{k}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {(chart.data || []).slice(0, 50).map((row, i) => (
                              <tr key={i} className="hover:bg-muted/20 transition-colors">
                                {Object.values(row).map((val: any, j) => (
                                  <td key={j} className="px-4 py-2 text-foreground truncate max-w-[250px]">
                                    {typeof val === "number" ? parseFloat(val.toFixed(4)).toString() : String(val ?? "-")}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {(!chart.data || chart.data.length === 0) && (
                          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                            No data available to display in table.
                          </div>
                        )}
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        {chart.type === "scatter" ? (
                          <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                            <XAxis dataKey={chart.xKey || "index"} name={chart.xKey || "Index"} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <YAxis dataKey={chart.yKey || "value"} name={chart.yKey || "Value"} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <Tooltip {...tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
                            <Scatter name="Data" data={chart.data} fill={COLORS.amber} />
                          </ScatterChart>
                        ) : chart.type === "bar" ? (
                          <BarChart data={chart.data} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                            <XAxis dataKey={chart.xKey || "name"} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <YAxis tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <Tooltip {...tooltipStyle} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Bar dataKey={chart.yKey || "mean"} fill={COLORS.blue} radius={[4, 4, 0, 0]} />
                          </BarChart>
                        ) : (
                          <AreaChart data={chart.data} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                            <defs>
                              <linearGradient id="reportFill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={COLORS.blue} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={COLORS.blue} stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 16%, 16%)" />
                            <XAxis dataKey={chart.xKey || "strain"} tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <YAxis tick={{ fill: "hsl(220, 12%, 50%)", fontSize: 11 }} axisLine={{ stroke: "hsl(220, 16%, 18%)" }} />
                            <Tooltip {...tooltipStyle} />
                            <Area type="monotone" dataKey={chart.yKey || "avg_value"} stroke={COLORS.blue} fill="url(#reportFill)" strokeWidth={2} dot={{ fill: COLORS.blue, r: 3 }} />
                          </AreaChart>
                        )}
                      </ResponsiveContainer>
                    )}
                  </div>
                </section>
              )}

              {/* Statistics */}
              <section>
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <ClipboardList className="w-4 h-4 text-chart-green" />
                  Statistics
                </h3>
                <div className="grid grid-cols-5 gap-3">
                  {Object.entries(stats).map(([k, v]) => (
                    <div key={k} className="bg-muted/30 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{k}</p>
                      <p className="text-lg font-bold text-foreground mt-1">{typeof v === 'number' ? v.toLocaleString() : v}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* Anomalies */}
              <section>
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-chart-amber" />
                  Anomalies Detected
                </h3>
                <div className="space-y-2">
                  {anomalies.map((a, i) => (
                    <div key={i} className="bg-chart-amber/5 border border-chart-amber/15 rounded-xl px-4 py-3 text-sm text-muted-foreground">
                      {a}
                    </div>
                  ))}
                </div>
              </section>

              {/* Recommendations */}
              <section>
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Lightbulb className="w-4 h-4 text-chart-green" />
                  Recommendations
                </h3>
                <div className="bg-chart-green/5 border border-chart-green/15 rounded-xl px-4 py-3 text-sm text-muted-foreground leading-relaxed">
                  {recommendation}
                </div>
              </section>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
