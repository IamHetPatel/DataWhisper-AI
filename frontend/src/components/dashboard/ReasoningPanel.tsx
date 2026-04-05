import { motion, AnimatePresence } from "framer-motion";
import {
  Brain, Database, Ruler, BarChart3, LineChart,
  ChevronRight, AlertTriangle, Lightbulb, ClipboardList,
  PanelRightClose, PanelRight,
  type LucideIcon,
} from "lucide-react";
import type { ReasoningData } from "./ChatPanel";

interface ReasoningPanelProps {
  reasoning: ReasoningData | null;
  collapsed: boolean;
  onToggle: () => void;
}

export function ReasoningPanel({ reasoning, collapsed, onToggle }: ReasoningPanelProps) {
  if (!collapsed && !reasoning) {
    return (
      <motion.aside
        initial={false}
        animate={{ width: 300 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="h-full flex flex-col border-l border-border bg-card/60 overflow-hidden shrink-0"
      >
        <div className="flex items-center justify-between p-2 border-b border-border">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">
            How I Got This
          </span>
          <button onClick={onToggle} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground transition-colors ml-auto">
            <PanelRightClose className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          <Brain className="w-8 h-8 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground leading-relaxed max-w-[200px]">
            Ask a question to see how I analyzed your data
          </p>
        </div>
      </motion.aside>
    );
  }

  const data = reasoning!;

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 44 : 300 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="h-full flex flex-col border-l border-border bg-card/60 overflow-hidden shrink-0"
    >
      {/* Toggle */}
      <div className="flex items-center justify-between p-2 border-b border-border">
        {!collapsed && (
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">
            How I Got This
          </span>
        )}
        <button onClick={onToggle} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground transition-colors ml-auto">
          {collapsed ? <PanelRight className="w-4 h-4" /> : <PanelRightClose className="w-4 h-4" />}
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-4">
          {/* Reasoning Steps */}
          <Section icon={Brain} label="Intent" value={data.intent} color="text-primary" />
          <Section icon={Database} label="Data Used" value={data.dataUsed} color="text-chart-green" />
          <Section icon={Ruler} label="Metric" value={data.metric} color="text-chart-amber" />
          <Section icon={BarChart3} label="Method" value={data.method} color="text-chart-purple" />
          <Section icon={LineChart} label="Chart Type" value={data.chartType} color="text-primary" />

          {/* Stats */}
          {data.stats && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <ClipboardList className="w-3 h-3" />
                Statistics
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(data.stats).map(([k, v]) => (
                  <div key={k} className="bg-muted/50 rounded-md px-2 py-1.5">
                    <p className="text-[10px] text-muted-foreground uppercase">{k}</p>
                    <p className="text-sm font-semibold text-foreground">{typeof v === 'number' ? v.toLocaleString() : v}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Anomalies */}
          {data.anomalies && data.anomalies.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-chart-amber">
                <AlertTriangle className="w-3 h-3" />
                Anomalies
              </div>
              <div className="space-y-1">
                {data.anomalies.map((a, i) => (
                  <p key={i} className="text-xs text-muted-foreground bg-chart-amber/5 border border-chart-amber/10 rounded-md px-2 py-1.5">{a}</p>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          {data.recommendations && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-chart-green">
                <Lightbulb className="w-3 h-3" />
                Recommendation
              </div>
              <p className="text-xs text-muted-foreground bg-chart-green/5 border border-chart-green/10 rounded-md px-2 py-1.5 leading-relaxed">
                {data.recommendations}
              </p>
            </div>
          )}

          {/* Audit Log */}
          {data.auditLog && data.auditLog.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <ClipboardList className="w-3 h-3" />
                Audit Log
              </div>
              <div className="space-y-0.5">
                {data.auditLog.map((entry, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <ChevronRight className="w-3 h-3 mt-0.5 shrink-0 text-border" />
                    <span>{entry}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </motion.aside>
  );
}

function Section({ icon: Icon, label, value, color }: { icon: LucideIcon; label: string; value: string; color: string }) {
  return (
    <div className="space-y-1">
      <div className={`flex items-center gap-1.5 text-xs font-medium ${color}`}>
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <p className="text-sm text-foreground pl-4">{value}</p>
    </div>
  );
}
