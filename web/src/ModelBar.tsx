import { useEffect, useState } from "react";
import { ModelPreset, getModels } from "./api";

export interface GenChoice {
  model: string;
  effort: string;
  thinking: boolean;
}

export function ModelBar({ value, onChange }:
  { value: GenChoice; onChange: (c: GenChoice) => void }) {
  const [models, setModels] = useState<ModelPreset[]>([]);

  useEffect(() => {
    getModels().then((r) => {
      setModels(r.models);
      if (!value.model && r.active) onChange({ ...value, model: r.active });
    }).catch(() => {});
  }, []);

  return (
    <div className="modelbar">
      <select value={value.model} onChange={(e) => {
        const p = models.find((m) => m.model === e.target.value);
        onChange({ model: e.target.value, effort: p?.effort ?? value.effort,
                   thinking: p?.thinking ?? value.thinking });
      }}>
        {models.length === 0 && <option value={value.model}>{value.model || "model"}</option>}
        {models.map((m) => <option key={m.model} value={m.model}>{m.label}</option>)}
      </select>

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
