import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Clock,
  Bookmark,
  Plus,
  ChevronLeft,
  Activity,
  FlaskConical,
  Gauge,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

interface SavedQuery {
  id: string;
  question: string;
  intent: string;
  created_at: string;
  row_count: number;
}

const INTENT_ICON: Record<string, LucideIcon> = {
  comparison: Activity,
  trend_drift: TrendingUp,
  anomaly_check: Gauge,
  hypothesis: FlaskConical,
  lookup: Activity,
  summary: FlaskConical,
  validation_compliance: Gauge,
};

const DEFAULT_RECENT: SavedQuery[] = [
  { id: "demo1", question: "Compare Machine A vs Machine B", intent: "comparison", created_at: "", row_count: 0 },
  { id: "demo2", question: "Tensile strength trend — 6 months", intent: "trend_drift", created_at: "", row_count: 0 },
  { id: "demo3", question: "Anomalies in force measurements", intent: "anomaly_check", created_at: "", row_count: 0 },
  { id: "demo4", question: "Test speed vs maximum force", intent: "hypothesis", created_at: "", row_count: 0 },
];

const DEFAULT_TEMPLATES: SavedQuery[] = [
  { id: "tmpl1", question: "Machine Comparison Report", intent: "comparison", created_at: "", row_count: 0 },
  { id: "tmpl2", question: "Monthly QC Summary", intent: "summary", created_at: "", row_count: 0 },
  { id: "tmpl3", question: "Material Batch Analysis", intent: "lookup", created_at: "", row_count: 0 },
];

interface LeftSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onQuerySelect: (query: string) => void;
  onNewChat: () => void;
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return "";
  }
}

export function LeftSidebar({ collapsed, onToggle, onQuerySelect, onNewChat }: LeftSidebarProps) {
  const [recent, setRecent] = useState<SavedQuery[]>(DEFAULT_RECENT);
  const [templates, setTemplates] = useState<SavedQuery[]>(DEFAULT_TEMPLATES);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL}/queries/templates`)
      .then((r) => r.ok ? r.json() : null)
      .then((data: SavedQuery[] | null) => {
        if (data && data.length > 0) {
          setRecent(data.slice(0, 4));
          if (data.length > 4) setTemplates(data.slice(4, 7));
        }
      })
      .catch(() => {});
  }, []);

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 56 : 280 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="h-full flex flex-col border-r border-border bg-sidebar overflow-hidden shrink-0"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2"
            >
              <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center">
                <FlaskConical className="w-4 h-4 text-primary" />
              </div>
              <span className="text-sm font-semibold text-foreground tracking-tight">ZwickRoell AI</span>
            </motion.div>
          )}
        </AnimatePresence>
        <button onClick={onToggle} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground transition-colors">
          <ChevronLeft className={`w-4 h-4 transition-transform ${collapsed ? "rotate-180" : ""}`} />
        </button>
      </div>

      {/* New Chat */}
      <div className="p-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-all text-sm"
        >
          <Plus className="w-4 h-4" />
          {!collapsed && <span>New Analysis</span>}
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3 space-y-4">
          {/* Recent Queries */}
          <div>
            <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Clock className="w-3 h-3" />
              Recent
            </div>
            <div className="space-y-0.5">
              {recent.map((q) => {
                const Icon = INTENT_ICON[q.intent] ?? Activity;
                const time = timeAgo(q.created_at);
                return (
                  <button
                    key={q.id}
                    onClick={() => onQuerySelect(q.question)}
                    className="w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors group"
                  >
                    <Icon className="w-3.5 h-3.5 mt-0.5 shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate">{q.question}</p>
                      {time && <p className="text-xs text-muted-foreground mt-0.5">{time}</p>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Saved Templates */}
          <div>
            <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Bookmark className="w-3 h-3" />
              Templates
            </div>
            <div className="space-y-0.5">
              {templates.map((t) => {
                const Icon = INTENT_ICON[t.intent] ?? FlaskConical;
                return (
                  <button
                    key={t.id}
                    onClick={() => onQuerySelect(t.question)}
                    className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors group"
                  >
                    <Icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
                    <span className="truncate">{t.question}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
}
