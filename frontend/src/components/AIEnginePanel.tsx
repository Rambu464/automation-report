"use client";

import React, { useEffect, useState } from "react";
import {
  Sparkles,
  Play,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Table2,
  Download,
  ArrowRight,
  SlidersHorizontal,
} from "lucide-react";
import {
  JobEventPayload,
  PreCleanPreviewResponse,
  ProjectItem,
  QCResponse,
  SystemAIStatus,
  fetchPrecleanPreview,
  fetchSystemAIStatus,
  runAIStage,
  subscribeJobStream,
} from "@/lib/api";

interface AIEnginePanelProps {
  project: ProjectItem;
  qcData: QCResponse | null;
  onAICompleted: (jobId: string) => Promise<void>;
  onGoPreclean: () => void;
  onGoQC: () => void;
  onGoExport: () => void;
  onOpenModelConfig: () => void;
}

export default function AIEnginePanel({
  project,
  qcData,
  onAICompleted,
  onGoPreclean,
  onGoQC,
  onGoExport,
  onOpenModelConfig,
}: AIEnginePanelProps) {
  const [aiStatus, setAiStatus] = useState<SystemAIStatus | null>(null);
  const [preview, setPreview] = useState<PreCleanPreviewResponse | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [percent, setPercent] = useState<number>(project.status === "completed" ? 100 : 0);
  const [events, setEvents] = useState<JobEventPayload[]>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    setError("");
    setEvents([]);
    setPercent(project.status === "completed" ? 100 : 0);
    fetchSystemAIStatus().then(setAiStatus).catch(() => setAiStatus(null));
    if (project.latest_job_id) {
      fetchPrecleanPreview(project.latest_job_id)
        .then(setPreview)
        .catch(() => setPreview(null));
    } else {
      setPreview(null);
    }
  }, [project.project_id, project.latest_job_id, project.status]);

  const activeProviders = (aiStatus?.providers || []).filter((p) => p.configured);
  const primaryProvider = activeProviders[0] || null;
  const cleaned = preview?.cleaned_summary || null;

  const handleRunAI = async () => {
    if (!project.latest_job_id) return;
    setError("");
    setRunning(true);
    setPercent(5);
    setEvents([]);
    try {
      const { job_id } = await runAIStage(project.latest_job_id);
      subscribeJobStream(
        job_id,
        (ev) => {
          setPercent(ev.percent);
          setEvents((prev) => [...prev, ev]);
          if (ev.event === "done") {
            setRunning(false);
            onAICompleted(job_id);
          } else if (ev.event === "error") {
            setRunning(false);
            setError(ev.message);
          }
        },
        (errMsg) => {
          setRunning(false);
          setError(errMsg);
        }
      );
    } catch (err) {
      setRunning(false);
      setError(err instanceof Error ? err.message : "Gagal menjalankan 3-Pass AI Engine.");
    }
  };

  if (!project.latest_job_id || !cleaned) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-xs">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-purple-50 text-purple-600">
          <Sparkles className="h-5 w-5" />
        </div>
        <h2 className="text-base font-bold text-zinc-900">Pre-Cleaning Belum Dijalankan</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Jalankan tahap <strong>Pre-Cleaning &amp; Media Tier</strong> terlebih dahulu agar data bersih siap dikirim ke 3-Pass Cloud AI Engine.
        </p>
        <button
          type="button"
          onClick={onGoPreclean}
          className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-700"
        >
          Buka Pre-Cleaning
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  const sent = qcData?.report_payload.sentiment_summary;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      {/* Left: Readiness & Trigger */}
      <div className="space-y-5 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs lg:col-span-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-100 text-purple-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-900">
                3-Pass Cloud AI Engine
              </h2>
              <p className="text-xs text-zinc-500">
                Pass 1 (Sentimen POV Klien, Ad-Hoc, Spokesperson) → Pass 2 (Standardisasi Newstrend) → Pass 3 (Narasi Executive Summary).
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenModelConfig}
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            <SlidersHorizontal className="h-3.5 w-3.5 text-blue-600" />
            Ganti Model AI
          </button>
        </div>

        {/* Readiness Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3.5">
            <div className="text-[11px] font-semibold text-zinc-500">Model Primary Aktif</div>
            {primaryProvider ? (
              <div className="mt-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-900">
                  <Cpu className="h-3.5 w-3.5 text-blue-600" />
                  {primaryProvider.name}
                </div>
                <div className="truncate font-mono text-[10px] text-zinc-500">
                  {primaryProvider.model}
                </div>
              </div>
            ) : (
              <div className="mt-1 text-xs font-semibold text-amber-700">
                API Key Belum Diisi
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3.5">
            <div className="text-[11px] font-semibold text-zinc-500">Berita Bersih / Klaster</div>
            <div className="mt-1 text-base font-bold text-zinc-900">
              {cleaned.total_clean} <span className="text-xs font-normal text-zinc-500">Keep</span>
              <span className="mx-1.5 text-zinc-300">•</span>
              <span className="text-purple-700">{cleaned.ai_cluster_reps}</span>{" "}
              <span className="text-xs font-normal text-zinc-500">Rep</span>
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3.5">
            <div className="text-[11px] font-semibold text-zinc-500">SQLite AI Batch Cache</div>
            <div className="mt-1 text-xs font-semibold text-emerald-700">
              Aktif (Prioritas human_qc)
            </div>
            <div className="text-[10px] text-zinc-500">
              Koreksi QC &amp; batch lama otomatis di-cache.
            </div>
          </div>
        </div>

        {/* Sentiment Results (if available) */}
        {sent && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
              <div className="text-xs font-semibold text-zinc-500">Komposisi Sentimen Saat Ini</div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg bg-emerald-50 p-2 text-emerald-800">
                  <div className="text-[10px]">Positif</div>
                  <div className="text-base font-bold">{sent.positive}</div>
                </div>
                <div className="rounded-lg bg-zinc-200/70 p-2 text-zinc-800">
                  <div className="text-[10px]">Netral</div>
                  <div className="text-base font-bold">{sent.neutral}</div>
                </div>
                <div className="rounded-lg bg-rose-50 p-2 text-rose-800">
                  <div className="text-[10px]">Negatif</div>
                  <div className="text-base font-bold">{sent.negative}</div>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
              <div className="text-xs font-semibold text-zinc-500">Kolom Ad-Hoc Aktif</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {(qcData?.adhoc_columns || []).length > 0 ? (
                  qcData?.adhoc_columns.map((c) => (
                    <span
                      key={c}
                      className="rounded-lg bg-purple-100 px-2.5 py-1 text-xs font-semibold text-purple-800"
                    >
                      {c}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-zinc-400">Tidak ada kolom ad-hoc.</span>
                )}
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-4">
          <div className="flex items-center gap-2">
            {qcData && (
              <>
                <button
                  type="button"
                  onClick={onGoQC}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  <Table2 className="h-3.5 w-3.5 text-emerald-600" />
                  Buka Tabel QC
                </button>
                <button
                  type="button"
                  onClick={onGoExport}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                >
                  <Download className="h-3.5 w-3.5" />
                  Ekspor 3 Output
                </button>
              </>
            )}
          </div>

          <button
            type="button"
            disabled={running || !primaryProvider}
            onClick={handleRunAI}
            className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            {running
              ? "Menjalankan 3-Pass AI..."
              : project.status === "completed"
              ? "Jalankan Ulang 3-Pass AI"
              : "Kirim ke 3-Pass AI Engine"}
          </button>
        </div>
      </div>

      {/* Right: Live Progress SSE */}
      <div className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-600">
            Live Progress AI (SSE)
          </h3>
          <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-bold text-purple-700">
            {percent}%
          </span>
        </div>

        <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-100">
          <div
            className="h-full rounded-full bg-purple-600 transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>

        <div className="flex-1 space-y-2 overflow-y-auto rounded-xl bg-zinc-50 p-3 text-xs max-h-72">
          {events.length === 0 ? (
            <p className="text-zinc-400">
              {project.status === "completed"
                ? "3-Pass AI Engine sudah selesai dijalankan pada project ini. Klik 'Jalankan Ulang 3-Pass AI' jika ingin memproses ulang."
                : "Klik 'Kirim ke 3-Pass AI Engine' untuk memantau progres Pass 1–3 secara real-time."}
            </p>
          ) : (
            events.map((ev, i) => (
              <div key={i} className="flex items-start gap-2">
                {ev.event === "done" ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                ) : ev.event === "error" ? (
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                ) : (
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-500" />
                )}
                <span className="text-zinc-700">{ev.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
