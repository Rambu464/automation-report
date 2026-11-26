"use client";

import React, { useEffect, useState } from "react";
import {
  Filter,
  Play,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  ArrowRight,
  Table2,
  ExternalLink,
} from "lucide-react";
import {
  PreCleanPreviewResponse,
  ProjectItem,
  fetchPrecleanPreview,
  runPrecleanStage,
} from "@/lib/api";

interface PreCleanPanelProps {
  project: ProjectItem;
  onPrecleanCompleted: (jobId: string) => Promise<void>;
  onGoUpload: () => void;
  onGoQC: () => void;
  onGoAI: () => void;
}

export default function PreCleanPanel({
  project,
  onPrecleanCompleted,
  onGoUpload,
  onGoQC,
  onGoAI,
}: PreCleanPanelProps) {
  const [preview, setPreview] = useState<PreCleanPreviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [cutoffInput, setCutoffInput] = useState<string>(
    project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : ""
  );
  const [activeTab, setActiveTab] = useState<"raw" | "cleaned">("raw");

  useEffect(() => {
    setCutoffInput(project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : "");
    setError("");
    if (!project.latest_job_id) {
      setPreview(null);
      return;
    }
    setLoading(true);
    fetchPrecleanPreview(project.latest_job_id)
      .then((res) => {
        setPreview(res);
        setActiveTab(res.cleaned_summary ? "cleaned" : "raw");
      })
      .catch((err) => {
        setPreview(null);
        setError(err instanceof Error ? err.message : "Gagal memuat preview.");
      })
      .finally(() => setLoading(false));
  }, [project.project_id, project.latest_job_id, project.cutoff_datetime]);

  const handleRunPreclean = async () => {
    if (!project.latest_job_id) return;
    setRunning(true);
    setError("");
    try {
      const normalizedCutoff = cutoffInput ? cutoffInput.replace("T", " ") : "";
      const res = await runPrecleanStage(project.latest_job_id, normalizedCutoff);
      setPreview(res);
      setActiveTab("cleaned");
      await onPrecleanCompleted(project.latest_job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menjalankan Pre-Cleaning.");
    } finally {
      setRunning(false);
    }
  };

  if (!project.latest_job_id) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-xs">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-50 text-sky-600">
          <FileSpreadsheet className="h-5 w-5" />
        </div>
        <h2 className="text-base font-bold text-zinc-900">Raw Data Belum Diunggah</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Unggah file Excel <code>.xls / .xlsx</code> di tahap Input Raw Data terlebih dahulu sebelum menjalankan Pre-Cleaning.
        </p>
        <button
          type="button"
          onClick={onGoUpload}
          className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
        >
          Buka Input Raw Data
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  const rawRows = preview?.raw_preview.rows || [];
  const cleaned = preview?.cleaned_summary || null;

  return (
    <div className="space-y-4">
      {/* Header + Action Card */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
              <Filter className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-900">
                Pre-Cleaning &amp; Media Tier Lookup
              </h2>
              <p className="text-xs text-zinc-500">
                Pemrosesan deterministik (<strong>0 Token AI</strong>): Split Date/Time, Cutoff 00:00, Deduplikasi 3-Lapis, Regex Spam, Takedown Klien, &amp; Custom Media Tier.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-2.5">
            <div>
              <label className="mb-1 block text-[11px] font-semibold text-zinc-500">
                Cutoff (WIB, Opsional)
              </label>
              <input
                type="datetime-local"
                value={cutoffInput}
                onChange={(e) => setCutoffInput(e.target.value)}
                className="rounded-xl border border-zinc-300 px-3 py-1.5 text-xs focus:border-blue-600 focus:outline-none"
              />
            </div>
            <button
              type="button"
              disabled={running || loading}
              onClick={handleRunPreclean}
              className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-sky-700 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              {running
                ? "Membersihkan Data..."
                : cleaned
                ? "Jalankan Ulang Pre-Cleaning"
                : "Mulai Pre-Cleaning"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Summary KPI Strip */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3">
            <div className="text-[11px] text-zinc-500">Raw Excel Awal</div>
            <div className="mt-0.5 text-lg font-bold text-zinc-900">
              {preview?.raw_preview.total_raw_news ?? 0}
              <span className="ml-1 text-[11px] font-normal text-zinc-400">baris</span>
            </div>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3">
            <div className="text-[11px] text-emerald-700">Hasil Bersih (Keep)</div>
            <div className="mt-0.5 text-lg font-bold text-emerald-700">
              {cleaned ? cleaned.total_clean : "—"}
            </div>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-3">
            <div className="text-[11px] text-rose-700">Takeout / Spam</div>
            <div className="mt-0.5 text-lg font-bold text-rose-600">
              {cleaned ? cleaned.total_takeout : "—"}
            </div>
          </div>
          <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-3">
            <div className="text-[11px] text-blue-700">Perwakilan Klaster AI</div>
            <div className="mt-0.5 text-lg font-bold text-blue-700">
              {cleaned ? cleaned.ai_cluster_reps : "—"}
            </div>
          </div>
        </div>

        {/* Breakdown Pills when cleaned */}
        {cleaned && (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3">
              <div className="mb-1.5 text-[11px] font-semibold text-zinc-600">
                Rincian Alasan Takeout ({cleaned.total_takeout})
              </div>
              {Object.keys(cleaned.takeout_reasons).length === 0 ? (
                <div className="text-xs text-zinc-400">Tidak ada baris yang di-takeout.</div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(cleaned.takeout_reasons).map(([reason, cnt]) => (
                    <span
                      key={reason}
                      className="rounded-full bg-rose-100/80 px-2.5 py-0.5 text-[11px] font-medium text-rose-800"
                    >
                      {reason}: <strong>{cnt}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3">
              <div className="mb-1.5 text-[11px] font-semibold text-zinc-600">
                Distribusi {cleaned.custom_tier_col} (Keep)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(cleaned.by_custom_tier).map(([tier, cnt]) => (
                  <span
                    key={tier}
                    className="rounded-full bg-sky-100/80 px-2.5 py-0.5 text-[11px] font-medium text-sky-800"
                  >
                    {tier}: <strong>{cnt}</strong>
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Before vs After Table Preview */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("raw")}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                activeTab === "raw"
                  ? "bg-zinc-900 text-white"
                  : "border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
              }`}
            >
              Preview Raw Awal ({preview?.raw_preview.total_raw_news ?? 0})
            </button>
            <button
              type="button"
              disabled={!cleaned}
              onClick={() => setActiveTab("cleaned")}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                activeTab === "cleaned"
                  ? "bg-emerald-600 text-white"
                  : "border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
              }`}
            >
              Hasil Setelah Bersih ({cleaned ? `${cleaned.total_clean} Keep / ${cleaned.total_takeout} Takeout` : "Belum Dijalankan"})
            </button>
          </div>

          {cleaned && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onGoQC}
                className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                <Table2 className="h-3.5 w-3.5 text-emerald-600" />
                Cek di Tabel QC
              </button>
              <button
                type="button"
                onClick={onGoAI}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
              >
                Lanjut ke 3-Pass AI
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="py-10 text-center text-xs text-zinc-400">Memuat preview data...</div>
        ) : activeTab === "raw" ? (
          <div className="max-h-[420px] overflow-auto rounded-xl border border-zinc-200">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-zinc-800 text-white">
                <tr>
                  <th className="px-2.5 py-2">#</th>
                  <th className="px-2.5 py-2">Date (Raw)</th>
                  <th className="px-2.5 py-2">Media Name</th>
                  <th className="px-2.5 py-2">Title</th>
                  <th className="px-2.5 py-2">Type</th>
                  <th className="px-2.5 py-2">Raw Tier</th>
                  <th className="px-2.5 py-2">Raw Sentiment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 bg-white">
                {rawRows.map((row, idx) => (
                  <tr key={String(row.ID || idx)} className="hover:bg-zinc-50">
                    <td className="px-2.5 py-2 text-zinc-400">{idx + 1}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-zinc-700">
                      {String(row.Date || "")}
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2 font-medium text-zinc-800">
                      {String(row["Media Name"] || "")}
                    </td>
                    <td className="max-w-md px-2.5 py-2 text-zinc-600">
                      <span className="line-clamp-2">{String(row.Title || "")}</span>
                    </td>
                    <td className="px-2.5 py-2 capitalize text-zinc-600">
                      {String(row["Media Type"] || "")}
                    </td>
                    <td className="px-2.5 py-2 text-zinc-600">
                      {String(row["Media Tier"] || "")}
                    </td>
                    <td className="px-2.5 py-2 text-zinc-600">
                      {String(row.Sentiment || "")}
                    </td>
                  </tr>
                ))}
                {rawRows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-zinc-400">
                      Tidak ada preview raw data.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="max-h-[420px] overflow-auto rounded-xl border border-zinc-200">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-slate-800 text-white">
                <tr>
                  <th className="px-2.5 py-2">Date / Time</th>
                  <th className="px-2.5 py-2">Status</th>
                  <th className="px-2.5 py-2">Alasan Takeout</th>
                  <th className="px-2.5 py-2">Media &amp; Judul</th>
                  <th className="px-2.5 py-2">{cleaned?.custom_tier_col || "Tier"}</th>
                  <th className="px-2.5 py-2">Klaster</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 bg-white">
                {(cleaned?.rows || []).map((row, idx) => {
                  const isTakeout = row.Status_Takeout !== "Keep";
                  const isCutoff00 = row.Flag_Cutoff_00 === "CEK_CUTOFF_00:00";
                  return (
                    <tr
                      key={String(row.ID || idx)}
                      className={
                        isCutoff00
                          ? "bg-amber-50/70"
                          : isTakeout
                          ? "bg-rose-50/40"
                          : "hover:bg-zinc-50"
                      }
                    >
                      <td className="whitespace-nowrap px-2.5 py-2">
                        <div className="font-medium text-zinc-800">{String(row.Date || "")}</div>
                        <div className={isCutoff00 ? "font-bold text-amber-700" : "text-zinc-500"}>
                          {String(row.Time || "")} {isCutoff00 ? "⚠" : ""}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-2.5 py-2">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            isTakeout
                              ? "bg-rose-100 text-rose-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {!isTakeout && <CheckCircle2 className="h-3 w-3" />}
                          {String(row.Status_Takeout || "Keep")}
                        </span>
                      </td>
                      <td className="px-2.5 py-2 text-zinc-600">
                        {String(row.Alasan_Spam || "-")}
                      </td>
                      <td className="max-w-md px-2.5 py-2">
                        <div className="flex items-center gap-1 font-semibold text-zinc-800">
                          <span>{String(row["Media Name"] || "")}</span>
                          {row["Page/URL"] ? (
                            <a
                              href={String(row["Page/URL"])}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:text-blue-800"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : null}
                        </div>
                        <div className="line-clamp-2 text-zinc-600">{String(row.Title || "")}</div>
                      </td>
                      <td className="whitespace-nowrap px-2.5 py-2 font-semibold text-sky-700">
                        {String(row.Tier || "-")}
                      </td>
                      <td className="whitespace-nowrap px-2.5 py-2 text-[11px] text-zinc-500">
                        {String(row.Cluster_ID || "-")}
                        {Boolean(row.Is_Cluster_Rep) && !isTakeout && (
                          <span className="ml-1 rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
                            Rep
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
