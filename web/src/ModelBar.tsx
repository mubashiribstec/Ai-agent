import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { ModelPreset, getModels } from "./api";

export interface GenChoice {
  model: string;
  effort: string;
  thinking: boolean;
}

const PROVIDER_LABEL: Record<string, string> = {
  ollama: "Ollama", openai: "OpenAI", anthropic: "Anthropic", gemini: "Gemini",
  openrouter: "OpenRouter", "claude-cli": "Claude (subscription)",
};

export function ModelBar({ value, onChange }:
  { value: GenChoice; onChange: (c: GenChoice) => void }) {
  const [models, setModels] = useState<ModelPreset[]>([]);

  useEffect(() => {
    getModels().then((r) => {
      setModels(r.models);
      if (!value.model && r.active) onChange({ ...value, model: r.active });
    }).catch(() => {});
  }, []);

  const [provider, ...rest] = (value.model || "").split(":");
  const modelName = rest.join(":") || value.model;
  const inList = models.some((m) => m.model === value.model);

  return (
    <div className="modelbar">
      <span className="badge" title="active provider">
        <Cpu size={13} /> {PROVIDER_LABEL[provider] ?? provider ?? "model"}
      </span>
      <select value={value.model} onChange={(e) => {
        const p = models.find((m) => m.model === e.target.value);
        onChange({ model: e.target.value, effort: p?.effort ?? value.effort,
                   thinking: p?.thinking ?? value.thinking });
      }}>
        {!inList && value.model && <option value={value.model}>{modelName}</option>}
        {models.map((m) => <option key={m.model} value={m.model}>{m.label}</option>)}
      </select>
      <span className="dim mono" style={{ fontSize: 12 }}>{modelName}</span>

      <label className="eff">effort
        <select value={value.effort} onChange={(e) => onChange({ ...value, effort: e.target.value })}>
          {["off", "low", "medium", "high"].map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
      </label>
      <label className="think">
        <input type="checkbox" checked={value.thinking}
               onChange={(e) => onChange({ ...value, thinking: e.target.checked })} />
        thinking
      </label>
    </div>
  );
}
