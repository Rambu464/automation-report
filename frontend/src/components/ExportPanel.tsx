"use client";

import React, { useState } from "react";
import { Download, Copy, Check, FileSpreadsheet, Presentation, FileText, Sparkles } from "lucide-react";
import { API_BASE, ExportResponse, QCResponse, exportDeliverables } from "@/lib/api";

interface ExportPanelProps {
  qcData: QCResponse;
}

const INTERNAL_HELPER_COLUMNS = new Set([
  "Content_Clean",
  "Content_Snippet",
  "Normalized_URL",
  "Cluster_ID",
  "Is_Cluster_Rep",
  "Has_Statement",
  "AI_Spokesperson",
  "AI_Jabatan",
  "Domain",
]);

export default function ExportPanel({ qcData }: ExportPanelProps) {
  const availableColumns = qcData.columns.filter((c) => !INTERNAL_HELPER_COLUMNS.has(c));
  const [selectedCols, setSelectedCols] = useState<string[]>(
    availableColumns.filter((c) => !["Flag_Cutoff_00", "Flag_Near_Dup", "Alasan_Spam"].includes(c))
  );
  const [exportPdf, setExportPdf] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ExportResponse | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const toggleCol = (col: string) => {
    setSelectedCols((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    );
  };

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await exportDeliverables(qcData.job_id, selectedCols, exportPdf);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyWording = async () => {
    if (!result?.wording_text) return;
    await navigator.clipboard.writeText(result.wording_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Left: Client Export Column Picker */}
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Client Export Column Picker
            </h2>
            <p className="text-xs text-slate-500">
              Pilih kolom yang disertakan pada sheet <code>News_Clean</code> file Excel klien.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSelectedCols(availableColumns)}
              className="rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Pilih Semua
            </button>
            <button
              type="button"
              onClick={() =>
                setSelectedCols(
                  availableColumns.filter(
                    (c) => !["Flag_Cutoff_00", "Flag_Near_Dup", "Alasan_Spam"].includes(c)
                  )
                )
              }
              className="rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Standar Klien
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {availableColumns.map((col) => (
            <label
              key={col}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs hover:bg-slate-50"
            >
              <input
                type="checkbox"
                checked={selectedCols.includes(col)}
                onChange={() => toggleCol(col)}
                className="h-3.5 w-3.5 rounded text-blue-600"
              />
              <span className="truncate font-medium text-slate-700">{col}</span>
            </label>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={exportPdf}
              onChange={(e) => setExportPdf(e.target.checked)}
              className="h-3.5 w-3.5 rounded text-blue-600"
            />
            Konversi PPTX ke PDF (memerlukan LibreOffice lokal)
          </label>

          <button
            type="button"
            disabled={loading || selectedCols.length === 0}
            onClick={handleGenerate}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {loading ? "Menyusun 3 Output..." : "Generate 3 Output Utama"}
          </button>
        </div>
      </div>

      {/* Right: Triple Deliverable Downloads & Copy Wording */}
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">
          3 Output Utama Klien (100% Sinkron)
        </h2>

        {!result ? (
          <p className="rounded-lg bg-slate-50 p-6 text-center text-sm text-slate-400">
            Klik <strong>Generate 3 Output Utama</strong> untuk mengunduh Excel Cleaned, Report PPTX/PDF, dan menyalin Teks Wording.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <a
                href={`${API_BASE}${result.excel_url}`}
                className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-900 transition hover:bg-emerald-100"
              >
                <span className="flex items-center gap-2">
                  <FileSpreadsheet className="h-5 w-5 text-emerald-700" />
                  Output 1: Excel (.xlsx)
                </span>
                <Download className="h-4 w-4" />
              </a>

              <a
                href={`${API_BASE}${result.pptx_url}`}
                className="flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-900 transition hover:bg-blue-100"
              >
                <span className="flex items-center gap-2">
                  <Presentation className="h-5 w-5 text-blue-700" />
                  Output 2: Report (.pptx)
                </span>
                <Download className="h-4 w-4" />
              </a>

              {result.pdf_url && (
                <a
                  href={`${API_BASE}${result.pdf_url}`}
                  className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900 transition hover:bg-rose-100"
                >
                  <span className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-rose-700" />
                    Output 2b: Report (.pdf)
                  </span>
                  <Download className="h-4 w-4" />
                </a>
              )}
            </div>

            {/* Output 3: Wording Email */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Output 3: Teks Wording Pengantar Email
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCopyWording}
                    className="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-900"
                  >
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied ? "Tersalin!" : "Copy Wording"}
                  </button>
                  <a
                    href={`${API_BASE}${result.wording_url}`}
                    className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    <Download className="h-3.5 w-3.5" />
                    .txt
                  </a>
                </div>
              </div>
              <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded bg-white p-3 font-sans text-xs leading-relaxed text-slate-800">
                {result.wording_text}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
