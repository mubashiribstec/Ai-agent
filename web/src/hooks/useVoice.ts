import { useRef, useState } from "react";

// Browser-native voice: streaming speech-to-text (SpeechRecognition) plus
// sentence-by-sentence text-to-speech (SpeechSynthesis). Zero backend deps;
// everything degrades to `supported === false` where the APIs are missing
// (e.g. Firefox without SpeechRecognition, or a headless test runner).
interface Handlers { onFinal?: (text: string) => void; onSpeechStart?: () => void; }

export function useVoice() {
  const supported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window) &&
    "speechSynthesis" in window;

  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const recRef = useRef<any>(null);
  const want = useRef(false);
  const handlers = useRef<Handlers>({});
  const buf = useRef("");

  const ensure = () => {
    if (recRef.current) return recRef.current;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = navigator.language || "en-US";
    rec.onresult = (e: any) => {
      let fin = "", intr = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) fin += r[0].transcript; else intr += r[0].transcript;
      }
      setInterim(intr);
      if (fin.trim()) { setInterim(""); handlers.current.onFinal?.(fin.trim()); }
    };
    rec.onspeechstart = () => handlers.current.onSpeechStart?.();
    rec.onend = () => {
      if (want.current) { try { rec.start(); } catch { /* already starting */ } }
      else setListening(false);
    };
    recRef.current = rec;
    return rec;
  };

  const startListening = (h: Handlers) => {
    if (!supported) return;
    handlers.current = h;
    want.current = true;
    setListening(true);
    try { ensure().start(); } catch { /* already running */ }
  };
  const stopListening = () => {
    want.current = false;
    setListening(false);
    try { recRef.current?.stop(); } catch { /* not running */ }
  };

  // ── streaming TTS ──────────────────────────────────────────────────────────
  const speak = (sentence: string) => {
    if (!supported || !sentence.trim()) return;
    const u = new SpeechSynthesisUtterance(sentence.trim());
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
  };
  // Feed streaming assistant tokens; speak each complete sentence as it lands.
  const feed = (text: string) => {
    buf.current += text;
    const parts = buf.current.split(/(?<=[.!?])\s+/);
    while (parts.length > 1) speak(parts.shift() as string);
    buf.current = parts[0] || "";
  };
  const flush = () => { const rest = buf.current; buf.current = ""; speak(rest); };
  const cancelSpeak = () => { buf.current = ""; try { window.speechSynthesis.cancel(); } catch { /* noop */ } };

  return { supported, listening, interim, startListening, stopListening, feed, flush, cancelSpeak };
}
