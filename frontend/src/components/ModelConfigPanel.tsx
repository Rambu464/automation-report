"use client";

import React, { useEffect, useState } from "react";
import {
  Cpu,
  CheckCircle2,
  Circle,
  Save,
  ArrowUpRight,
  KeyRound,
  Building2,
} from "lucide-react";
import {
  SystemAIStatus,
  fetchSystemAIStatus,
  updateSystemAISettings,
} from "@/lib/api";

interface ModelConfigPanelProps {
  clientId: string;
  onGoSystemSettings: () => void;
  onGoClientConfig: (clientId: string) => void;
}

export default function ModelConfigPanel({
  clientId,
  onGoSystemSettings,
  onGoClientConfig,
}: ModelConfigPanelProps) {
  const [aiStatus, setAiStatus] = useState<SystemAIStatus | null>(null);
  const [preferredProvider, setPreferredProvider] = useState<string>("deepseek");
  const [useProPass3, setUseProPass3] = useState<boolean>(false);
  const [useCache, setUseCache] = useState<boolean>(true);
  const [batchSize, setBatchSize] = useState<number>(30);
  const [concurrency, setConcurrency] = useState<number>(5);
  const [saving, setSaving] = useState<boolean>(false);
  const [savedMsg, setSavedMsg] = useState<string>("");

  useEffect(() => {
    fetchSystemAIStatus()
      .then((status) => {
        setAiStatus(status);
        setBatchSize(status.ai_batch_size);
        setConcurrency(status.ai_max_concurrency);
        const firstActive = status.providers.find((p) => p.configured);
        if (firstActive) setPreferredProvider(firstActive.id);
      })
      .catch(() => setAiStatus(null));
  }, []);

  const handleSaveTuning = async () => {
    setSaving(true);
    setSavedMsg("");
    try {
      const updated = await updateSystemAISettings({
        ai_batch_size: batchSize,
        ai_max_concurrency: concurrency,
      });
      setAiStatus(updated);
      setSavedMsg("Parameter model & batch tersimpan.");
    } finally {
      setSaving(false);
    }
  };

  const configuredCount = aiStatus?.providers.filter((p) => p.configured).length ?? 0;

  return (
    <div className="space-y-4">
      {/* Provider Status Overview */}
      <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wide text-zinc-600">
            Status Cloud AI
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              configuredCount > 0
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            {configuredCount > 0 ? `${configuredCount} Provider Aktif` : "Pre-Clean Mode"}
          </span>
        </div>

        <div className="space-y-1.5">
          {(aiStatus?.providers || []).map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between rounded-lg bg-white px-2.5 py-1.5 text-xs shadow-2xs"
            >
              <div className="min-w-0">
                <div className="truncate font-semibold text-zinc-800">{p.name}</div>
                <div className="truncate font-mono text-[10px] text-zinc-400">{p.model}</div>
              </div>
              {p.configured ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Aktif
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[10px] text-zinc-400">
                  <Circle className="h-3 w-3" />
                  Kosong
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Model & Mode Settings */}
      <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-4">
        <div className="flex items-center gap-2 text-xs font-bold text-zinc-900">
          <Cpu className="h-4 w-4 text-blue-600" />
          Konfigurasi 3-Pass AI
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-zinc-600">
            Primary Model (Auto-Fallback Aktif)
          </label>
          <select
            value={preferredProvider}
            onChange={(e) => setPreferredProvider(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs focus:border-blue-600 focus:outline-none"
          >
            <option value="deepseek">DeepSeek-Chat (Primary • Termurah)</option>
            <option value="openrouter">Qwen 2.5 72B (OpenRouter)</option>
            <option value="groq">Llama 3.3 70B (Groq • Cepat)</option>
            <option value="gemini">Gemini 2.5 Flash (Google AI)</option>
          </select>
        </div>

        <div className="space-y-2 border-t border-zinc-100 pt-2.5">
          <label className="flex cursor-pointer items-center justify-between text-xs text-zinc-700">
            <span>Pass 3 Executive Summary pakai Pro</span>
            <input
              type="checkbox"
              checked={useProPass3}
              onChange={(e) => setUseProPass3(e.target.checked)}
              className="h-4 w-4 rounded text-blue-700"
            />
          </label>
          <label className="flex cursor-pointer items-center justify-between text-xs text-zinc-700">
            <span>Gunakan SQLite Batch Cache</span>
            <input
              type="checkbox"
              checked={useCache}
              onChange={(e) => setUseCache(e.target.checked)}
              className="h-4 w-4 rounded text-blue-700"
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3 border-t border-zinc-100 pt-2.5">
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-zinc-600">
              Batch Size (baris)
            </label>
            <input
              type="number"
              min={5}
              max={100}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value) || 30)}
              className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-zinc-600">
              Max Concurrency
            </label>
            <input
              type="number"
              min={1}
              max={12}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value) || 5)}
              className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs"
            />
          </div>
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={handleSaveTuning}
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-zinc-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-zinc-800 disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? "Menyimpan..." : "Simpan Parameter Model"}
        </button>

        {savedMsg && (
          <div className="flex items-center gap-1.5 rounded-lg bg-emerald-50 p-2 text-[11px] text-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>{savedMsg}</span>
          </div>
        )}
      </div>

      {/* Quick Shortcuts */}
      <div className="space-y-2 border-t border-zinc-200 pt-3">
        <button
          type="button"
          onClick={onGoSystemSettings}
          className="flex w-full items-center justify-between rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-xs font-semibold text-zinc-700 transition hover:border-blue-300 hover:text-blue-700"
        >
          <span className="inline-flex items-center gap-2">
            <KeyRound className="h-3.5 w-3.5 text-blue-600" />
            Atur API Keys (.env)
          </span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>

        <button
          type="button"
          onClick={() => onGoClientConfig(clientId)}
          className="flex w-full items-center justify-between rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-xs font-semibold text-zinc-700 transition hover:border-blue-300 hover:text-blue-700"
        >
          <span className="inline-flex items-center gap-2">
            <Building2 className="h-3.5 w-3.5 text-sky-600" />
            Config Klien ({clientId.toUpperCase()})
          </span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
