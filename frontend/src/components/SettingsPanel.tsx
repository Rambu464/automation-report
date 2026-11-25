"use client";

import React, { useEffect, useState } from "react";
import { Plus, Trash2, Save, Upload, CheckCircle2, AlertCircle, Presentation, Building2, BookOpenCheck, FileJson, Sparkles } from "lucide-react";
import {
  ClientConfigData,
  NewstrendBriefData,
  SentimentBriefData,
  fetchClientConfig,
  importMediaMaster,
  updateClientConfig,
  uploadClientPptxTemplate,
} from "@/lib/api";

interface SettingsPanelProps {
  clientId: string;
}

export default function SettingsPanel({ clientId }: SettingsPanelProps) {
  const [config, setConfig] = useState<ClientConfigData | null>(null);
  const [newColName, setNewColName] = useState<string>("");
  const [newColDesc, setNewColDesc] = useState<string>("");
  const [cfgMsg, setCfgMsg] = useState<string>("");

  // Media Master Import
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [tierKey, setTierKey] = useState<string>(clientId);
  const [mediaMsg, setMediaMsg] = useState<string>("");

  // PPTX Template Upload
  const [pptxFile, setPptxFile] = useState<File | null>(null);
  const [pptxMsg, setPptxMsg] = useState<string>("");
  const [pptxErr, setPptxErr] = useState<string>("");

  // Sentiment Brief (POV Klien)
  const [showJsonImport, setShowJsonImport] = useState<boolean>(false);
  const [rawBriefJson, setRawBriefJson] = useState<string>("");
  const [briefTab, setBriefTab] = useState<"negative" | "neutral" | "positive">("negative");
  const [newRuleText, setNewRuleText] = useState<string>("");
  const [briefMsg, setBriefMsg] = useState<string>("");
  const [briefErr, setBriefErr] = useState<string>("");

  // Newstrend Creation Brief
  const [showNtJsonImport, setShowNtJsonImport] = useState<boolean>(false);
  const [rawNtJson, setRawNtJson] = useState<string>("");
  const [newExContext, setNewExContext] = useState<string>("");
  const [newExPattern, setNewExPattern] = useState<string>("");
  const [ntMsg, setNtMsg] = useState<string>("");
  const [ntErr, setNtErr] = useState<string>("");

  useEffect(() => {
    setTierKey(clientId);
    setCfgMsg("");
    setMediaMsg("");
    setPptxMsg("");
    setPptxErr("");
    fetchClientConfig(clientId)
      .then(setConfig)
      .catch(() => setConfig(null));
  }, [clientId]);

  const handleAddAdhoc = () => {
    if (!config || !newColName.trim() || !newColDesc.trim()) return;
    setConfig({
      ...config,
      adhoc_columns: [
        ...(config.adhoc_columns || []),
        { name: newColName.trim(), description: newColDesc.trim() },
      ],
    });
    setNewColName("");
    setNewColDesc("");
    setCfgMsg("");
  };

  const handleRemoveAdhoc = (name: string) => {
    if (!config) return;
    setConfig({
      ...config,
      adhoc_columns: config.adhoc_columns.filter((c) => c.name !== name),
    });
    setCfgMsg("");
  };

  const handleSaveConfig = async () => {
    if (!config) return;
    const saved = await updateClientConfig(clientId, config);
    setConfig(saved);
    setCfgMsg("Konfigurasi klien & kolom Ad-Hoc berhasil disimpan ke config.yaml.");
  };

  const handleImportMedia = async () => {
    if (!mediaFile) return;
    const res = await importMediaMaster(mediaFile, tierKey);
    setMediaMsg(
      `Berhasil mengimpor/memperbarui ${res.records_upserted} domain ke SQLite media_master_hypestat.`
    );
    setMediaFile(null);
  };

  const handleUploadPptx = async () => {
    if (!pptxFile) return;
    setPptxErr("");
    setPptxMsg("");
    try {
      const res = await uploadClientPptxTemplate(clientId, pptxFile);
      setPptxMsg(
        `Template PPTX berhasil disimpan ke ${res.template_path} (${(res.size_bytes / 1024).toFixed(1)} KB).`
      );
      setPptxFile(null);
    } catch (err) {
      setPptxErr(err instanceof Error ? err.message : "Gagal mengunggah template PPTX.");
    }
  };

  const currentBrief: SentimentBriefData = config?.sentiment_brief || {
    brief_uuid: "",
    deskripsi: "",
    analyst_verdict: "",
    negative_guidelines: [],
    neutral_guidelines: [],
    positive_guidelines: [],
    output_rules: [],
  };

  const updateBrief = (patch: Partial<SentimentBriefData>) => {
    if (!config) return;
    setConfig({
      ...config,
      sentiment_brief: { ...currentBrief, ...patch },
    });
    setBriefMsg("");
  };

  const handleImportBriefJson = () => {
    if (!config || !rawBriefJson.trim()) return;
    setBriefErr("");
    setBriefMsg("");
    try {
      const parsed = JSON.parse(rawBriefJson);
      const instr = parsed.instructions || parsed;
      const dedupe = (arr: unknown): string[] =>
        Array.isArray(arr)
          ? Array.from(new Set(arr.map((x) => String(x).trim()).filter(Boolean)))
          : [];

      const imported: SentimentBriefData = {
        brief_uuid: String(parsed.brief_uuid || currentBrief.brief_uuid || ""),
        deskripsi: String(parsed.deskripsi || currentBrief.deskripsi || ""),
        analyst_verdict: String(instr.analyst_verdict || ""),
        negative_guidelines: dedupe(instr.negative_guidelines),
        neutral_guidelines: dedupe(instr.neutral_guidelines),
        positive_guidelines: dedupe(instr.positive_guidelines),
        output_rules: dedupe(instr.output_rules),
      };
      setConfig({ ...config, sentiment_brief: imported });
      setRawBriefJson("");
      setShowJsonImport(false);
      setBriefMsg(
        `JSON berhasil diimpor (${imported.negative_guidelines.length} Neg, ${imported.neutral_guidelines.length} Neu, ${imported.positive_guidelines.length} Pos). Klik Simpan Brief untuk menyimpan ke config.yaml.`
      );
    } catch {
      setBriefErr("Format JSON tidak valid. Pastikan JSON utuh dari tanda { sampai }.");
    }
  };

  const handleAddBriefRule = () => {
    if (!newRuleText.trim()) return;
    const key =
      briefTab === "negative"
        ? "negative_guidelines"
        : briefTab === "neutral"
        ? "neutral_guidelines"
        : "positive_guidelines";
    updateBrief({ [key]: [...currentBrief[key], newRuleText.trim()] });
    setNewRuleText("");
  };

  const handleRemoveBriefRule = (idx: number) => {
    const key =
      briefTab === "negative"
        ? "negative_guidelines"
        : briefTab === "neutral"
        ? "neutral_guidelines"
        : "positive_guidelines";
    updateBrief({ [key]: currentBrief[key].filter((_, i) => i !== idx) });
  };

  const handleSaveBrief = async () => {
    if (!config) return;
    const saved = await updateClientConfig(clientId, config);
    setConfig(saved);
    setBriefMsg("Sentiment Brief (POV Klien) berhasil disimpan ke config.yaml & siap dipakai Pass 1 AI.");
  };

  const currentNtBrief: NewstrendBriefData = config?.newstrend_brief || {
    brief_uuid: "",
    client_name: "All Client",
    deskripsi: "Pembuatan newstrend secara otomatis",
    clustering_method: "general",
    general_guideline: "",
    additional_information: "",
    examples: [],
  };

  const updateNtBrief = (patch: Partial<NewstrendBriefData>) => {
    if (!config) return;
    setConfig({
      ...config,
      newstrend_brief: { ...currentNtBrief, ...patch },
    });
    setNtMsg("");
  };

  const handleImportNtJson = () => {
    if (!config || !rawNtJson.trim()) return;
    setNtErr("");
    setNtMsg("");
    try {
      const parsed = JSON.parse(rawNtJson);
      const instr = parsed.instructions || parsed;
      const examples = Array.isArray(instr.examples)
        ? instr.examples
            .filter((e: unknown) => e && typeof e === "object")
            .map((e: Record<string, unknown>) => ({
              context: String(e.context || "").trim(),
              pattern: String(e.pattern || "").trim(),
            }))
            .filter((e: { context: string; pattern: string }) => e.context && e.pattern)
        : [];
      const imported: NewstrendBriefData = {
        brief_uuid: String(parsed.brief_uuid || currentNtBrief.brief_uuid || ""),
        client_name: String(parsed.client_name || "All Client"),
        deskripsi: String(parsed.deskripsi || currentNtBrief.deskripsi || ""),
        clustering_method: String(instr.clustering_method || "general"),
        general_guideline: String(instr.general_guideline || ""),
        additional_information: String(instr.additional_information || ""),
        examples,
      };
      setConfig({ ...config, newstrend_brief: imported });
      setRawNtJson("");
      setShowNtJsonImport(false);
      setNtMsg(
        `JSON Newstrend Brief berhasil diimpor (${examples.length} contoh pola). Klik Simpan untuk menyimpan ke config.yaml.`
      );
    } catch {
      setNtErr("Format JSON tidak valid. Pastikan JSON utuh dari tanda { sampai }.");
    }
  };

  const handleAddNtExample = () => {
    if (!newExContext.trim() || !newExPattern.trim()) return;
    updateNtBrief({
      examples: [
        ...currentNtBrief.examples,
        { context: newExContext.trim(), pattern: newExPattern.trim() },
      ],
    });
    setNewExContext("");
    setNewExPattern("");
  };

  const handleRemoveNtExample = (idx: number) => {
    updateNtBrief({
      examples: currentNtBrief.examples.filter((_, i) => i !== idx),
    });
  };

  const handleSaveNtBrief = async () => {
    if (!config) return;
    const saved = await updateClientConfig(clientId, config);
    setConfig(saved);
    setNtMsg("Newstrend Creation Brief berhasil disimpan ke config.yaml & siap dipakai Pass 2 AI.");
  };

  return (
    <div className="space-y-6">
      {/* Focused Single-Client Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-zinc-900">
              {config?.client_name || clientId.toUpperCase()}
            </h1>
            <p className="font-mono text-xs text-zinc-400">
              clients/{clientId}/config.yaml
            </p>
          </div>
        </div>
        {config?.focus_type && (
          <span className="rounded-lg bg-zinc-100 px-3 py-1 text-xs font-semibold uppercase text-zinc-600">
            {config.focus_type.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Dynamic Ad-Hoc Columns Editor */}
        <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
          <div>
            <h2 className="text-base font-bold text-zinc-900">
              Kolom Ad-Hoc Klien ({clientId.toUpperCase()})
            </h2>
            <p className="text-xs text-zinc-500">
              Tambahkan kolom khusus (mis. <code>Kluster</code>, <code>Paid_Earned</code>,{" "}
              <code>Sub_Program</code>) tanpa mengedit file YAML manual.
            </p>
          </div>

          {config ? (
            <>
              <div className="space-y-2">
                {config.adhoc_columns.map((col) => (
                  <div
                    key={col.name}
                    className="flex items-start justify-between gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3"
                  >
                    <div>
                      <div className="text-xs font-bold text-zinc-800">{col.name}</div>
                      <div className="text-xs text-zinc-600">{col.description}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveAdhoc(col.name)}
                      className="rounded p-1 text-zinc-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="space-y-2 rounded-xl border border-dashed border-zinc-300 p-3.5">
                <div className="text-xs font-semibold text-zinc-700">Tambah Kolom Ad-Hoc Baru</div>
                <input
                  type="text"
                  value={newColName}
                  onChange={(e) => setNewColName(e.target.value)}
                  placeholder="Nama Kolom (mis. Sub_Program)"
                  className="w-full rounded-lg border border-zinc-300 px-3 py-1.5 text-xs focus:border-blue-600 focus:outline-none"
                />
                <input
                  type="text"
                  value={newColDesc}
                  onChange={(e) => setNewColDesc(e.target.value)}
                  placeholder="Instruksi klasifikasi AI untuk kolom ini..."
                  className="w-full rounded-lg border border-zinc-300 px-3 py-1.5 text-xs focus:border-blue-600 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAddAdhoc}
                  className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-zinc-800"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Tambah ke Daftar
                </button>
              </div>

              <button
                type="button"
                onClick={handleSaveConfig}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
              >
                <Save className="h-4 w-4" />
                Simpan ke config.yaml
              </button>

              {cfgMsg && (
                <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-2.5 text-xs text-emerald-800">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{cfgMsg}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-zinc-400">Memuat konfigurasi klien...</p>
          )}
        </div>

        {/* Right Column: Media Master Importer + PPTX Template Uploader */}
        <div className="space-y-6">
          <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
            <div>
              <h2 className="text-base font-bold text-zinc-900">
                Import Master Media &amp; Custom Tier (SQLite)
              </h2>
              <p className="text-xs text-zinc-500">
                Unggah file <code>.xlsx</code> atau <code>.csv</code> berisi daftar domain,{" "}
                <code>tier_bino</code>, <code>TIER {clientId.toUpperCase()}</code>, <code>Newswire</code>/
                <code>Media Bazar</code>, dan trafik Hypestat.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-600">
                Client Key untuk Custom Tier
              </label>
              <input
                type="text"
                value={tierKey}
                onChange={(e) => setTierKey(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
              />
            </div>

            <div>
              <input
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={(e) => setMediaFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-zinc-600 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-100 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-zinc-700 hover:file:bg-zinc-200"
              />
            </div>

            <button
              type="button"
              disabled={!mediaFile}
              onClick={handleImportMedia}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-40"
            >
              <Upload className="h-4 w-4" />
              Import &amp; Upsert ke SQLite
            </button>

            {mediaMsg && (
              <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-2.5 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                <span>{mediaMsg}</span>
              </div>
            )}
          </div>

          <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
            <div>
              <h2 className="flex items-center gap-2 text-base font-bold text-zinc-900">
                <Presentation className="h-5 w-5 text-blue-600" />
                Upload Template Report PPTX ({clientId.toUpperCase()})
              </h2>
              <p className="text-xs text-zinc-500">
                Unggah file <code>.pptx</code> template klien untuk disimpan ke{" "}
                <code>clients/{clientId}/template_daily.pptx</code> dan dipakai saat ekspor Output 2.
              </p>
            </div>

            <div>
              <input
                type="file"
                accept=".pptx"
                onChange={(e) => setPptxFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-zinc-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>

            <button
              type="button"
              disabled={!pptxFile}
              onClick={handleUploadPptx}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
            >
              <Upload className="h-4 w-4" />
              Upload Template PPTX
            </button>

            {pptxMsg && (
              <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-2.5 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                <span>{pptxMsg}</span>
              </div>
            )}
            {pptxErr && (
              <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
                <AlertCircle className="h-4 w-4" />
                <span>{pptxErr}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Full-Width Sentiment Brief (POV Klien) Card */}
      <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-zinc-900">
              <BookOpenCheck className="h-5 w-5 text-blue-600" />
              Sentiment Brief / POV Klien ({clientId.toUpperCase()})
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Panduan konteks sentimen khusus klien (otomatis di-cache di System Prompt Pass 1 — tambahan biaya &lt; Rp 15/laporan).
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setBriefErr("");
              setShowJsonImport((v) => !v);
            }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-300 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            <FileJson className="h-4 w-4 text-blue-600" />
            {showJsonImport ? "Tutup Import JSON" : "Paste / Import JSON Brief"}
          </button>
        </div>

        {showJsonImport && (
          <div className="space-y-2.5 rounded-xl border border-blue-200 bg-blue-50/40 p-4">
            <div className="text-xs font-semibold text-zinc-800">
              Tempel JSON Brief Sentimen (mendukung format <code>instructions.analyst_verdict</code> &amp; <code>*_guidelines</code>)
            </div>
            <textarea
              rows={6}
              value={rawBriefJson}
              onChange={(e) => setRawBriefJson(e.target.value)}
              placeholder='{"brief_uuid": "...", "deskripsi": "...", "instructions": { "analyst_verdict": "...", "negative_guidelines": [...], ... }}'
              className="w-full rounded-xl border border-zinc-300 bg-white p-3 font-mono text-xs focus:border-blue-600 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleImportBriefJson}
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
            >
              Parse &amp; Muat JSON ke Form
            </button>
          </div>
        )}

        {briefErr && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
            <AlertCircle className="h-4 w-4" />
            <span>{briefErr}</span>
          </div>
        )}

        {config && (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-700">
                Analyst Verdict (Konteks Utama POV Klien)
              </label>
              <textarea
                rows={5}
                value={currentBrief.analyst_verdict}
                onChange={(e) => updateBrief({ analyst_verdict: e.target.value })}
                placeholder="Jelaskan prinsip penilaian sentimen Negative, Neutral, dan Positive dari sudut pandang klien..."
                className="w-full rounded-xl border border-zinc-300 p-3 text-xs leading-relaxed focus:border-blue-600 focus:outline-none"
              />
            </div>

            {/* Guidelines Tabs */}
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    {
                      id: "negative",
                      label: `Negative Guidelines (${currentBrief.negative_guidelines.length})`,
                      activeCls: "bg-rose-600 text-white",
                    },
                    {
                      id: "neutral",
                      label: `Neutral Guidelines (${currentBrief.neutral_guidelines.length})`,
                      activeCls: "bg-zinc-800 text-white",
                    },
                    {
                      id: "positive",
                      label: `Positive Guidelines (${currentBrief.positive_guidelines.length})`,
                      activeCls: "bg-emerald-600 text-white",
                    },
                  ] as const
                ).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setBriefTab(t.id)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      briefTab === t.id
                        ? t.activeCls
                        : "border border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="max-h-64 space-y-1.5 overflow-y-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3">
                {(briefTab === "negative"
                  ? currentBrief.negative_guidelines
                  : briefTab === "neutral"
                  ? currentBrief.neutral_guidelines
                  : currentBrief.positive_guidelines
                ).map((rule, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-2 rounded-lg bg-white px-3 py-2 text-xs text-zinc-700 shadow-2xs"
                  >
                    <span>{rule}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveBriefRule(idx)}
                      className="shrink-0 rounded p-0.5 text-zinc-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={newRuleText}
                  onChange={(e) => setNewRuleText(e.target.value)}
                  placeholder={`Tambah aturan ${briefTab} baru...`}
                  className="flex-1 rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAddBriefRule}
                  className="inline-flex items-center gap-1 rounded-xl bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-zinc-800"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Tambah
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-3">
              <button
                type="button"
                onClick={handleSaveBrief}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white hover:bg-blue-700"
              >
                <Save className="h-4 w-4" />
                Simpan Sentiment Brief ke config.yaml
              </button>
              {briefMsg && (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  {briefMsg}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Full-Width Newstrend Creation Brief Card */}
      <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-zinc-900">
              <Sparkles className="h-5 w-5 text-blue-600" />
              Newstrend Creation Brief ({clientId.toUpperCase()})
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Panduan pengelompokan &amp; standardisasi <code>Newstrends</code> pada Pass 1 &amp; Pass 2 (default global <em>All Client</em>, dapat disesuaikan per klien).
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setNtErr("");
              setShowNtJsonImport((v) => !v);
            }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-300 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            <FileJson className="h-4 w-4 text-blue-600" />
            {showNtJsonImport ? "Tutup Import JSON" : "Paste / Import JSON Brief"}
          </button>
        </div>

        {showNtJsonImport && (
          <div className="space-y-2.5 rounded-xl border border-blue-200 bg-blue-50/40 p-4">
            <div className="text-xs font-semibold text-zinc-800">
              Tempel JSON Brief Newstrend (mendukung format <code>instructions.general_guideline</code> &amp; <code>examples</code>)
            </div>
            <textarea
              rows={5}
              value={rawNtJson}
              onChange={(e) => setRawNtJson(e.target.value)}
              placeholder='{"brief_uuid": "...", "instructions": { "general_guideline": "...", "examples": [...] }}'
              className="w-full rounded-xl border border-zinc-300 bg-white p-3 font-mono text-xs focus:border-blue-600 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleImportNtJson}
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
            >
              Parse &amp; Muat JSON ke Form
            </button>
          </div>
        )}

        {ntErr && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
            <AlertCircle className="h-4 w-4" />
            <span>{ntErr}</span>
          </div>
        )}

        {config && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-zinc-700">
                  General Guideline
                </label>
                <textarea
                  rows={5}
                  value={currentNtBrief.general_guideline}
                  onChange={(e) => updateNtBrief({ general_guideline: e.target.value })}
                  className="w-full rounded-xl border border-zinc-300 p-3 text-xs leading-relaxed focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-zinc-700">
                  Additional Information
                </label>
                <textarea
                  rows={5}
                  value={currentNtBrief.additional_information}
                  onChange={(e) => updateNtBrief({ additional_information: e.target.value })}
                  className="w-full rounded-xl border border-zinc-300 p-3 text-xs leading-relaxed focus:border-blue-600 focus:outline-none"
                />
              </div>
            </div>

            <div className="space-y-2.5">
              <div className="text-xs font-semibold text-zinc-700">
                Contoh Pola Clustering ({currentNtBrief.examples.length})
              </div>
              <div className="max-h-60 space-y-2 overflow-y-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3">
                {currentNtBrief.examples.map((ex, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-2 rounded-lg bg-white px-3 py-2 text-xs shadow-2xs"
                  >
                    <div className="space-y-0.5">
                      <div className="text-zinc-700">
                        <strong className="text-zinc-900">Konteks:</strong> {ex.context}
                      </div>
                      <div className="text-blue-700">
                        <strong>Pola:</strong> {ex.pattern}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveNtExample(idx)}
                      className="shrink-0 rounded p-0.5 text-zinc-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                <input
                  type="text"
                  value={newExContext}
                  onChange={(e) => setNewExContext(e.target.value)}
                  placeholder="Konteks berita..."
                  className="rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none sm:col-span-6"
                />
                <input
                  type="text"
                  value={newExPattern}
                  onChange={(e) => setNewExPattern(e.target.value)}
                  placeholder="Pola Newstrend (sama / berbeda)..."
                  className="rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none sm:col-span-4"
                />
                <button
                  type="button"
                  onClick={handleAddNtExample}
                  className="inline-flex items-center justify-center gap-1 rounded-xl bg-zinc-900 px-3 py-2 text-xs font-semibold text-white hover:bg-zinc-800 sm:col-span-2"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Tambah
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-3">
              <button
                type="button"
                onClick={handleSaveNtBrief}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white hover:bg-blue-700"
              >
                <Save className="h-4 w-4" />
                Simpan Newstrend Brief ke config.yaml
              </button>
              {ntMsg && (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  {ntMsg}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
