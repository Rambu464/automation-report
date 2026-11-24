"use client";

import React, { useEffect, useState } from "react";
import { Plus, Trash2, Save, Upload, CheckCircle2, AlertCircle, Presentation, Building2 } from "lucide-react";
import {
  ClientConfigData,
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
    </div>
  );
}
