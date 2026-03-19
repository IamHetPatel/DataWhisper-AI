import { useState, useCallback } from "react";
import { LeftSidebar } from "@/components/dashboard/LeftSidebar";
import { ChatPanel, type ChatMessage, type ChartConfig, type ReasoningData } from "@/components/dashboard/ChatPanel";
import { ChartDisplay } from "@/components/dashboard/ChartDisplay";
import { ReasoningPanel } from "@/components/dashboard/ReasoningPanel";
import { ReportModal } from "@/components/dashboard/ReportModal";
import { v4 as uuidv4 } from "uuid";

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
      const conversationHistory = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await fetch(`${import.meta.env.VITE_API_URL}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: text, context: {}, conversation_history: conversationHistory }),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();

      const markdownContent = data.summary_3_sentences.join(" ") +
                              "\n\n**Recommendation:** " + data.recommendation;

      let extractedStats: Record<string, number> | undefined = undefined;
      if (data.stats_summary && Object.keys(data.stats_summary).length > 0) {
        const ss = data.stats_summary;
        if (ss.group_comparison) {
          const gc = ss.group_comparison;
          extractedStats = {
            "group 1": gc.mean_1,
            "group 2": gc.mean_2,
            delta: gc.difference,
            "p-value": gc.p_value,
          };
        } else if (ss.drift) {
          extractedStats = {
            slope: ss.drift.slope,
            "p-value": ss.drift.p_value,
          };
        }
      }
      if (!extractedStats && data.chart_data && data.chart_data.length > 0) {
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
        summary: data.summary_3_sentences,
        auditLog: data.audit_log,
        anomalies: data.anomaly_notes,
        recommendations: data.recommendation,
        stats: extractedStats,
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
  }, [messages]);

  const handleQuerySelect = (query: string) => {
    if (query) handleSendMessage(query);
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveChart(null);
    setActiveReasoning(null);
  };

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <LeftSidebar collapsed={leftCollapsed} onToggle={() => setLeftCollapsed((c) => !c)} onQuerySelect={handleQuerySelect} onNewChat={handleNewChat} />

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
