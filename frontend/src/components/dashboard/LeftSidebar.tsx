import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Clock,
  Bookmark,
  Plus,
  ChevronLeft,
  Activity,
  FlaskConical,
  Gauge,
  TrendingUp,
} from "lucide-react";

const recentQueries = [
  { id: 1, text: "Compare Machine A vs Machine B", icon: Activity, time: "2m ago" },
  { id: 2, text: "Tensile strength trend — 6 months", icon: TrendingUp, time: "15m ago" },
  { id: 3, text: "Anomalies in force measurements", icon: Gauge, time: "1h ago" },
  { id: 4, text: "Test speed vs maximum force", icon: FlaskConical, time: "3h ago" },
];

const savedTemplates = [
  { id: 1, text: "Machine Comparison Report", icon: Activity },
  { id: 2, text: "Monthly QC Summary", icon: Gauge },
  { id: 3, text: "Material Batch Analysis", icon: FlaskConical },
];

interface LeftSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onQuerySelect: (query: string) => void;
}

export function LeftSidebar({ collapsed, onToggle, onQuerySelect }: LeftSidebarProps) {
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
          onClick={() => onQuerySelect("")}
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
              {recentQueries.map((q) => (
                <button
                  key={q.id}
                  onClick={() => onQuerySelect(q.text)}
                  className="w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors group"
                >
                  <q.icon className="w-3.5 h-3.5 mt-0.5 shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate">{q.text}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{q.time}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Saved Templates */}
          <div>
            <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Bookmark className="w-3 h-3" />
              Templates
            </div>
            <div className="space-y-0.5">
              {savedTemplates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => onQuerySelect(t.text)}
                  className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors group"
                >
                  <t.icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
                  <span className="truncate">{t.text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
}
