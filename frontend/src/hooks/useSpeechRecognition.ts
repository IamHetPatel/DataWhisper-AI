import { useState, useRef, useCallback, useEffect } from "react";

export type SpeechStatus = "idle" | "listening" | "processing" | "error";

export interface UseSpeechRecognitionReturn {
  transcript: string;
  interimTranscript: string;
  status: SpeechStatus;
  error: string | null;
  isSupported: boolean;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const SpeechRecognition =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  const isSupported = !!SpeechRecognition;

  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [status, setStatus] = useState<SpeechStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const stop = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setStatus("idle");
  }, []);

  const reset = useCallback(() => {
    stop();
    setTranscript("");
    setInterimTranscript("");
    setError(null);
  }, [stop]);

  const start = useCallback(() => {
    if (!SpeechRecognition) {
      setError("Speech recognition is not supported in this browser.");
      setStatus("error");
      return;
    }

    reset();

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setStatus("listening");
      setError(null);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      setStatus("processing");
      let final = "";
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript + " ";
        } else {
          interim += result[0].transcript;
        }
      }

      if (final) {
        setTranscript((prev) => (prev + final).trim());
      }
      setInterimTranscript(interim);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech") {
        setStatus("idle");
        return;
      }
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        setError("Microphone access denied. Please allow microphone access in your browser settings.");
        setStatus("error");
      } else {
        setError(`Speech recognition error: ${event.error}`);
        setStatus("error");
      }
    };

    recognition.onend = () => {
      setInterimTranscript("");
      if (status !== "error") {
        setStatus("idle");
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [SpeechRecognition, reset, status]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  return {
    transcript,
    interimTranscript,
    status,
    error,
    isSupported,
    start,
    stop,
    reset,
  };
}
