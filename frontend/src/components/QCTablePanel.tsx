"use client";

import React, { useMemo, useState } from "react";
import {
  Save,
  Search,
  ExternalLink,
  CheckCircle2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  Plus,
  X,
  AlertCircle,
} from "lucide-react";
import { QCResponse, QCRow, addQCRow, saveQCEdits } from "@/lib/api";

type FilterTab = "all" | "cutoff_00" | "takeout" | "rilis_spk_zero" | "near_dup";
type SortDir = "asc" | "desc";

interface QCTablePanelProps {
  qcData: QCResponse;
  onRefresh: () => Promise<void>;
}

const EMPTY_TOKEN = "__EMPTY__";

export default function QCTablePanel({ qcData, onRefresh }: QCTablePanelProps) {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [search, setSearch] = useState<string>("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [colFilters, setColFilters] = useState<Record<string, string>>({});
  const [localRows, setLocalRows] = useState<QCRow[]>(qcData.rows);
  const [dirtyIds, setDirtyIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>("");

  // Insert Row Modal (Manual Req Upload)
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [addUrl, setAddUrl] = useState<string>("");
  const [addMedia, setAddMedia] = useState<string>("");
  const [addTitle, setAddTitle] = useState<string>("");
  const [addDate, setAddDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [addTime, setAddTime] = useState<string>("12:00");
  const [addSentiment, setAddSentiment] = useState<"positive" | "neutral" | "negative">("positive");
  const [addType, setAddType] = useState<"Rilis" | "Organik">("Rilis");
  const [addNewstrend, setAddNewstrend] = useState<string>("");
  const [addSpokesperson, setAddSpokesperson] = useState<string>("");
  const [addJabatan, setAddJabatan] = useState<string>("");
  const [addAdhoc, setAddAdhoc] = useState<Record<string, string>>({});
  const [addingRow, setAddingRow] = useState<boolean>(false);
  const [addErr, setAddErr] = useState<string>("");

  const handleUrlInputChange = (url: string) => {
    setAddUrl(url);
    if (!addMedia.trim() && url.trim()) {
      try {
        const parsed = new URL(url.startsWith("http") ? url : `https://${url}`);
        const host = parsed.hostname.replace(/^(www\.|m\.|amp\.)/i, "");
        if (host) setAddMedia(host);
      } catch {
        // ignore partial URL while typing
      }
    }
  };

  const handleInsertRow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addUrl.trim()) {
      setAddErr("URL berita wajib diisi.");
      return;
    }
    if (!addTitle.trim()) {
      setAddErr("Judul berita wajib diisi.");
      return;
    }
    setAddingRow(true);
    setAddErr("");
    try {
      const res = await addQCRow(qcData.job_id, {
        page_url: addUrl.trim(),
        media_name: addMedia.trim(),
        title: addTitle.trim(),
        date: addDate,
        time: addTime,
        sentiment: addSentiment,
        content_type: addType,
        newstrends: addNewstrend.trim(),
        spokesperson: addSpokesperson.trim() || "0",
        jabatan: addJabatan.trim() || "0",
        adhoc: addAdhoc,
      });
      setShowAddModal(false);
      setAddUrl("");
      setAddMedia("");
      setAddTitle("");
      setAddNewstrend("");
      setAddSpokesperson("");
      setAddJabatan("");
      setAddAdhoc({});
      setSaveMessage(
        `Berita Req Upload "${res.row["Media Name"]}" berhasil ditambahkan (Tier: ${res.row["Media Tier"] || "-"}).`
      );
      await onRefresh();
    } catch (err) {
      setAddErr(err instanceof Error ? err.message : "Gagal menambahkan berita.");
    } finally {
      setAddingRow(false);
    }
  };

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

  const setColFilter = (key: string, val: string) => {
    setColFilters((prev) => {
      const next = { ...prev };
      if (!val) {
        delete next[key];
      } else {
        next[key] = val;
      }
      return next;
    });
  };

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // Date/Time defaults to newest first; text columns default to A-Z
      setSortDir(key === "datetime" ? "desc" : "asc");
    }
  };

  const hasActiveFiltersOrSort =
    activeTab !== "all" ||
    search.trim().length > 0 ||
    Object.keys(colFilters).length > 0 ||
    sortKey !== null;

  const resetFiltersAndSort = () => {
    setActiveTab("all");
    setSearch("");
    setColFilters({});
    setSortKey(null);
    setSortDir("desc");
  };

  // Unique dropdown values for Excel-style column filters
  const uniqueOptions = useMemo(() => {
    const collect = (getter: (r: QCRow) => string, sortDesc = false): string[] => {
      const set = new Set<string>();
      for (const r of localRows) {
        const v = getter(r).trim();
        if (v) set.add(v);
      }
      return Array.from(set).sort((a, b) =>
        sortDesc ? b.localeCompare(a) : a.localeCompare(b)
      );
    };

    const adhocOpts: Record<string, string[]> = {};
    for (const ac of qcData.adhoc_columns) {
      adhocOpts[ac] = collect((r) => String(r[ac] || ""));
    }

    return {
      dates: collect((r) => String(r.Date || ""), true),
      reasons: collect((r) => String(r.Alasan_Spam || "")),
      newstrends: collect((r) => String(r.Newstrends || "")),
      adhoc: adhocOpts,
    };
  }, [localRows, qcData.adhoc_columns]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = localRows.filter((row) => {
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

      // Per-column Excel-style filters
      if (colFilters.Date && String(row.Date || "").trim() !== colFilters.Date) return false;
      if (colFilters.Status_Takeout && String(row.Status_Takeout || "Keep") !== colFilters.Status_Takeout) {
        return false;
      }
      if (colFilters.Alasan_Spam) {
        const val = String(row.Alasan_Spam || "").trim();
        if (colFilters.Alasan_Spam === EMPTY_TOKEN) {
          if (val !== "") return false;
        } else if (val !== colFilters.Alasan_Spam) {
          return false;
        }
      }
      if (colFilters.mediaTitle) {
        const mt = colFilters.mediaTitle.toLowerCase();
        const hayMt = `${row["Media Name"] || ""} ${row.Title || ""}`.toLowerCase();
        if (!hayMt.includes(mt)) return false;
      }
      if (
        colFilters.Sentiment &&
        String(row.Sentiment || "neutral").toLowerCase() !== colFilters.Sentiment
      ) {
        return false;
      }
      if (colFilters.Newstrends) {
        const val = String(row.Newstrends || "").trim();
        if (colFilters.Newstrends === EMPTY_TOKEN) {
          if (val !== "") return false;
        } else if (val !== colFilters.Newstrends) {
          return false;
        }
      }
      if (
        colFilters.Content_Type &&
        String(row.Content_Type || "Organik").toLowerCase() !== colFilters.Content_Type.toLowerCase()
      ) {
        return false;
      }
      if (colFilters.spokesperson) {
        const sp = colFilters.spokesperson.toLowerCase();
        const haySp = `${row.Spokesperson || ""} ${row.Jabatan || ""}`.toLowerCase();
        if (!haySp.includes(sp)) return false;
      }
      for (const ac of qcData.adhoc_columns) {
        const fVal = colFilters[`adhoc:${ac}`];
        if (!fVal) continue;
        const cellVal = String(row[ac] || "").trim();
        if (fVal === EMPTY_TOKEN) {
          if (cellVal !== "") return false;
        } else if (cellVal !== fVal) {
          return false;
        }
      }

      if (q) {
        const hay = `${row.Title || ""} ${row["Media Name"] || ""} ${row.Newstrends || ""} ${row.Spokesperson || ""} ${row.Alasan_Spam || ""}`.toLowerCase();
        return hay.includes(q);
      }
      return true;
    });

    if (!sortKey) return filtered;

    const getSortValue = (row: QCRow): string => {
      if (sortKey === "datetime") {
        const d = String(row.Date || "").trim();
        const t = String(row.Time || "00:00").trim();
        return `${d} ${t}`;
      }
      if (sortKey === "mediaTitle") {
        return `${String(row["Media Name"] || "").toLowerCase()} ${String(row.Title || "").toLowerCase()}`;
      }
      return String(row[sortKey] || "").trim().toLowerCase();
    };

    const mul = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => getSortValue(a).localeCompare(getSortValue(b)) * mul);
  }, [localRows, activeTab, search, colFilters, sortKey, sortDir, qcData.adhoc_columns]);

  const renderSortIcon = (key: string) => {
    if (sortKey !== key) {
      return <ArrowUpDown className="h-3 w-3 shrink-0 opacity-45" />;
    }
    return sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3 shrink-0 text-sky-300" />
    ) : (
      <ArrowDown className="h-3 w-3 shrink-0 text-sky-300" />
    );
  };

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
              onClick={() => {
                setAddErr("");
                setShowAddModal(true);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-blue-600 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"
            >
              <Plus className="h-3.5 w-3.5" />
              Tambah Berita
            </button>

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

        {/* Row count + Quick Sort + Reset Filter bar */}
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-2">
            <span>
              Menampilkan <strong className="text-slate-900">{filteredRows.length}</strong> dari{" "}
              <strong className="text-slate-900">{localRows.length}</strong> baris
            </span>
            <span className="text-slate-300">|</span>
            <button
              type="button"
              onClick={() => {
                setSortKey("datetime");
                setSortDir("desc");
              }}
              className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition ${
                sortKey === "datetime" && sortDir === "desc"
                  ? "bg-blue-100 text-blue-800"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Terbaru ↓
            </button>
            <button
              type="button"
              onClick={() => {
                setSortKey("datetime");
                setSortDir("asc");
              }}
              className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition ${
                sortKey === "datetime" && sortDir === "asc"
                  ? "bg-blue-100 text-blue-800"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Terlama ↑
            </button>
          </div>

          {hasActiveFiltersOrSort && (
            <button
              type="button"
              onClick={resetFiltersAndSort}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            >
              <RotateCcw className="h-3 w-3" />
              Reset Filter &amp; Sort
            </button>
          )}
        </div>

        {/* Spreadsheet-style Editable Table with Excel-like Sorting & AutoFilter */}
        <div className="max-h-[540px] overflow-auto rounded-lg border border-slate-200">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 z-10">
              <tr className="bg-slate-800 text-white">
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("datetime")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                    title="Urutkan Tanggal & Jam (Terbaru / Terlama)"
                  >
                    Date/Time {renderSortIcon("datetime")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Status_Takeout")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Status {renderSortIcon("Status_Takeout")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Alasan_Spam")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Alasan Spam / Takeout {renderSortIcon("Alasan_Spam")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("mediaTitle")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Media &amp; Judul {renderSortIcon("mediaTitle")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Sentiment")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Sentimen {renderSortIcon("Sentiment")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Newstrends")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Newstrends {renderSortIcon("Newstrends")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Content_Type")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Tipe {renderSortIcon("Content_Type")}
                  </button>
                </th>
                <th className="whitespace-nowrap px-2.5 py-2">
                  <button
                    type="button"
                    onClick={() => handleSort("Spokesperson")}
                    className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                  >
                    Spokesperson / Jabatan {renderSortIcon("Spokesperson")}
                  </button>
                </th>
                {qcData.adhoc_columns.map((ac) => (
                  <th key={ac} className="whitespace-nowrap px-2.5 py-2">
                    <button
                      type="button"
                      onClick={() => handleSort(ac)}
                      className="inline-flex items-center gap-1 font-semibold hover:text-sky-200"
                    >
                      {ac} {renderSortIcon(ac)}
                    </button>
                  </th>
                ))}
              </tr>

              {/* Excel-style AutoFilter Row */}
              <tr className="border-b border-slate-300 bg-slate-100 text-slate-700">
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Date || ""}
                    onChange={(e) => setColFilter("Date", e.target.value)}
                    className="w-28 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua Tgl</option>
                    {uniqueOptions.dates.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Status_Takeout || ""}
                    onChange={(e) => setColFilter("Status_Takeout", e.target.value)}
                    className="w-20 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua</option>
                    <option value="Keep">Keep</option>
                    <option value="Takeout">Takeout</option>
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Alasan_Spam || ""}
                    onChange={(e) => setColFilter("Alasan_Spam", e.target.value)}
                    className="w-40 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua Alasan</option>
                    <option value={EMPTY_TOKEN}>(Kosong)</option>
                    {uniqueOptions.reasons.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <input
                    type="text"
                    value={colFilters.mediaTitle || ""}
                    onChange={(e) => setColFilter("mediaTitle", e.target.value)}
                    placeholder="Filter media/judul..."
                    className="w-full min-w-[140px] rounded border border-slate-300 bg-white px-2 py-1 text-[11px] focus:border-blue-500 focus:outline-none"
                  />
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Sentiment || ""}
                    onChange={(e) => setColFilter("Sentiment", e.target.value)}
                    className="w-24 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua</option>
                    <option value="positive">positive</option>
                    <option value="neutral">neutral</option>
                    <option value="negative">negative</option>
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Newstrends || ""}
                    onChange={(e) => setColFilter("Newstrends", e.target.value)}
                    className="w-52 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua Newstrends</option>
                    <option value={EMPTY_TOKEN}>(Kosong)</option>
                    {uniqueOptions.newstrends.map((nt) => (
                      <option key={nt} value={nt}>
                        {nt}
                      </option>
                    ))}
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <select
                    value={colFilters.Content_Type || ""}
                    onChange={(e) => setColFilter("Content_Type", e.target.value)}
                    className="w-22 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                  >
                    <option value="">Semua</option>
                    <option value="Rilis">Rilis</option>
                    <option value="Organik">Organik</option>
                  </select>
                </th>
                <th className="px-2 py-1.5 font-normal">
                  <input
                    type="text"
                    value={colFilters.spokesperson || ""}
                    onChange={(e) => setColFilter("spokesperson", e.target.value)}
                    placeholder="Filter narasumber..."
                    className="w-36 rounded border border-slate-300 bg-white px-2 py-1 text-[11px] focus:border-blue-500 focus:outline-none"
                  />
                </th>
                {qcData.adhoc_columns.map((ac) => (
                  <th key={ac} className="px-2 py-1.5 font-normal">
                    <select
                      value={colFilters[`adhoc:${ac}`] || ""}
                      onChange={(e) => setColFilter(`adhoc:${ac}`, e.target.value)}
                      className="w-32 rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px]"
                    >
                      <option value="">Semua</option>
                      <option value={EMPTY_TOKEN}>(Kosong)</option>
                      {(uniqueOptions.adhoc[ac] || []).map((val) => (
                        <option key={val} value={val}>
                          {val}
                        </option>
                      ))}
                    </select>
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

      {/* Insert Row Modal (Manual Req Upload) */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4 backdrop-blur-xs">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-zinc-900">
                  Tambah Berita Manual (Req Upload)
                </h3>
                <p className="text-xs text-zinc-500">
                  Insert baris baru ke tabel QC. Custom Media Tier otomatis dicocokkan dari domain URL.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleInsertRow} className="space-y-3.5 text-xs">
              <div>
                <label className="mb-1 block font-semibold text-zinc-700">
                  URL Berita (Page/URL) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="url"
                  required
                  value={addUrl}
                  onChange={(e) => handleUrlInputChange(e.target.value)}
                  placeholder="https://kompas.com/ekonomi/..."
                  autoFocus
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block font-semibold text-zinc-700">
                    Nama Media
                  </label>
                  <input
                    type="text"
                    value={addMedia}
                    onChange={(e) => setAddMedia(e.target.value)}
                    placeholder="Otomatis dari domain URL"
                    className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="mb-1 block font-semibold text-zinc-700">
                      Tanggal
                    </label>
                    <input
                      type="date"
                      value={addDate}
                      onChange={(e) => setAddDate(e.target.value)}
                      className="w-full rounded-xl border border-zinc-300 px-2.5 py-2 text-xs focus:border-blue-600 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block font-semibold text-zinc-700">
                      Jam (WIB)
                    </label>
                    <input
                      type="time"
                      value={addTime}
                      onChange={(e) => setAddTime(e.target.value)}
                      className="w-full rounded-xl border border-zinc-300 px-2.5 py-2 text-xs focus:border-blue-600 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="mb-1 block font-semibold text-zinc-700">
                  Judul Berita <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addTitle}
                  onChange={(e) => setAddTitle(e.target.value)}
                  placeholder="Masukkan judul lengkap berita..."
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-semibold text-zinc-700">
                    Sentimen <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={addSentiment}
                    onChange={(e) =>
                      setAddSentiment(e.target.value as "positive" | "neutral" | "negative")
                    }
                    className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  >
                    <option value="positive">positive</option>
                    <option value="neutral">neutral</option>
                    <option value="negative">negative</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block font-semibold text-zinc-700">
                    Tipe Berita <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={addType}
                    onChange={(e) => setAddType(e.target.value as "Rilis" | "Organik")}
                    className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  >
                    <option value="Rilis">Rilis</option>
                    <option value="Organik">Organik</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block font-semibold text-zinc-700">
                  Newstrends
                </label>
                <input
                  type="text"
                  value={addNewstrend}
                  onChange={(e) => setAddNewstrend(e.target.value)}
                  placeholder="Contoh: BNI Dorong Pembiayaan UMKM..."
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-semibold text-zinc-700">
                    Spokesperson
                  </label>
                  <input
                    type="text"
                    value={addSpokesperson}
                    onChange={(e) => setAddSpokesperson(e.target.value)}
                    placeholder="Kosongkan jika 0"
                    className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-semibold text-zinc-700">
                    Jabatan
                  </label>
                  <input
                    type="text"
                    value={addJabatan}
                    onChange={(e) => setAddJabatan(e.target.value)}
                    placeholder="Kosongkan jika 0"
                    className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  />
                </div>
              </div>

              {qcData.adhoc_columns.length > 0 && (
                <div className="grid grid-cols-2 gap-3 border-t border-zinc-100 pt-3">
                  {qcData.adhoc_columns.map((ac) => (
                    <div key={ac}>
                      <label className="mb-1 block font-semibold text-zinc-700">
                        {ac}
                      </label>
                      <input
                        type="text"
                        value={addAdhoc[ac] || ""}
                        onChange={(e) =>
                          setAddAdhoc((prev) => ({ ...prev, [ac]: e.target.value }))
                        }
                        placeholder={`Isi ${ac}...`}
                        className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                      />
                    </div>
                  ))}
                </div>
              )}

              {addErr && (
                <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{addErr}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 border-t border-zinc-100 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={addingRow}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {addingRow ? "Menyimpan..." : "Tambahkan ke Tabel QC"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
