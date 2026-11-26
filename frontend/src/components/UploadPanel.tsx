"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  ArrowRight,
  ShieldBan,
  Save,
} from "lucide-react";
import {
  ProjectItem,
  RawPreviewData,
  fetchClientTakedowns,
  fetchPrecleanPreview,
  stageRawFiles,
} from "@/lib/api";

interface UploadPanelProps {
  project: ProjectItem;
  onRawStaged: (jobId: string) => Promise<void>;
  onGoPreclean: () => void;
}

export default function UploadPanel({
  project,
  onRawStaged,
  onGoPreclean,
}: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [cutoffDatetime, setCutoffDatetime] = useState<string>(
    project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : ""
  );
  const [savedTakedownCount, setSavedTakedownCount] = useState<number>(0);
  const [stagedPreview, setStagedPreview] = useState<RawPreviewData | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    setCutoffDatetime(project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : "");
    setFiles([]);
    setSuccessMsg("");
    setError("");
    fetchClientTakedowns(project.client_id)
      .then((res) => setSavedTakedownCount(res.count))
      .catch(() => setSavedTakedownCount(0));

    if (project.latest_job_id) {
      fetchPrecleanPreview(project.latest_job_id)
        .then((res) => setStagedPreview(res.raw_preview))
        .catch(() => setStagedPreview(null));
    } else {
      setStagedPreview(null);
    }
  }, [project.project_id, project.client_id, project.cutoff_datetime, project.latest_job_id]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      setError("");
      setSuccessMsg("");
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      setFiles(Array.from(e.dataTransfer.files));
      setError("");
      setSuccessMsg("");
    }
  };

  const handleStageRaw = async () => {
    if (files.length === 0) {
      setError("Pilih minimal 1 file Excel (.xls / .xlsx with Statements) terlebih dahulu.");
      return;
    }
    setError("");
    setSuccessMsg("");
    setSaving(true);
    try {
      const normalizedCutoff = cutoffDatetime ? cutoffDatetime.replace("T", " ") : "";
      const res = await stageRawFiles({
        projectId: project.project_id,
        clientId: project.client_id,
        files,
        cutoffDatetime: normalizedCutoff,
      });
      setStagedPreview(res.raw_preview);
      setFiles([]);
      setSuccessMsg(
        `Raw data tersimpan (${res.raw_preview.total_raw_news} berita & ${res.raw_preview.total_raw_statements} statements). Lanjutkan ke tahap Pre-Cleaning.`
      );
      await onRawStaged(res.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan raw data.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="space-y-5 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-zinc-900">
              Input Raw Data — {project.name}
            </h2>
            <p className="text-xs text-zinc-500">
              Klien aktif: <strong className="text-zinc-800">{project.client_id.toUpperCase()}</strong> •
              Tipe: <strong className="uppercase text-zinc-800">{project.report_type}</strong>
            </p>
          </div>
          {stagedPreview && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {stagedPreview.total_raw_news} Raw News tersimpan
            </span>
          )}
        </div>

        {/* Drag and Drop Zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-zinc-300 bg-zinc-50/70 px-6 py-8 text-center transition hover:border-blue-400 hover:bg-blue-50/40"
        >
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
            <UploadCloud className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-zinc-700">
            Tarik &amp; lepaskan file <span className="font-semibold">.xls / .xlsx</span> ke sini, atau klik untuk memilih
          </p>
          <p className="mt-1 text-xs text-zinc-400">
            Format standar: Spreadsheet (.xls with Statements) dari Dashboard Newstensity
          </p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".xls,.xlsx"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {files.length > 0 && (
          <div className="space-y-1.5 rounded-xl border border-blue-200 bg-blue-50/50 p-3">
            <div className="text-[11px] font-semibold text-blue-700">
              File siap diunggah ({files.length}):
            </div>
            {files.map((f) => (
              <div key={f.name} className="flex items-center gap-2 text-xs text-zinc-800">
                <FileSpreadsheet className="h-4 w-4 text-blue-700" />
                <span className="font-semibold">{f.name}</span>
                <span className="text-zinc-500">({(f.size / 1024).toFixed(1)} KB)</span>
              </div>
            ))}
          </div>
        )}

        {/* Cutoff */}
        <div className="max-w-sm">
          <label className="mb-1 block text-xs font-semibold text-zinc-600">
            Batas Tanggal &amp; Jam Cutoff (WIB, Opsional)
          </label>
          <input
            type="datetime-local"
            value={cutoffDatetime}
            onChange={(e) => setCutoffDatetime(e.target.value)}
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
          />
        </div>

        {/* Previously Staged Files Summary */}
        {stagedPreview && stagedPreview.files.length > 0 && (
          <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5 text-xs">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="font-semibold text-zinc-700">File Raw Tersimpan di Project Ini</span>
              <span className="text-[11px] text-zinc-500">
                {stagedPreview.total_raw_news} baris News • {stagedPreview.total_raw_statements} baris Statements
              </span>
            </div>
            <div className="space-y-1">
              {stagedPreview.files.map((f) => (
                <div key={f.name} className="flex items-center gap-2 text-zinc-700">
                  <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="font-medium">{f.name}</span>
                  <span className="text-zinc-400">({(f.size_bytes / 1024).toFixed(1)} KB)</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-4">
          <div className="text-[11px] text-zinc-500">
            {savedTakedownCount > 0 ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-1 font-semibold text-rose-700">
                <ShieldBan className="h-3.5 w-3.5" />
                {savedTakedownCount} URL Takedown {project.client_id.toUpperCase()} aktif saat Pre-Cleaning
              </span>
            ) : (
              <span>Unggah file mentah lalu lanjutkan ke tahap Pre-Cleaning &amp; Media Tier.</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={saving || files.length === 0}
              onClick={handleStageRaw}
              className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? "Menyimpan Raw Data..." : "Simpan Raw Data"}
            </button>

            {stagedPreview && (
              <button
                type="button"
                onClick={onGoPreclean}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700"
              >
                Lanjut ke Pre-Cleaning
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
