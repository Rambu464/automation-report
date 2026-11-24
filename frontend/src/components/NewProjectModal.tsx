"use client";

import React, { useState } from "react";
import { X, FolderPlus, AlertCircle } from "lucide-react";
import { ProjectItem, createProject } from "@/lib/api";

interface NewProjectModalProps {
  open: boolean;
  clients: string[];
  defaultClient: string;
  onClose: () => void;
  onCreated: (project: ProjectItem) => void;
}

export default function NewProjectModal({
  open,
  clients,
  defaultClient,
  onClose,
  onCreated,
}: NewProjectModalProps) {
  const [name, setName] = useState<string>("");
  const [clientId, setClientId] = useState<string>(defaultClient || "bni");
  const [reportType, setReportType] = useState<"daily" | "weekly" | "monthly" | "crisis">("daily");
  const [cutoffDatetime, setCutoffDatetime] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  React.useEffect(() => {
    if (open) {
      setClientId(defaultClient || clients[0] || "bni");
      setError("");
    }
  }, [open, defaultClient, clients]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Nama Project / Kasus wajib diisi.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const normalizedCutoff = cutoffDatetime ? cutoffDatetime.replace("T", " ") : "";
      const project = await createProject({
        name: name.trim(),
        client_id: clientId,
        report_type: reportType,
        cutoff_datetime: normalizedCutoff,
      });
      setName("");
      setCutoffDatetime("");
      onCreated(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-100 text-orange-600">
              <FolderPlus className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-zinc-900">Buat Project / Kasus Baru</h2>
              <p className="text-xs text-zinc-500">1 kasus disimpan sebagai 1 project persisten.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-semibold text-zinc-700">
              Nama Kasus / Project
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Contoh: BNI Jember 16–19 Nov 2026"
              autoFocus
              className="w-full rounded-xl border border-zinc-300 px-3.5 py-2 text-sm focus:border-orange-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-700">
                Profil Klien
              </label>
              <select
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
              >
                {clients.map((c) => (
                  <option key={c} value={c}>
                    {c.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-zinc-700">
                Tipe Laporan
              </label>
              <select
                value={reportType}
                onChange={(e) =>
                  setReportType(e.target.value as "daily" | "weekly" | "monthly" | "crisis")
                }
                className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
              >
                <option value="daily">Daily Report</option>
                <option value="weekly">Weekly Report</option>
                <option value="monthly">Monthly Report</option>
                <option value="crisis">Crisis / Ad-Hoc</option>
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-zinc-700">
              Batas Tanggal &amp; Jam Cutoff (WIB, Opsional)
            </label>
            <input
              type="datetime-local"
              value={cutoffDatetime}
              onChange={(e) => setCutoffDatetime(e.target.value)}
              className="w-full rounded-xl border border-zinc-300 px-3.5 py-2 text-sm focus:border-orange-500 focus:outline-none"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-xl bg-orange-500 px-5 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-orange-600 disabled:opacity-50"
            >
              {submitting ? "Membuat..." : "Buat Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
