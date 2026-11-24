"use client";

import React, { useEffect, useState } from "react";
import { KeyRound, Save, CheckCircle2, Circle, ShieldCheck } from "lucide-react";
import {
  SystemAIStatus,
  fetchSystemAIStatus,
  updateSystemAISettings,
} from "@/lib/api";

export default function SystemSettingsPanel() {
  const [status, setStatus] = useState<SystemAIStatus | null>(null);
  const [deepseekKey, setDeepseekKey] = useState<string>("");
  const [openrouterKey, setOpenrouterKey] = useState<string>("");
  const [groqKey, setGroqKey] = useState<string>("");
  const [geminiKey, setGeminiKey] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [msg, setMsg] = useState<string>("");

  useEffect(() => {
    fetchSystemAIStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const updated = await updateSystemAISettings({
        deepseek_api_key: deepseekKey || undefined,
        openrouter_api_key: openrouterKey || undefined,
        groq_api_key: groqKey || undefined,
        gemini_api_key: geminiKey || undefined,
      });
      setStatus(updated);
      setDeepseekKey("");
      setOpenrouterKey("");
      setGroqKey("");
      setGeminiKey("");
      setMsg("API Keys berhasil disimpan ke .env lokal & langsung aktif tanpa restart backend!");
    } finally {
      setSaving(false);
    }
  };

  const isSet = (id: string) =>
    status?.providers.find((p) => p.id === id)?.configured ?? false;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
            <KeyRound className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-zinc-900">Pengaturan Sistem &amp; Cloud AI API Keys</h1>
            <p className="text-xs text-zinc-500">
              API Key disimpan lokal di file <code>.env</code> (tidak pernah dikirim ke Git maupun ditampilkan kembali di layar).
            </p>
          </div>
        </div>
      </div>

      <form
        onSubmit={handleSave}
        className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs"
      >
        {[
          {
            id: "deepseek",
            label: "DeepSeek API Key (Primary — Rp 335–665/laporan)",
            placeholder: "sk-...",
            value: deepseekKey,
            setter: setDeepseekKey,
          },
          {
            id: "openrouter",
            label: "OpenRouter API Key (Secondary Fallback — Qwen 2.5 72B)",
            placeholder: "sk-or-...",
            value: openrouterKey,
            setter: setOpenrouterKey,
          },
          {
            id: "groq",
            label: "Groq API Key (Fast Fallback — Llama 3.3 70B Free Dev Tier)",
            placeholder: "gsk_...",
            value: groqKey,
            setter: setGroqKey,
          },
          {
            id: "gemini",
            label: "Google Gemini API Key (Backup — Gemini 2.5 Flash Free Tier)",
            placeholder: "AIza...",
            value: geminiKey,
            setter: setGeminiKey,
          },
        ].map((field) => (
          <div key={field.id} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-700">{field.label}</label>
              {isSet(field.id) ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                  <CheckCircle2 className="h-3 w-3" />
                  Terpasang di .env
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-500">
                  <Circle className="h-3 w-3" />
                  Belum diset
                </span>
              )}
            </div>
            <input
              type="password"
              value={field.value}
              onChange={(e) => field.setter(e.target.value)}
              placeholder={isSet(field.id) ? "•••••••••••••••• (isi hanya jika ingin mengganti)" : field.placeholder}
              className="w-full rounded-xl border border-zinc-300 px-3.5 py-2 text-xs focus:border-blue-600 focus:outline-none"
            />
          </div>
        ))}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-4">
          <span className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            Tersimpan lokal di .env (aman untuk screen-share)
          </span>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? "Menyimpan..." : "Simpan API Keys"}
          </button>
        </div>

        {msg && (
          <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-xs font-medium text-emerald-800">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{msg}</span>
          </div>
        )}
      </form>
    </div>
  );
}
