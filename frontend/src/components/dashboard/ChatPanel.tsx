import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Bot, User, Loader2, Sparkles, Mic, MicOff } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  chartConfig?: ChartConfig;
  reasoning?: ReasoningData;
  followUps?: string[];
}

export interface ChartConfig {
  type: "line" | "bar" | "scatter" | "table";
  title: string;
  data: any[];
  xKey?: string;
  yKey?: string;
}

export interface ReasoningData {
  intent: string;
  dataUsed: string;
  metric: string;
  method: string;
  chartType: string;
  summary?: string[];
  auditLog?: string[];
  anomalies?: string[];
  stats?: Record<string, number>;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
  onFollowUp: (question: string) => void;
}

const suggestedQueries = [
  "Compare Machine A vs Machine B",
  "Show trend of tensile strength over last 6 months",
  "Are there anomalies in force measurements?",
  "Does changing test speed affect maximum force?",
];

export function ChatPanel({ messages, isLoading, onSendMessage, onFollowUp }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const {
    transcript,
    interimTranscript,
    status,
    error: micError,
    isSupported: micSupported,
    start: startListening,
    stop: stopListening,
    reset: resetTranscript,
  } = useSpeechRecognition();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const isListening = status === "listening" || status === "processing";

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  useEffect(() => {
    if (transcript) {
      setInput((prev) => {
        const trimmed = transcript.trim();
        if (!trimmed) return prev;
        return prev.trim() ? `${prev.trim()} ${trimmed}` : trimmed;
      });
      resetTranscript();
    }
  }, [transcript, resetTranscript]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-8 h-8 text-primary" />
            </div>
            <div className="text-center space-y-2">
              <h2 className="text-xl font-semibold text-foreground">Material Testing AI Assistant</h2>
              <p className="text-sm text-muted-foreground max-w-md">
                Ask questions about your test data — compare machines, analyze trends, detect anomalies, and generate reports.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {suggestedQueries.map((q) => (
                <button
                  key={q}
                  onClick={() => onSendMessage(q)}
                  className="text-left px-3 py-2.5 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-secondary/50 transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-foreground"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm prose-invert max-w-none">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-muted-foreground" />
              </div>
            )}
          </motion.div>
        ))}

        {/* Follow-up suggestions */}
        {messages.length > 0 && messages[messages.length - 1]?.followUps && !isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap gap-2 pl-10"
          >
            {messages[messages.length - 1].followUps!.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowUp(q)}
                className="px-3 py-1.5 rounded-full border border-border text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 transition-all"
              >
                {q}
              </button>
            ))}
          </motion.div>
        )}

        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3 items-start"
          >
            <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div className="bg-secondary rounded-xl px-4 py-3 flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
              <span className="text-sm text-muted-foreground">Analyzing test data...</span>
            </div>
          </motion.div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-3">
        {/* Mic error */}
        {micError && (
          <div className="mb-2 px-2 text-xs text-chart-red bg-chart-red/5 border border-chart-red/10 rounded-md py-1.5">
            {micError}
          </div>
        )}

        <div className="flex items-center gap-2 bg-secondary rounded-xl px-3 py-1 focus-within:ring-1 focus-within:ring-primary/50 transition-all">
          {micSupported ? (
            <button
              onClick={handleMicClick}
              disabled={isLoading}
              title={isListening ? "Stop recording" : "Start voice input"}
              className={`shrink-0 p-2 rounded-lg transition-all ${
                isListening
                  ? "bg-chart-red/20 text-chart-red animate-pulse"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          ) : (
            <div
              title="Speech recognition not supported in this browser"
              className="shrink-0 p-2 rounded-lg text-muted-foreground/30"
            >
              <Mic className="w-4 h-4" />
            </div>
          )}

          <input
            value={input + (interimTranscript ? ` ${interimTranscript}` : "")}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Ask about your test data..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none py-2.5"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-2 rounded-lg bg-primary text-primary-foreground disabled:opacity-30 hover:opacity-90 transition-opacity"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
