"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Cpu,
  Check,
  CheckCircle2,
  Save,
  ArrowUpRight,
  KeyRound,
  Building2,
  ChevronDown,
  ChevronRight,
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
  const [batchSize, setBatchSize] = useState<number>(30);
  const [concurrency, setConcurrency] = useState<number>(5);
  const [saving, setSaving] = useState<boolean>(false);
  const [reordering, setReordering] = useState<boolean>(false);
  const [dropdownOpen, setDropdownOpen] = useState<boolean>(false);
  const [orderMsg, setOrderMsg] = useState<string>("");
  const [savedMsg, setSavedMsg] = useState<string>("");
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchSystemAIStatus()
      .then((status) => {
        setAiStatus(status);
        setBatchSize(status.ai_batch_size);
        setConcurrency(status.ai_max_concurrency);
      })
      .catch(() => setAiStatus(null));
  }, []);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const handleSelectPrimary = async (providerId: string) => {
    if (!aiStatus || reordering) return;
    setDropdownOpen(false);
    const picked = aiStatus.providers.find((p) => p.id === providerId);
    if (!picked) return;
    const rest = aiStatus.providers.filter((p) => p.id !== providerId);
    const nextProviders = [picked, ...rest];
    const nextOrder = nextProviders.map((p) => p.id);

    setAiStatus({ ...aiStatus, providers: nextProviders, provider_order: nextOrder });
    setReordering(true);
    setOrderMsg("");
    try {
      const updated = await updateSystemAISettings({ ai_provider_order: nextOrder });
      setAiStatus(updated);
      setOrderMsg(`Primary diubah ke ${picked.name}.`);
    } catch {
      fetchSystemAIStatus().then(setAiStatus).catch(() => null);
    } finally {
      setReordering(false);
    }
  };

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

  const providers = aiStatus?.providers || [];
  const configuredCount = providers.filter((p) => p.configured).length;
  const selectedPrimary = providers[0] || null;

  return (
    <div className="space-y-4">
      {/* Modern Custom Model Dropdown Selector */}
      <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wide text-zinc-600">
            Model Cloud AI
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              configuredCount > 0
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            {configuredCount > 0 ? `${configuredCount} Aktif` : "Pre-Clean Mode"}
          </span>
        </div>

        <div ref={dropdownRef} className="relative">
          <button
            type="button"
            disabled={reordering || !aiStatus}
            onClick={() => setDropdownOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-2 rounded-xl border border-zinc-300 bg-white px-3 py-2 text-left transition hover:border-blue-400 focus:border-blue-600 focus:outline-none disabled:opacity-60"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-xs font-semibold text-zinc-900">
                  {selectedPrimary ? selectedPrimary.name : "Memuat model..."}
                </span>
                {selectedPrimary && (
                  <span
                    className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      selectedPrimary.configured
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-zinc-100 text-zinc-500"
                    }`}
                  >
                    {selectedPrimary.configured ? "Aktif" : "Key Kosong"}
                  </span>
                )}
              </div>
              {selectedPrimary && (
                <div className="truncate font-mono text-[10px] text-zinc-400">
                  {selectedPrimary.model}
                </div>
              )}
            </div>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-zinc-400 transition ${
                dropdownOpen ? "rotate-180" : ""
              }`}
            />
          </button>

          {/* Popover Menu */}
          {dropdownOpen && (
            <div className="absolute left-0 right-0 z-30 mt-1.5 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-lg">
              <div className="border-b border-zinc-100 px-3 py-2 text-[11px] font-semibold text-zinc-400">
                Model
              </div>
              <div className="divide-y divide-zinc-50 py-1">
                {providers.map((p, idx) => {
                  const isSelected = idx === 0;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectPrimary(p.id)}
                      className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition hover:bg-zinc-50 ${
                        isSelected ? "bg-blue-50/40" : ""
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`truncate text-xs ${
                              isSelected
                                ? "font-bold text-zinc-900"
                                : "font-medium text-zinc-700"
                            }`}
                          >
                            {p.name}
                          </span>
                          <span
                            className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                              p.configured
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-zinc-100 text-zinc-500"
                            }`}
                          >
                            {p.configured ? "Aktif" : "Kosong"}
                          </span>
                        </div>
                        <div className="truncate font-mono text-[10px] text-zinc-400">
                          {p.model}
                        </div>
                      </div>
                      {isSelected ? (
                        <Check className="h-3.5 w-3.5 shrink-0 text-blue-600" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-zinc-300" />
                      )}
                    </button>
                  );
                })}
              </div>
              <button
                type="button"
                onClick={() => {
                  setDropdownOpen(false);
                  onGoSystemSettings();
                }}
                className="flex w-full items-center justify-between border-t border-zinc-100 px-3 py-2 text-xs font-medium text-zinc-600 transition hover:bg-zinc-50 hover:text-zinc-900"
              >
                <span className="inline-flex items-center gap-1.5">
                  <KeyRound className="h-3.5 w-3.5 text-zinc-400" />
                  Kelola API Keys
                </span>
                <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />
              </button>
            </div>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-zinc-400">
          <span>Model lain yang aktif otomatis menjadi fallback.</span>
          {orderMsg && <span className="font-semibold text-emerald-600">{orderMsg}</span>}
        </div>
      </div>

      {/* Batch & Concurrency Tuning */}
      <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-4">
        <div className="flex items-center gap-2 text-xs font-bold text-zinc-900">
          <Cpu className="h-4 w-4 text-blue-600" />
          Parameter Batch 3-Pass AI
        </div>

        <div className="grid grid-cols-2 gap-3">
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

      {/* Quick Shortcut */}
      <div className="border-t border-zinc-200 pt-3">
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
