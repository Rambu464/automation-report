"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  Play,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Filter,
  Sparkles,
  Table2,
  Download,
  ArrowRight,
} from "lucide-react";
import { JobEventPayload, ProjectItem, subscribeJobStream, uploadJob } from "@/lib/api";

interface UploadPanelProps {
  project: ProjectItem;
  onJobCompleted: (jobId: string) => void;
}

export default function UploadPanel({ project, onJobCompleted }: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [cutoffDatetime, setCutoffDatetime] = useState<string>(
    project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : ""
  );
  const [reqUploadUrls, setReqUploadUrls] = useState<string>("");
  const [takedownUrls, setTakedownUrls] = useState<string>("");
  const [skipAi, setSkipAi] = useState<boolean>(false);

  const [running, setRunning] = useState<boolean>(false);
  const [percent, setPercent] = useState<number>(project.status === "completed" ? 100 : 0);
  const [events, setEvents] = useState<JobEventPayload[]>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    setCutoffDatetime(project.cutoff_datetime ? project.cutoff_datetime.replace(" ", "T") : "");
    setPercent(project.status === "completed" ? 100 : 0);
    setFiles([]);
    setEvents([]);
    setError("");
  }, [project.project_id, project.cutoff_datetime, project.status]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles(Array.from(e.target.files));
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) setFiles(Array.from(e.dataTransfer.files));
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
        clientId: project.client_id,
        projectId: project.project_id,
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

  const steps = [
    {
      num: "1",
      title: "Raw Excel",
      desc: ".xls with Statements",
      icon: <FileSpreadsheet className="h-4 w-4 text-orange-600" />,
      ring: "border-orange-200 bg-orange-50/70",
      active: files.length > 0 || percent > 0,
    },
    {
      num: "2",
      title: "Pre-Clean & Cutoff",
      desc: "Dedup 3-Lapis & Tier",
      icon: <Filter className="h-4 w-4 text-sky-600" />,
      ring: "border-sky-200 bg-sky-50/70",
      active: percent >= 15,
    },
    {
      num: "3",
      title: "3-Pass AI Engine",
      desc: "Sentimen & Newstrend",
      icon: <Sparkles className="h-4 w-4 text-purple-600" />,
      ring: "border-purple-200 bg-purple-50/70",
      active: percent >= 35,
    },
    {
      num: "4",
      title: "Tabel QC 4-Tab",
      desc: "Review & Sync SQLite",
      icon: <Table2 className="h-4 w-4 text-emerald-600" />,
      ring: "border-emerald-200 bg-emerald-50/70",
      active: percent === 100,
    },
    {
      num: "5",
      title: "3 Output Klien",
      desc: ".xlsx, .pptx, Wording",
      icon: <Download className="h-4 w-4 text-zinc-700" />,
      ring: "border-zinc-200 bg-zinc-100/80",
      active: percent === 100,
    },
  ];

  return (
    <div className="space-y-5">
      {/* Visual Workflow Pipeline Strip (AutomiQ-inspired) */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-zinc-200 bg-white/90 p-4 shadow-xs">
        {steps.map((st, idx) => (
          <React.Fragment key={st.num}>
            <div
              className={`flex min-w-[155px] flex-1 items-center gap-3 rounded-xl border p-3 transition ${
                st.active ? st.ring : "border-zinc-200 bg-white opacity-75"
              }`}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white shadow-2xs">
                {st.icon}
              </div>
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-zinc-900">
                  {st.title}
                </div>
                <div className="truncate text-[11px] text-zinc-500">{st.desc}</div>
              </div>
            </div>
            {idx < steps.length - 1 && (
              <ArrowRight className="hidden h-4 w-4 shrink-0 text-zinc-300 xl:block" />
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Left: Upload & Parameters */}
        <div className="space-y-5 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-base font-semibold text-zinc-900">
                Unggah Raw Data — {project.name}
              </h2>
              <p className="text-xs text-zinc-500">
                Klien aktif: <strong className="text-zinc-800">{project.client_id.toUpperCase()}</strong> •
                Tipe: <strong className="uppercase text-zinc-800">{project.report_type}</strong>
              </p>
            </div>
            {project.status === "completed" && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {project.total_clean} Clean / {project.total_takeout} Takeout tersimpan
              </span>
            )}
          </div>

          {/* Drag and Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-zinc-300 bg-zinc-50/70 px-6 py-8 text-center transition hover:border-orange-400 hover:bg-orange-50/40"
          >
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-orange-100 text-orange-600">
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
            <div className="space-y-1.5 rounded-xl border border-orange-200 bg-orange-50/50 p-3">
              {files.map((f) => (
                <div key={f.name} className="flex items-center gap-2 text-xs text-zinc-800">
                  <FileSpreadsheet className="h-4 w-4 text-orange-600" />
                  <span className="font-semibold">{f.name}</span>
                  <span className="text-zinc-500">({(f.size / 1024).toFixed(1)} KB)</span>
                </div>
              ))}
            </div>
          )}

          {/* Cutoff */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-600">
                Batas Tanggal &amp; Jam Cutoff (WIB, Opsional)
              </label>
              <input
                type="datetime-local"
                value={cutoffDatetime}
                onChange={(e) => setCutoffDatetime(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-orange-500 focus:outline-none"
              />
            </div>

            <div className="flex items-end pb-1.5">
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-zinc-700">
                <input
                  type="checkbox"
                  checked={skipAi}
                  onChange={(e) => setSkipAi(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-300 text-orange-600"
                />
                Mode Pre-Clean Only (0 Token AI — tanpa panggilan LLM)
              </label>
            </div>
          </div>

          {/* Optional Client URL Lists */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-600">
                Daftar URL Req Upload (Opsional)
              </label>
              <textarea
                rows={3}
                value={reqUploadUrls}
                onChange={(e) => setReqUploadUrls(e.target.value)}
                placeholder="https://kompas.com/..."
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-orange-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-600">
                Daftar URL Takedown Klien (Auto Sync SQLite)
              </label>
              <textarea
                rows={3}
                value={takedownUrls}
                onChange={(e) => setTakedownUrls(e.target.value)}
                placeholder="https://portal.id/berita-takedown..."
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-orange-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex items-center justify-end border-t border-zinc-100 pt-4">
            <button
              type="button"
              disabled={running}
              onClick={handleStart}
              className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              {running ? "Memproses Pipeline..." : "Jalankan Pipeline Project"}
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Right: Live SSE Progress Card */}
        <div className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
          <h3 className="text-sm font-semibold text-zinc-900">Live Progress (SSE)</h3>
          <p className="mb-4 text-xs text-zinc-500">
            Pemantauan real-time per tahap &amp; micro-batch dari FastAPI.
          </p>

          <div className="mb-2 flex items-center justify-between text-xs font-semibold text-zinc-700">
            <span>Progres</span>
            <span>{percent}%</span>
          </div>
          <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full rounded-full bg-orange-500 transition-all duration-300"
              style={{ width: `${percent}%` }}
            />
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto rounded-xl bg-zinc-50 p-3 text-xs">
            {events.length === 0 ? (
              <p className="text-zinc-400">
                {project.status === "completed"
                  ? "Project ini sudah selesai diproses. Buka tab Tabel QC atau Ekspor 3 Output, atau unggah file baru untuk memproses ulang."
                  : "Unggah file raw data lalu klik Jalankan Pipeline Project."}
              </p>
            ) : (
              events.map((ev, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  {ev.event === "done" ? (
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  ) : ev.event === "error" ? (
                    <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                  ) : (
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-orange-500" />
                  )}
                  <span className="text-zinc-700">{ev.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
