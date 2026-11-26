"use client";

import React, { useState } from "react";
import {
  FileSpreadsheet,
  Filter,
  Sparkles,
  Download,
  ChevronDown,
  ChevronUp,
  Terminal,
  ArrowUpRight,
} from "lucide-react";
import { ProjectItem, QCResponse } from "@/lib/api";

export type WorkflowNodeId = "upload" | "preclean" | "ai" | "export";

interface WorkflowCanvasProps {
  project: ProjectItem;
  qcData: QCResponse | null;
  onSelectNode: (nodeId: WorkflowNodeId) => void;
}

function VerticalConnector() {
  return (
    <svg className="h-8 w-5 text-zinc-200" viewBox="0 0 20 32" fill="none">
      <path d="M10 0 V26" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M6.5 22.5 L10 27 L13.5 22.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function WorkflowCanvas({
  project,
  qcData,
  onSelectNode,
}: WorkflowCanvasProps) {
  const [logOpen, setLogOpen] = useState<boolean>(true);
  const hasRaw =
    Boolean(project.latest_job_id) ||
    ["raw_uploaded", "precleaned", "completed"].includes(project.status);
  const hasPrecleaned =
    qcData !== null || ["precleaned", "completed"].includes(project.status);
  const isCompleted = project.status === "completed" && qcData !== null;

  const meta = qcData?.report_payload.meta;
  const sent = qcData?.report_payload.sentiment_summary;
  const tiers = qcData?.report_payload.media_breakdown.by_custom_tier || {};

  const statusDot = (done: boolean, pendingLabel: string) => (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-zinc-500">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          done ? "bg-emerald-500" : "bg-zinc-300"
        }`}
      />
      <span className={done ? "text-zinc-700" : "text-zinc-400"}>
        {done ? "Done" : pendingLabel}
      </span>
    </span>
  );

  const nodeBase =
    "group w-full max-w-[400px] rounded-xl border border-zinc-200 bg-white px-4 py-3.5 text-left transition duration-150 hover:border-blue-400/80 hover:shadow-xs";
  const iconBox =
    "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-200/80 bg-zinc-50 text-zinc-600 transition group-hover:border-blue-200 group-hover:bg-blue-50/50 group-hover:text-blue-600";

  return (
    <div className="space-y-4">
      {/* Main Minimalist Vertical Node Canvas */}
      <div className="rounded-2xl border border-zinc-200/90 bg-white/70 px-6 py-8 shadow-2xs backdrop-blur-[1px]">
        <div className="mx-auto flex flex-col items-center">
          {/* NODE 1: Input Raw Data */}
          <button
            type="button"
            onClick={() => onSelectNode("upload")}
            className={nodeBase}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={iconBox}>
                  <FileSpreadsheet className="h-4 w-4" strokeWidth={1.6} />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-zinc-900">
                    Input Raw Data
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    .xls with Statements
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-0.5">
                {statusDot(hasRaw, "Upload")}
                <ArrowUpRight className="h-3.5 w-3.5 text-zinc-300 transition group-hover:text-blue-600" />
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2.5 text-[11px] text-zinc-500">
              <span className="truncate">
                <strong className="font-semibold uppercase text-zinc-800">
                  {project.client_id}
                </strong>
                {project.cutoff_datetime ? ` · ${project.cutoff_datetime}` : ""}
              </span>
              <span className="shrink-0 font-mono text-[11px] font-semibold text-zinc-700">
                {hasRaw ? `${meta?.total_raw ?? project.total_raw} raw` : "—"}
              </span>
            </div>
          </button>

          <VerticalConnector />

          {/* NODE 2: Pre-Cleaning & Media Tier */}
          <button
            type="button"
            onClick={() => onSelectNode("preclean")}
            className={nodeBase}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={iconBox}>
                  <Filter className="h-4 w-4" strokeWidth={1.6} />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-zinc-900">
                    Pre-Cleaning &amp; Media Tier
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Cutoff 00:00 · Dedup 3-Lapis · Custom Tier
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-0.5">
                {statusDot(hasPrecleaned, hasRaw ? "Ready" : "Waiting")}
                <ArrowUpRight className="h-3.5 w-3.5 text-zinc-300 transition group-hover:text-blue-600" />
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2.5 text-[11px]">
              {meta ? (
                <div className="flex w-full items-center justify-between text-zinc-500">
                  <span>
                    <strong className="font-semibold text-emerald-700">
                      {meta.total_clean}
                    </strong>{" "}
                    Keep
                  </span>
                  <span className="text-zinc-300">·</span>
                  <span>
                    <strong className="font-semibold text-rose-600">
                      {meta.total_takeout}
                    </strong>{" "}
                    Takeout
                  </span>
                  <span className="text-zinc-300">·</span>
                  <span>
                    <strong className="font-semibold text-zinc-800">
                      {tiers["Tier 1"] ?? 0}
                    </strong>{" "}
                    Tier 1
                  </span>
                </div>
              ) : (
                <span className="text-zinc-400">
                  Jalankan cleaning &amp; lihat preview Raw vs Bersih
                </span>
              )}
            </div>
          </button>

          <VerticalConnector />

          {/* NODE 3: 3-Pass Cloud AI Engine */}
          <button
            type="button"
            onClick={() => onSelectNode("ai")}
            className={nodeBase}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={iconBox}>
                  <Sparkles className="h-4 w-4" strokeWidth={1.6} />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-zinc-900">
                    3-Pass Cloud AI Engine
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Sentimen · Newstrend · Spokesperson · Ad-Hoc
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-0.5">
                {statusDot(isCompleted, hasPrecleaned ? "Ready" : "Waiting")}
                <ArrowUpRight className="h-3.5 w-3.5 text-zinc-300 transition group-hover:text-blue-600" />
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2.5 text-[11px]">
              {isCompleted && sent ? (
                <div className="flex w-full items-center justify-between text-zinc-600">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <strong className="font-semibold text-zinc-900">
                      {sent.positive}
                    </strong>{" "}
                    Pos
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                    <strong className="font-semibold text-zinc-900">
                      {sent.neutral}
                    </strong>{" "}
                    Neu
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                    <strong className="font-semibold text-zinc-900">
                      {sent.negative}
                    </strong>{" "}
                    Neg
                  </span>
                </div>
              ) : (
                <span className="text-zinc-400">
                  Kirim data bersih ke Cloud AI Engine (Live SSE)
                </span>
              )}
            </div>
          </button>

          <VerticalConnector />

          {/* NODE 4: Ekspor 3 Output Klien */}
          <button
            type="button"
            disabled={!hasPrecleaned}
            onClick={() => onSelectNode("export")}
            className={`${nodeBase} disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:border-zinc-200 disabled:hover:shadow-none`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={iconBox}>
                  <Download className="h-4 w-4" strokeWidth={1.6} />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-zinc-900">
                    Ekspor 3 Output Klien
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Column Picker · Template PPTX · Wording
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-0.5">
                {statusDot(hasPrecleaned, "Waiting")}
                <ArrowUpRight className="h-3.5 w-3.5 text-zinc-300 transition group-hover:text-blue-600" />
              </div>
            </div>

            <div className="mt-3 flex items-center gap-1.5 border-t border-zinc-100 pt-2.5 text-[10px] font-medium text-zinc-600">
              <span className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5">
                Excel (.xlsx)
              </span>
              <span className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5">
                Report (.pptx)
              </span>
              <span className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5">
                Wording (.txt)
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* Bottom Collapsible Run Log Console */}
      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xs">
        <button
          type="button"
          onClick={() => setLogOpen((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
        >
          <span className="inline-flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.6} />
            <span className="font-semibold text-zinc-800">Run Log</span>
            <span className="text-zinc-400">· {project.name}</span>
          </span>
          <span className="inline-flex items-center gap-2 text-[11px] text-zinc-500">
            {isCompleted
              ? "Completed (0 errors)"
              : hasPrecleaned
              ? "Pre-Cleaned"
              : hasRaw
              ? "Raw Staged"
              : "Draft"}
            {logOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          </span>
        </button>

        {logOpen && (
          <div className="border-t border-zinc-100 bg-zinc-50/70 px-4 py-3 font-mono text-[11px] text-zinc-600">
            {hasPrecleaned && meta ? (
              <div className="space-y-1">
                <div>
                  <span className="text-emerald-600">●</span> [Pre-Cleaning] Raw: {meta.total_raw} baris → Keep: {meta.total_clean} | Takeout: {meta.total_takeout} | Cutoff: {meta.cutoff_wib}
                </div>
                <div>
                  <span className="text-emerald-600">●</span> [Media Tier] {Object.entries(tiers).map(([k, v]) => `${k}: ${v}`).join(" · ") || "Unassigned"}
                </div>
                {isCompleted && sent && (
                  <div>
                    <span className="text-emerald-600">●</span> [Sentiment] Positif: {sent.positive} | Netral: {sent.neutral} | Negatif: {sent.negative}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-zinc-400">
                Belum ada proses dijalankan. Klik node &ldquo;Input Raw Data&rdquo; untuk mengunggah file .xls/.xlsx.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
