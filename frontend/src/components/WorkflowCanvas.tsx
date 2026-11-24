"use client";

import React, { useState } from "react";
import {
  FileSpreadsheet,
  Filter,
  Sparkles,
  Table2,
  Presentation,
  FileText,
  CheckCircle2,
  Clock,
  ChevronDown,
  ChevronUp,
  Terminal,
  ArrowUpRight,
} from "lucide-react";
import { ProjectItem, QCResponse } from "@/lib/api";

export type WorkflowNodeId =
  | "upload"
  | "preclean"
  | "ai"
  | "qc"
  | "export_excel"
  | "export_pptx"
  | "export_wording";

interface WorkflowCanvasProps {
  project: ProjectItem;
  qcData: QCResponse | null;
  onSelectNode: (nodeId: WorkflowNodeId) => void;
}

export default function WorkflowCanvas({
  project,
  qcData,
  onSelectNode,
}: WorkflowCanvasProps) {
  const [logOpen, setLogOpen] = useState<boolean>(true);
  const isCompleted = project.status === "completed" && qcData !== null;

  const meta = qcData?.report_payload.meta;
  const sent = qcData?.report_payload.sentiment_summary;
  const tiers = qcData?.report_payload.media_breakdown.by_custom_tier || {};
  const tabs = qcData?.tab_counts;

  const statusPill = (done: boolean) =>
    done ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        Done
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold text-zinc-500">
        <Clock className="h-3 w-3" />
        Ready
      </span>
    );

  return (
    <div className="space-y-4">
      {/* Main Interactive Node Canvas */}
      <div className="relative overflow-x-auto rounded-2xl border border-zinc-200 bg-white/75 p-6 shadow-xs backdrop-blur-[1px]">
        <div className="mx-auto flex min-w-[680px] max-w-4xl flex-col items-center">
          {/* NODE 1: TRIGGER — Input Raw Data */}
          <div className="flex flex-col items-center">
            <span className="mb-1.5 rounded-full bg-blue-600 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-2xs">
              Trigger • Input
            </span>
            <button
              type="button"
              onClick={() => onSelectNode("upload")}
              className="group w-80 rounded-2xl border-2 border-blue-200 bg-white p-4 text-left shadow-xs transition hover:-translate-y-0.5 hover:border-blue-400 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
                    <FileSpreadsheet className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-zinc-900">Input Raw Data</div>
                    <div className="text-[11px] text-zinc-500">.xls with Statements</div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-zinc-300 transition group-hover:text-blue-600" />
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-100 pt-2.5 text-[11px]">
                <span className="font-medium text-zinc-600">
                  Klien: <strong className="uppercase text-zinc-900">{project.client_id}</strong>
                  {project.cutoff_datetime ? ` • ${project.cutoff_datetime}` : ""}
                </span>
                {meta ? (
                  <span className="rounded-md bg-blue-50 px-2 py-0.5 font-bold text-blue-700">
                    {meta.total_raw} raw
                  </span>
                ) : (
                  statusPill(false)
                )}
              </div>
            </button>
          </div>

          {/* Vertical Connector 1 -> 2 */}
          <svg className="h-9 w-6 text-zinc-300" viewBox="0 0 24 36" fill="none">
            <path d="M12 0 V30" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M7 25 L12 32 L17 25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>

          {/* NODE 2: Pre-Cleaning & Media Tier Lookup */}
          <button
            type="button"
            onClick={() => onSelectNode("preclean")}
            className={`group w-88 rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition hover:-translate-y-0.5 hover:shadow-md ${
              isCompleted
                ? "border-sky-200 hover:border-sky-400"
                : "border-zinc-200 hover:border-zinc-400"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
                  <Filter className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-zinc-900">
                    Pre-Cleaning &amp; Media Tier
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Cutoff 00:00 • Dedup 3-Lapis • SQLite Tier
                  </div>
                </div>
              </div>
              {statusPill(isCompleted)}
            </div>
            {meta ? (
              <div className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-zinc-50 p-2 text-center text-[11px]">
                <div>
                  <div className="text-[10px] text-zinc-400">Keep</div>
                  <div className="font-bold text-emerald-700">{meta.total_clean}</div>
                </div>
                <div>
                  <div className="text-[10px] text-zinc-400">Takeout</div>
                  <div className="font-bold text-rose-600">{meta.total_takeout}</div>
                </div>
                <div>
                  <div className="text-[10px] text-zinc-400">Tier 1</div>
                  <div className="font-bold text-sky-700">{tiers["Tier 1"] ?? 0}</div>
                </div>
              </div>
            ) : (
              <div className="mt-2.5 text-[11px] text-zinc-400">
                Klik untuk melihat rincian aturan pre-cleaning &amp; tier.
              </div>
            )}
          </button>

          {/* Vertical Connector 2 -> 3 */}
          <svg className="h-9 w-6 text-zinc-300" viewBox="0 0 24 36" fill="none">
            <path d="M12 0 V30" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M7 25 L12 32 L17 25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>

          {/* NODE 3: 3-Pass Cloud AI Engine */}
          <button
            type="button"
            onClick={() => onSelectNode("ai")}
            className={`group w-88 rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition hover:-translate-y-0.5 hover:shadow-md ${
              isCompleted
                ? "border-purple-200 hover:border-purple-400"
                : "border-zinc-200 hover:border-zinc-400"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-purple-100 text-purple-600">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-zinc-900">
                    3-Pass Cloud AI Engine
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Sentimen • Newstrend • Spokesperson • Ad-Hoc
                  </div>
                </div>
              </div>
              {statusPill(isCompleted)}
            </div>
            {sent ? (
              <div className="mt-3 flex items-center justify-between rounded-xl bg-purple-50/60 px-3 py-2 text-[11px]">
                <span className="font-semibold text-emerald-700">Pos: {sent.positive}</span>
                <span className="font-semibold text-zinc-600">Neu: {sent.neutral}</span>
                <span className="font-semibold text-rose-700">Neg: {sent.negative}</span>
              </div>
            ) : (
              <div className="mt-2.5 text-[11px] text-zinc-400">
                Klik untuk melihat ringkasan sentimen &amp; kolom ad-hoc.
              </div>
            )}
          </button>

          {/* Vertical Connector 3 -> 4 */}
          <svg className="h-9 w-6 text-zinc-300" viewBox="0 0 24 36" fill="none">
            <path d="M12 0 V30" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M7 25 L12 32 L17 25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>

          {/* NODE 4: Interactive QC Table */}
          <button
            type="button"
            disabled={!isCompleted}
            onClick={() => onSelectNode("qc")}
            className={`group w-88 rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition ${
              isCompleted
                ? "border-emerald-200 hover:-translate-y-0.5 hover:border-emerald-400 hover:shadow-md"
                : "cursor-not-allowed border-zinc-200 opacity-60"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600">
                  <Table2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-zinc-900">
                    Interactive Spreadsheet QC
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    4 Tab Filter Cepat • Auto-Sync SQLite Bulanan
                  </div>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-zinc-300 transition group-hover:text-emerald-600" />
            </div>
            {tabs && (
              <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] font-semibold">
                <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-zinc-700">
                  Semua: {tabs.all}
                </span>
                <span className="rounded-md bg-amber-100 px-2 py-0.5 text-amber-800">
                  00:00: {tabs.cutoff_00}
                </span>
                <span className="rounded-md bg-red-100 px-2 py-0.5 text-red-700">
                  Takeout: {tabs.takeout}
                </span>
                <span className="rounded-md bg-purple-100 px-2 py-0.5 text-purple-800">
                  Mirip Judul: {tabs.near_dup}
                </span>
              </div>
            )}
          </button>

          {/* 3-Way Branching SVG Connector 4 -> 5a / 5b / 5c */}
          <svg className="h-12 w-full max-w-3xl text-blue-300" viewBox="0 0 600 48" fill="none">
            <path d="M300 0 V20" stroke="currentColor" strokeWidth="2" />
            <path d="M100 20 H500" stroke="currentColor" strokeWidth="2" />
            <path d="M100 20 V42" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M300 20 V42" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M500 20 V42" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
            <path d="M95 37 L100 44 L105 37" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M295 37 L300 44 L305 37" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M495 37 L500 44 L505 37" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>

          {/* NODE 5a, 5b, 5c: Triple Deliverables Branch */}
          <div className="grid w-full max-w-3xl grid-cols-3 gap-4">
            <button
              type="button"
              disabled={!isCompleted}
              onClick={() => onSelectNode("export_excel")}
              className={`group rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition ${
                isCompleted
                  ? "border-emerald-200 hover:-translate-y-0.5 hover:border-emerald-400 hover:shadow-md"
                  : "cursor-not-allowed border-zinc-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
                  <FileSpreadsheet className="h-4 w-4" />
                </div>
                <ArrowUpRight className="h-4 w-4 text-zinc-300 group-hover:text-emerald-600" />
              </div>
              <div className="mt-2.5 text-xs font-bold text-zinc-900">Excel Cleaned</div>
              <div className="mt-0.5 text-[11px] text-zinc-500">
                8 Pivot + 6 Chart • Column Picker
              </div>
            </button>

            <button
              type="button"
              disabled={!isCompleted}
              onClick={() => onSelectNode("export_pptx")}
              className={`group rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition ${
                isCompleted
                  ? "border-blue-200 hover:-translate-y-0.5 hover:border-blue-400 hover:shadow-md"
                  : "cursor-not-allowed border-zinc-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
                  <Presentation className="h-4 w-4" />
                </div>
                <ArrowUpRight className="h-4 w-4 text-zinc-300 group-hover:text-blue-700" />
              </div>
              <div className="mt-2.5 text-xs font-bold text-zinc-900">Report PPTX/PDF</div>
              <div className="mt-0.5 text-[11px] text-zinc-500">
                Smart In-Place Template Update
              </div>
            </button>

            <button
              type="button"
              disabled={!isCompleted}
              onClick={() => onSelectNode("export_wording")}
              className={`group rounded-2xl border-2 bg-white p-4 text-left shadow-xs transition ${
                isCompleted
                  ? "border-sky-200 hover:-translate-y-0.5 hover:border-sky-400 hover:shadow-md"
                  : "cursor-not-allowed border-zinc-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
                  <FileText className="h-4 w-4" />
                </div>
                <ArrowUpRight className="h-4 w-4 text-zinc-300 group-hover:text-sky-600" />
              </div>
              <div className="mt-2.5 text-xs font-bold text-zinc-900">Teks Wording</div>
              <div className="mt-0.5 text-[11px] text-zinc-500">
                100% Sinkron • Copy-to-Clipboard
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Collapsible Run Log Console (like reference image) */}
      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xs">
        <button
          type="button"
          onClick={() => setLogOpen((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
        >
          <span className="inline-flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-blue-600" />
            RUN LOG • {project.name}
          </span>
          <span className="inline-flex items-center gap-2 text-[11px] font-normal text-zinc-500">
            {isCompleted ? "Status: Completed (0 errors)" : `Status: ${project.status}`}
            {logOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </span>
        </button>

        {logOpen && (
          <div className="border-t border-zinc-100 bg-zinc-50/70 px-4 py-3 font-mono text-[11px] text-zinc-600">
            {isCompleted && meta ? (
              <div className="space-y-1">
                <div>
                  <span className="text-emerald-600">●</span> [Pre-Cleaning] Raw: {meta.total_raw} baris → Keep: {meta.total_clean} | Takeout: {meta.total_takeout} | Cutoff: {meta.cutoff_wib}
                </div>
                <div>
                  <span className="text-emerald-600">●</span> [Media Tier] {Object.entries(tiers).map(([k, v]) => `${k}: ${v}`).join(" • ") || "Unassigned"}
                </div>
                <div>
                  <span className="text-emerald-600">●</span> [Sentiment] Positif: {sent?.positive ?? 0} | Netral: {sent?.neutral ?? 0} | Negatif: {sent?.negative ?? 0}
                </div>
                <div>
                  <span className="text-emerald-600">●</span> [Deliverables] Siap ekspor Excel (8 Pivot + 6 Chart), PPTX (Smart Template), &amp; Wording — klik node di atas untuk detail.
                </div>
              </div>
            ) : (
              <div>
                <span className="text-blue-600">●</span> Project dibuat. Klik node <strong>Input Raw Data</strong> di atas untuk mengunggah file <code>.xls with Statements</code> dan menjalankan pipeline.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
