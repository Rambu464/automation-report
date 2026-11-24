"use client";

import React, { useRef, useState } from "react";
import { UploadCloud, Play, CheckCircle2, AlertCircle, FileSpreadsheet } from "lucide-react";
import { JobEventPayload, subscribeJobStream, uploadJob } from "@/lib/api";

interface UploadPanelProps {
  clients: string[];
  selectedClient: string;
  onSelectClient: (c: string) => void;
  onJobCompleted: (jobId: string) => void;
}

export default function UploadPanel({
  clients,
  selectedClient,
  onSelectClient,
  onJobCompleted,
}: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [cutoffDatetime, setCutoffDatetime] = useState<string>("");
  const [reqUploadUrls, setReqUploadUrls] = useState<string>("");
  const [takedownUrls, setTakedownUrls] = useState<string>("");
  const [skipAi, setSkipAi] = useState<boolean>(false);

  const [running, setRunning] = useState<boolean>(false);
  const [percent, setPercent] = useState<number>(0);
  const [events, setEvents] = useState<JobEventPayload[]>([]);
  const [error, setError] = useState<string>("");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      setFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleStart = async () => {
    if (files.length === 0) {
      setError("Pilih minimal 1 file Excel (.xls / .xlsx with Statements) terlebih dahulu.");
      return;
    }
    setError("");
    setRunning(true);
    setPercent(5);
    setEvents([]);

    try {
      const normalizedCutoff = cutoffDatetime ? cutoffDatetime.replace("T", " ") : "";
      const { job_id } = await uploadJob({
        files,
        clientId: selectedClient,
        cutoffDatetime: normalizedCutoff,
        reqUploadUrls,
        takedownUrls,
        skipAi,
      });

      subscribeJobStream(
        job_id,
        (ev) => {
          setPercent(ev.percent);
          setEvents((prev) => [...prev, ev]);
          if (ev.event === "done") {
            setRunning(false);
            onJobCompleted(job_id);
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
      setError(err instanceof Error ? err.message : "Gagal memulai job.");
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Left: Upload & Parameters */}
      <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            1. Unggah Raw Data Newstensity (.xls with Statements)
          </h2>
          <p className="text-sm text-slate-500">
            Mendukung 1 file (Daily Report) maupun multi-file (Monthly Report) dengan sinkronisasi Takeout otomatis.
          </p>
        </div>

        {/* Drag and Drop Zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center transition hover:border-blue-500 hover:bg-blue-50/40"
        >
          <UploadCloud className="mb-3 h-10 w-10 text-blue-600" />
          <p className="text-sm font-medium text-slate-700">
            Tarik &amp; lepaskan file <span className="font-semibold">.xls / .xlsx</span> ke sini, atau klik untuk memilih
          </p>
          <p className="mt-1 text-xs text-slate-400">
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
          <div className="space-y-1 rounded-lg bg-blue-50/60 p-3">
            {files.map((f) => (
              <div key={f.name} className="flex items-center gap-2 text-sm text-blue-900">
                <FileSpreadsheet className="h-4 w-4 text-blue-600" />
                <span className="font-medium">{f.name}</span>
                <span className="text-xs text-blue-600">({(f.size / 1024).toFixed(1)} KB)</span>
              </div>
            ))}
          </div>
        )}

        {/* Client & Cutoff Row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Profil Klien
            </label>
            <select
              value={selectedClient}
              onChange={(e) => onSelectClient(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              {clients.map((c) => (
                <option key={c} value={c}>
                  {c.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Batas Tanggal &amp; Jam Cutoff (WIB, Opsional)
            </label>
            <input
              type="datetime-local"
              value={cutoffDatetime}
              onChange={(e) => setCutoffDatetime(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Optional Client URL Lists */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Daftar URL Req Upload (Opsional — 1 URL/baris)
            </label>
            <textarea
              rows={3}
              value={reqUploadUrls}
              onChange={(e) => setReqUploadUrls(e.target.value)}
              placeholder="https://kompas.com/..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Daftar URL Takedown Klien (Opsional — Auto Sync SQLite)
            </label>
            <textarea
              rows={3}
              value={takedownUrls}
              onChange={(e) => setTakedownUrls(e.target.value)}
              placeholder="https://portal.id/berita-takedown..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-4">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={skipAi}
              onChange={(e) => setSkipAi(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600"
            />
            Mode Pre-Clean Only (0 Token AI — tanpa panggilan LLM)
          </label>

          <button
            type="button"
            disabled={running}
            onClick={handleStart}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {running ? "Sedang Memproses..." : "Mulai Proses Otomasi"}
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Right: Live SSE Progress */}
      <div className="flex flex-col rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-base font-semibold text-slate-900">Live Progress (SSE)</h3>
        <p className="mb-4 text-xs text-slate-500">
          Pemantauan *real-time* per tahap &amp; micro-batch dari FastAPI.
        </p>

        <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-700">
          <span>Progres</span>
          <span>{percent}%</span>
        </div>
        <div className="mb-4 h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>

        <div className="flex-1 space-y-2 overflow-y-auto rounded-lg bg-slate-50 p-3 text-xs">
          {events.length === 0 ? (
            <p className="text-slate-400">Belum ada proses berjalan.</p>
          ) : (
            events.map((ev, idx) => (
              <div key={idx} className="flex items-start gap-2">
                {ev.event === "done" ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                ) : ev.event === "error" ? (
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                ) : (
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                )}
                <span className="text-slate-700">{ev.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
