"use client";

import React, { useEffect, useState } from "react";
import { Plus, Trash2, Save, Upload, CheckCircle2, UserPlus, AlertCircle, Presentation } from "lucide-react";
import {
  ClientConfigData,
  createClientProfile,
  fetchClientConfig,
  importMediaMaster,
  updateClientConfig,
  uploadClientPptxTemplate,
} from "@/lib/api";

interface SettingsPanelProps {
  clients: string[];
  clientId: string;
  onSelectClient: (c: string) => void;
  onClientCreated: (newClientId: string) => Promise<void>;
  compact?: boolean;
}

export default function SettingsPanel({
  clients,
  clientId,
  onSelectClient,
  onClientCreated,
  compact = false,
}: SettingsPanelProps) {
  const [compactTab, setCompactTab] = useState<"adhoc" | "media" | "pptx">("adhoc");
  const [config, setConfig] = useState<ClientConfigData | null>(null);
  const [newColName, setNewColName] = useState<string>("");
  const [newColDesc, setNewColDesc] = useState<string>("");
  const [cfgMsg, setCfgMsg] = useState<string>("");

  // Create New Client Form
  const [showCreateForm, setShowCreateForm] = useState<boolean>(false);
  const [newClientId, setNewClientId] = useState<string>("");
  const [newClientName, setNewClientName] = useState<string>("");
  const [newFocusType, setNewFocusType] = useState<"brand_only" | "brand_and_competitor" | "crisis">(
    "brand_and_competitor"
  );
  const [newTierCol, setNewTierCol] = useState<string>("");
  const [newCompetitors, setNewCompetitors] = useState<string>("");
  const [createErr, setCreateErr] = useState<string>("");
  const [createMsg, setCreateMsg] = useState<string>("");

  // Media Master Import
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [tierKey, setTierKey] = useState<string>(clientId);
  const [mediaMsg, setMediaMsg] = useState<string>("");

  // PPTX Template Upload
  const [pptxFile, setPptxFile] = useState<File | null>(null);
  const [pptxMsg, setPptxMsg] = useState<string>("");
  const [pptxErr, setPptxErr] = useState<string>("");

  useEffect(() => {
    setTierKey(clientId);
    fetchClientConfig(clientId)
      .then(setConfig)
      .catch(() => setConfig(null));
  }, [clientId]);

  const handleCreateClient = async () => {
    if (!newClientId.trim() || !newClientName.trim()) {
      setCreateErr("ID Klien dan Nama Klien wajib diisi.");
      return;
    }
    setCreateErr("");
    setCreateMsg("");
    try {
      const res = await createClientProfile({
        client_id: newClientId.trim(),
        client_name: newClientName.trim(),
        focus_type: newFocusType,
        custom_tier_enabled: true,
        custom_tier_column: newTierCol.trim(),
        competitors: newCompetitors
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await onClientCreated(res.client_id);
      setCreateMsg(`Profil klien '${res.client_id.toUpperCase()}' berhasil dibuat!`);
      setNewClientId("");
      setNewClientName("");
      setNewTierCol("");
      setNewCompetitors("");
      setShowCreateForm(false);
    } catch (err) {
      setCreateErr(err instanceof Error ? err.message : "Gagal membuat profil klien.");
    }
  };

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

  return (
    <div className={compact ? "space-y-4" : "space-y-6"}>
      {/* Top Bar: Client Switcher + Create New Client */}
      <div className={compact ? "space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5" : "rounded-xl border border-slate-200 bg-white p-5 shadow-sm"}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Klien:
            </span>
            <select
              value={clientId}
              onChange={(e) => onSelectClient(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-bold text-zinc-800"
            >
              {clients.map((c) => (
                <option key={c} value={c}>
                  {c.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={() => setShowCreateForm((v) => !v)}
            className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-zinc-800"
          >
            <UserPlus className="h-3.5 w-3.5" />
            {showCreateForm ? "Tutup" : "+ Klien Baru"}
          </button>
        </div>

        {compact && (
          <div className="grid grid-cols-3 gap-1 rounded-lg bg-zinc-200/70 p-1">
            {(
              [
                { id: "adhoc", label: "Ad-Hoc" },
                { id: "media", label: "Master Media" },
                { id: "pptx", label: "Template PPTX" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setCompactTab(t.id)}
                className={`rounded-md py-1.5 text-[11px] font-semibold transition ${
                  compactTab === t.id
                    ? "bg-white text-zinc-900 shadow-2xs"
                    : "text-zinc-600 hover:text-zinc-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {createMsg && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            <span>{createMsg}</span>
          </div>
        )}

        {showCreateForm && (
          <div className="mt-4 space-y-3 rounded-lg border border-blue-200 bg-blue-50/40 p-4">
            <div className="text-sm font-semibold text-slate-900">Buat Profil Klien Baru</div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="text"
                value={newClientId}
                onChange={(e) => setNewClientId(e.target.value)}
                placeholder="ID Klien (mis. mandiri, telkom)"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              />
              <input
                type="text"
                value={newClientName}
                onChange={(e) => setNewClientName(e.target.value)}
                placeholder="Nama Resmi Klien (mis. Bank Mandiri)"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              />
              <select
                value={newFocusType}
                onChange={(e) =>
                  setNewFocusType(
                    e.target.value as "brand_only" | "brand_and_competitor" | "crisis"
                  )
                }
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              >
                <option value="brand_and_competitor">Brand + Kompetitor</option>
                <option value="brand_only">Brand Only</option>
                <option value="crisis">Crisis / Issue Monitoring</option>
              </select>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                type="text"
                value={newTierCol}
                onChange={(e) => setNewTierCol(e.target.value)}
                placeholder="Nama Kolom Custom Tier (opsional, default: TIER <ID>)"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              />
              <input
                type="text"
                value={newCompetitors}
                onChange={(e) => setNewCompetitors(e.target.value)}
                placeholder="Kompetitor pisah koma (opsional, mis. BRI, BNI, BCA)"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              />
            </div>
            {createErr && (
              <div className="flex items-center gap-2 text-xs text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span>{createErr}</span>
              </div>
            )}
            <button
              type="button"
              onClick={handleCreateClient}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
            >
              <Save className="h-3.5 w-3.5" />
              Simpan Profil Klien Baru
            </button>
          </div>
        )}
      </div>

      <div className={compact ? "space-y-4" : "grid grid-cols-1 gap-6 lg:grid-cols-2"}>
        {/* Left: Dynamic Ad-Hoc Columns Editor */}
        {(!compact || compactTab === "adhoc") && (
        <div className={compact ? "space-y-3 rounded-xl border border-zinc-200 bg-white p-4" : "space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"}>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Kolom Ad-Hoc Klien ({clientId.toUpperCase()})
            </h2>
            <p className="text-xs text-slate-500">
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
                    className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3"
                  >
                    <div>
                      <div className="text-xs font-bold text-slate-800">{col.name}</div>
                      <div className="text-xs text-slate-600">{col.description}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveAdhoc(col.name)}
                      className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="space-y-2 rounded-lg border border-dashed border-slate-300 p-3">
                <div className="text-xs font-semibold text-slate-700">Tambah Kolom Ad-Hoc Baru</div>
                <input
                  type="text"
                  value={newColName}
                  onChange={(e) => setNewColName(e.target.value)}
                  placeholder="Nama Kolom (mis. Sub_Program)"
                  className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs"
                />
                <input
                  type="text"
                  value={newColDesc}
                  onChange={(e) => setNewColDesc(e.target.value)}
                  placeholder="Instruksi klasifikasi AI untuk kolom ini..."
                  className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs"
                />
                <button
                  type="button"
                  onClick={handleAddAdhoc}
                  className="inline-flex items-center gap-1 rounded bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Tambah ke Daftar
                </button>
              </div>

              <button
                type="button"
                onClick={handleSaveConfig}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-800"
              >
                <Save className="h-4 w-4" />
                Simpan ke config.yaml
              </button>

              {cfgMsg && (
                <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-800">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{cfgMsg}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-slate-400">Memuat konfigurasi klien...</p>
          )}
        </div>
        )}

        {/* Right Column: Media Master Importer + PPTX Template Uploader */}
        <div className={compact ? "space-y-4" : "space-y-6"}>
          {(!compact || compactTab === "media") && (
          <div className={compact ? "space-y-3 rounded-xl border border-zinc-200 bg-white p-4" : "space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"}>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Import Master Media &amp; Custom Tier (SQLite)
              </h2>
              <p className="text-xs text-slate-500">
                Unggah file <code>.xlsx</code> atau <code>.csv</code> berisi daftar domain,{" "}
                <code>tier_bino</code>, <code>TIER &lt;KLIEN&gt;</code>, <code>Newswire</code>/
                <code>Media Bazar</code>, dan trafik Hypestat.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600">
                Client Key untuk Custom Tier (Opsional, mis. bri / bni)
              </label>
              <input
                type="text"
                value={tierKey}
                onChange={(e) => setTierKey(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>

            <div>
              <input
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={(e) => setMediaFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>

            <button
              type="button"
              disabled={!mediaFile}
              onClick={handleImportMedia}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-40"
            >
              <Upload className="h-4 w-4" />
              Import &amp; Upsert ke SQLite
            </button>

            {mediaMsg && (
              <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                <span>{mediaMsg}</span>
              </div>
            )}
          </div>
          )}

          {(!compact || compactTab === "pptx") && (
          <div className={compact ? "space-y-3 rounded-xl border border-zinc-200 bg-white p-4" : "space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"}>
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                <Presentation className="h-5 w-5 text-orange-600" />
                Upload Template Report PPTX ({clientId.toUpperCase()})
              </h2>
              <p className="text-xs text-slate-500">
                Unggah file <code>.pptx</code> template klien untuk disimpan ke{" "}
                <code>clients/{clientId}/template_daily.pptx</code> dan dipakai saat ekspor Output 2.
              </p>
            </div>

            <div>
              <input
                type="file"
                accept=".pptx"
                onChange={(e) => setPptxFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-orange-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-orange-700 hover:file:bg-orange-100"
              />
            </div>

            <button
              type="button"
              disabled={!pptxFile}
              onClick={handleUploadPptx}
              className="inline-flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-xs font-semibold text-white hover:bg-orange-700 disabled:opacity-40"
            >
              <Upload className="h-4 w-4" />
              Upload Template PPTX
            </button>

            {pptxMsg && (
              <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                <span>{pptxMsg}</span>
              </div>
            )}
            {pptxErr && (
              <div className="flex items-center gap-2 rounded-lg bg-red-50 p-2.5 text-xs text-red-700">
                <AlertCircle className="h-4 w-4" />
                <span>{pptxErr}</span>
              </div>
            )}
          </div>
          )}
        </div>
      </div>
    </div>
  );
}
