"use client";

import React, { useMemo, useState } from "react";
import { Save, Search, ExternalLink, CheckCircle2 } from "lucide-react";
import { QCResponse, QCRow, saveQCEdits } from "@/lib/api";

type FilterTab = "all" | "cutoff_00" | "takeout" | "rilis_spk_zero" | "near_dup";

interface QCTablePanelProps {
  qcData: QCResponse;
  onRefresh: () => Promise<void>;
}

export default function QCTablePanel({ qcData, onRefresh }: QCTablePanelProps) {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [search, setSearch] = useState<string>("");
  const [localRows, setLocalRows] = useState<QCRow[]>(qcData.rows);
  const [dirtyIds, setDirtyIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>("");

  React.useEffect(() => {
    setLocalRows(qcData.rows);
    setDirtyIds(new Set());
  }, [qcData]);

  const updateCell = (id: string, field: string, value: string) => {
    setLocalRows((prev) =>
      prev.map((row) => (row.ID === id ? { ...row, [field]: value } : row))
    );
    setDirtyIds((prev) => new Set(prev).add(id));
    setSaveMessage("");
  };

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return localRows.filter((row) => {
      if (activeTab === "cutoff_00" && row.Flag_Cutoff_00 !== "CEK_CUTOFF_00:00") return false;
      if (activeTab === "takeout" && row.Status_Takeout === "Keep") return false;
      if (
        activeTab === "rilis_spk_zero" &&
        !(
          row.Status_Takeout === "Keep" &&
          String(row.Content_Type || "").toLowerCase() === "rilis" &&
          ["", "0"].includes(String(row.Spokesperson || "").trim())
        )
      ) {
        return false;
      }
      if (activeTab === "near_dup" && row.Flag_Near_Dup !== "CEK_MIRIP_JUDUL") return false;

      if (q) {
        const hay = `${row.Title || ""} ${row["Media Name"] || ""} ${row.Newstrends || ""} ${row.Spokesperson || ""} ${row.Alasan_Spam || ""}`.toLowerCase();
        return hay.includes(q);
      }
      return true;
    });
  }, [localRows, activeTab, search]);

  const handleSave = async () => {
    if (dirtyIds.size === 0) return;
    setSaving(true);
    try {
      const edits = localRows.filter((r) => dirtyIds.has(r.ID));
      const res = await saveQCEdits(qcData.job_id, edits);
      setSaveMessage(
        `Tersimpan ${res.updated_count} baris (${res.synced_takeouts} takeout disinkronkan ke SQLite).`
      );
      await onRefresh();
    } finally {
      setSaving(false);
    }
  };

  const tabs: Array<{ id: FilterTab; label: string; count: number; badgeClass: string }> = [
    { id: "all", label: "Semua Berita", count: qcData.tab_counts.all, badgeClass: "bg-slate-100 text-slate-700" },
    { id: "cutoff_00", label: "Perlu Dicek (00:00)", count: qcData.tab_counts.cutoff_00, badgeClass: "bg-amber-100 text-amber-800" },
    { id: "takeout", label: "Takeout & Alasan Spam", count: qcData.tab_counts.takeout, badgeClass: "bg-red-100 text-red-700" },
    { id: "rilis_spk_zero", label: "Berita Rilis & Spokesperson (0)", count: qcData.tab_counts.rilis_spk_zero, badgeClass: "bg-indigo-100 text-indigo-700" },
    { id: "near_dup", label: "Mirip Judul (Flag_Near_Dup)", count: qcData.tab_counts.near_dup, badgeClass: "bg-purple-100 text-purple-700" },
  ];

  const meta = qcData.report_payload.meta;
  const sent = qcData.report_payload.sentiment_summary;

  return (
    <div className="space-y-4">
      {/* KPI Summary Bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Total Raw / Clean</div>
          <div className="text-lg font-bold text-slate-900">
            {meta.total_raw} / <span className="text-blue-700">{meta.total_clean}</span>
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Takeout</div>
          <div className="text-lg font-bold text-red-600">{meta.total_takeout}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Positif</div>
          <div className="text-lg font-bold text-emerald-700">{sent.positive}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Netral</div>
          <div className="text-lg font-bold text-slate-600">{sent.neutral}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Negatif</div>
          <div className="text-lg font-bold text-rose-700">{sent.negative}</div>
        </div>
      </div>

      {/* 4 Quick Filter Tabs + Search + Save */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === t.id
                    ? "bg-blue-700 text-white shadow-sm"
                    : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span>{t.label}</span>
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                    activeTab === t.id ? "bg-blue-600 text-white" : t.badgeClass
                  }`}
                >
                  {t.count}
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari judul, media, isu..."
                className="rounded-lg border border-slate-300 py-1.5 pl-8 pr-3 text-xs focus:border-blue-500 focus:outline-none"
              />
            </div>

            <button
              type="button"
              disabled={dirtyIds.size === 0 || saving}
              onClick={handleSave}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? "Menyimpan..." : `Simpan Revisi (${dirtyIds.size})`}
            </button>
          </div>
        </div>

        {saveMessage && (
          <div className="mb-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            <span>{saveMessage}</span>
          </div>
        )}

        {/* Spreadsheet-style Editable Table */}
        <div className="max-h-[540px] overflow-auto rounded-lg border border-slate-200">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 z-10 bg-slate-800 text-white">
              <tr>
                <th className="px-2.5 py-2">Date/Time</th>
                <th className="px-2.5 py-2">Status</th>
                <th className="px-2.5 py-2">Alasan Spam / Takeout</th>
                <th className="px-2.5 py-2">Media &amp; Judul</th>
                <th className="px-2.5 py-2">Sentimen</th>
                <th className="px-2.5 py-2">Newstrends</th>
                <th className="px-2.5 py-2">Tipe</th>
                <th className="px-2.5 py-2">Spokesperson / Jabatan</th>
                {qcData.adhoc_columns.map((ac) => (
                  <th key={ac} className="px-2.5 py-2">
                    {ac}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {filteredRows.map((row) => {
                const isCutoff00 = row.Flag_Cutoff_00 === "CEK_CUTOFF_00:00";
                const isTakeout = row.Status_Takeout !== "Keep";
                return (
                  <tr
                    key={row.ID}
                    className={
                      isCutoff00
                        ? "bg-amber-50/70"
                        : isTakeout
                        ? "bg-red-50/40"
                        : "hover:bg-slate-50"
                    }
                  >
                    <td className="whitespace-nowrap px-2.5 py-2 align-top">
                      <div className="font-medium text-slate-800">{row.Date}</div>
                      <div className={isCutoff00 ? "font-bold text-amber-700" : "text-slate-500"}>
                        {row.Time} {isCutoff00 ? "⚠" : ""}
                      </div>
                    </td>
                    <td className="px-2 py-2 align-top">
                      <select
                        value={String(row.Status_Takeout || "Keep")}
                        onChange={(e) => updateCell(row.ID, "Status_Takeout", e.target.value)}
                        className="rounded border border-slate-300 bg-white px-1.5 py-1 text-xs"
                      >
                        <option value="Keep">Keep</option>
                        <option value="Takeout">Takeout</option>
                      </select>
                    </td>
                    <td className="px-2 py-2 align-top">
                      <input
                        type="text"
                        value={String(row.Alasan_Spam || "")}
                        onChange={(e) => updateCell(row.ID, "Alasan_Spam", e.target.value)}
                        placeholder="-"
                        className="w-40 rounded border border-slate-200 px-1.5 py-1 text-xs"
                      />
                    </td>
                    <td className="max-w-xs px-2.5 py-2 align-top">
                      <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                        <span>{row["Media Name"]}</span>
                        {row["Page/URL"] ? (
                          <a
                            href={String(row["Page/URL"])}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 hover:text-blue-800"
                            title={String(row["Page/URL"])}
                          >
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : null}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-slate-600">{row.Title}</div>
                      {row.Flag_Near_Dup ? (
                        <span className="mt-1 inline-block rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-800">
                          {row.Flag_Near_Dup}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 align-top">
                      <select
                        value={String(row.Sentiment || "neutral").toLowerCase()}
                        onChange={(e) => updateCell(row.ID, "Sentiment", e.target.value)}
                        className="rounded border border-slate-300 bg-white px-1.5 py-1 text-xs"
                      >
                        <option value="positive">positive</option>
                        <option value="neutral">neutral</option>
                        <option value="negative">negative</option>
                      </select>
                    </td>
                    <td className="px-2 py-2 align-top">
                      <input
                        type="text"
                        value={String(row.Newstrends || "")}
                        onChange={(e) => updateCell(row.ID, "Newstrends", e.target.value)}
                        className="w-52 rounded border border-slate-200 px-1.5 py-1 text-xs"
                      />
                    </td>
                    <td className="px-2 py-2 align-top">
                      <select
                        value={String(row.Content_Type || "Organik")}
                        onChange={(e) => updateCell(row.ID, "Content_Type", e.target.value)}
                        className="rounded border border-slate-300 bg-white px-1.5 py-1 text-xs"
                      >
                        <option value="Rilis">Rilis</option>
                        <option value="Organik">Organik</option>
                      </select>
                    </td>
                    <td className="space-y-1 px-2 py-2 align-top">
                      <input
                        type="text"
                        value={String(row.Spokesperson || "0")}
                        onChange={(e) => updateCell(row.ID, "Spokesperson", e.target.value)}
                        placeholder="Spokesperson"
                        className="block w-36 rounded border border-slate-200 px-1.5 py-1 text-xs"
                      />
                      <input
                        type="text"
                        value={String(row.Jabatan || "0")}
                        onChange={(e) => updateCell(row.ID, "Jabatan", e.target.value)}
                        placeholder="Jabatan"
                        className="block w-36 rounded border border-slate-200 px-1.5 py-1 text-xs text-slate-600"
                      />
                    </td>
                    {qcData.adhoc_columns.map((ac) => (
                      <td key={ac} className="px-2 py-2 align-top">
                        <input
                          type="text"
                          value={String(row[ac] || "")}
                          onChange={(e) => updateCell(row.ID, ac, e.target.value)}
                          className="w-32 rounded border border-slate-200 px-1.5 py-1 text-xs"
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={8 + qcData.adhoc_columns.length} className="px-4 py-8 text-center text-slate-400">
                    Tidak ada baris yang cocok dengan filter ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
