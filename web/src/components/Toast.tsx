import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";

type Kind = "info" | "success" | "error";
interface Toast { id: number; kind: Kind; msg: string; }

const ToastCtx = createContext<(msg: string, kind?: Kind) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

const ICON = { info: Info, success: CheckCircle2, error: XCircle };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((msg: string, kind: Kind = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, msg }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts">
        {items.map((t) => {
          const I = ICON[t.kind];
          return (
            <div key={t.id} className={`toast-item ${t.kind}`}>
              <I size={17} /> <span>{t.msg}</span>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}
