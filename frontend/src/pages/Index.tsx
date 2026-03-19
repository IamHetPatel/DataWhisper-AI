import { useState, useCallback } from "react";
import { LeftSidebar } from "@/components/dashboard/LeftSidebar";
import { ChatPanel, type ChatMessage, type ChartConfig, type ReasoningData } from "@/components/dashboard/ChatPanel";
import { ChartDisplay } from "@/components/dashboard/ChartDisplay";
import { ReasoningPanel } from "@/components/dashboard/ReasoningPanel";
import { ReportModal } from "@/components/dashboard/ReportModal";
import { v4 as uuidv4 } from "uuid";
// Simulated AI responses for demo
const demoResponses: Record<string, { content: string; chartConfig?: ChartConfig; reasoning?: ReasoningData; followUps: string[] }> = {
  default: {
    content: "Based on your test data, I've analyzed **847 tensile test records** from the past 6 months.\n\nThe mean maximum force across all specimens is **714.2 N** (σ = 18.7 N). Machine A shows slightly higher consistency with a CV of 2.4% compared to Machine B's 2.9%.\n\nI've plotted the force-strain curve for the latest batch below.",
    followUps: ["Compare last 7 days?", "Check anomalies?", "Filter by material?", "Compare another machine?"],
    reasoning: {
      intent: "Trend Analysis",
      dataUsed: "Tests, Values (last 6 months)",
      metric: "Maximum Force (N)",
      method: "Mean, Std Dev, Linear Regression",
      chartType: "Area Chart",
      auditLog: ["Queried tests — 847 records", "Filtered Oct 2025 – Mar 2026", "Joined values on test_id", "Computed statistics", "Generated trend line"],
      anomalies: ["Sample #412 — force 45% below mean", "Machine B batch Dec-15 — elevated std dev"],
      recommendations: "Inspect Machine B calibration logs for December. Re-test sample #412.",
      stats: { mean: 714.2, std: 18.7, count: 847, min: 392, max: 745 },
    },
  },
  compare: {
    content: "**Machine A vs Machine B — Comparison Complete**\n\nAcross 5 matched sample pairs:\n- Machine A mean: **717.6 N**\n- Machine B mean: **701.0 N**\n\nMachine A delivers **2.4% higher** maximum force on average. The difference is statistically significant (p < 0.05).",
    chartConfig: { type: "bar", title: "Maximum Force Comparison (Machine A vs B)", data: [], xKey: "name", yKey: "machineA" },
    followUps: ["Show individual samples?", "Check Machine B calibration?", "Run t-test details?", "Filter by material type?"],
    reasoning: {
      intent: "Comparison",
      dataUsed: "Tests (Machine A, Machine B)",
      metric: "Maximum Force (N)",
      method: "Paired comparison, t-test",
      chartType: "Bar Chart",
      auditLog: ["Selected matched pairs", "Computed per-machine stats", "Ran paired t-test (p=0.032)", "Generated comparison chart"],
      anomalies: [],
      recommendations: "Machine B shows consistent under-performance. Schedule calibration check.",
      stats: { "A mean": 717.6, "B mean": 701.0, "p-value": 0.032, delta: 16.6, pairs: 5 },
    },
  },
};

function getResponse(query: string) {
  const lower = query.toLowerCase();
  if (lower.includes("compare") || lower.includes("machine")) return demoResponses.compare;
  return demoResponses.default;
}

export default function Index() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeChart, setActiveChart] = useState<ChartConfig | null>(null);
  const [activeReasoning, setActiveReasoning] = useState<ReasoningData | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: text, context: {} }),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      
      // Map FastAPI InsightResponse to UI Format
      // data: { summary_3_sentences: [], anomaly_notes: [], recommendation: "", follow_up_questions: [], chart_config: {}, audit_log: [] }
      
      const markdownContent = data.summary_3_sentences.join(" ") + 
                              "\n\n**Recommendation:** " + data.recommendation;

      let extractedStats = undefined;
      if (data.chart_data && data.chart_data.length > 0) {
        const firstRow = data.chart_data[0];
        if (firstRow && typeof firstRow.mean === "number") {
          extractedStats = {
            mean: firstRow.mean,
            std: firstRow.stdDev,
            count: firstRow.count,
            min: firstRow.min,
            max: firstRow.max,
          };
        } else if (firstRow && typeof firstRow.total === "number") {
          extractedStats = { total: firstRow.total };
        }
      }

      const getAuditVal = (prefix: string, def: string) => {
        const log = data.audit_log?.find((l: string) => l.startsWith(prefix));
        return log ? log.replace(prefix, "").trim() : def;
      };

      const uiReasoning: ReasoningData = {
        intent: getAuditVal("Intent:", "Backend Analysis"),
        dataUsed: "Live MongoDB Data",
        metric: getAuditVal("Metrics:", "Auto-computed"),
        method: getAuditVal("Operation:", "LangChain Pipeline"),
        chartType: data.chart_config?.type || "Dynamic",
        auditLog: data.audit_log,
        anomalies: data.anomaly_notes,
        recommendations: data.recommendation,
        stats: extractedStats, // dynamically populated from MongoDB rows!
      };

      const chartConfigObj = Object.keys(data.chart_config).length > 0
        ? { ...data.chart_config, data: data.chart_data || [] } as ChartConfig
        : undefined;

      const aiMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: markdownContent,
        timestamp: new Date(),
        chartConfig: chartConfigObj,
        reasoning: uiReasoning,
        followUps: data.follow_up_questions,
      };

      setMessages((prev) => [...prev, aiMsg]);
      if (aiMsg.chartConfig) setActiveChart(aiMsg.chartConfig);
      setActiveReasoning(uiReasoning);

    } catch (error) {
      console.error("Fetch failed:", error);
      const errorMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: "🚨 Failed to connect to the backend API (" + import.meta.env.VITE_API_URL + "/query). Please ensure the FastAPI server is running.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleQuerySelect = (query: string) => {
    if (query) handleSendMessage(query);
  };

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <LeftSidebar collapsed={leftCollapsed} onToggle={() => setLeftCollapsed((c) => !c)} onQuerySelect={handleQuerySelect} />

      {/* Center: Chat + Charts */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Chat area */}
        <div className="flex-1 min-h-0">
          <ChatPanel messages={messages} isLoading={isLoading} onSendMessage={handleSendMessage} onFollowUp={handleSendMessage} />
        </div>

        {/* Chart area */}
        {activeChart && (
          <div className="border-t border-border p-4 shrink-0 flex flex-col min-h-0" style={{ maxHeight: "55%" }}>
            <div className="flex-1 overflow-y-auto scrollbar-thin rounded-xl">
              <ChartDisplay chart={activeChart} onGenerateReport={() => setReportOpen(true)} />
            </div>
          </div>
        )}
      </div>

      <ReasoningPanel reasoning={activeReasoning} collapsed={rightCollapsed} onToggle={() => setRightCollapsed((c) => !c)} />
      <ReportModal open={reportOpen} onClose={() => setReportOpen(false)} reasoning={activeReasoning} chart={activeChart} />
    </div>
  );
}
