"use client";

import React, { useEffect, useState } from "react";
import {
  Building2,
  Plus,
  ArrowRight,
  Layers,
  Tag,
  X,
  Save,
  AlertCircle,
} from "lucide-react";
import {
  ClientConfigData,
  createClientProfile,
  fetchClientConfig,
} from "@/lib/api";

interface ClientsGridProps {
  clients: string[];
  onOpenClient: (clientId: string) => void;
  onClientCreated: (newClientId: string) => Promise<void>;
}

export default function ClientsGrid({
  clients,
  onOpenClient,
  onClientCreated,
}: ClientsGridProps) {
  const [configs, setConfigs] = useState<Record<string, ClientConfigData>>({});
  const [loading, setLoading] = useState<boolean>(true);

  // Create New Client Modal state
  const [showModal, setShowModal] = useState<boolean>(false);
  const [newClientId, setNewClientId] = useState<string>("");
  const [newClientName, setNewClientName] = useState<string>("");
  const [newFocusType, setNewFocusType] = useState<
    "brand_only" | "brand_and_competitor" | "crisis"
  >("brand_and_competitor");
  const [newTierCol, setNewTierCol] = useState<string>("");
  const [newCompetitors, setNewCompetitors] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all(
      clients.map(async (cid) => {
        try {
          const cfg = await fetchClientConfig(cid);
          return [cid, cfg] as const;
        } catch {
          return null;
        }
      })
    ).then((entries) => {
      if (!active) return;
      const map: Record<string, ClientConfigData> = {};
      for (const item of entries) {
        if (item) map[item[0]] = item[1];
      }
      setConfigs(map);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [clients]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClientId.trim() || !newClientName.trim()) {
      setErr("ID Klien dan Nama Resmi Klien wajib diisi.");
      return;
    }
    setSubmitting(true);
    setErr("");
    try {
      const res = await createClientProfile({
        client_id: newClientId.trim(),
        client_name: newClientName.trim(),
        focus_type: newFocusType,
        custom_tier_enabled: true,
        custom_tier_column: newTierCol.trim(),
        competitors: newCompetitors
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await onClientCreated(res.client_id);
      setNewClientId("");
      setNewClientName("");
      setNewTierCol("");
      setNewCompetitors("");
      setShowModal(false);
      onOpenClient(res.client_id);
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Gagal membuat profil klien.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header Card (mirrors Projects Dashboard) */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Konfigurasi Klien</h1>
          <p className="mt-1 text-xs text-zinc-500">
            Pilih kartu klien untuk mengatur kolom Ad-Hoc, Master Media Tier, dan Template PPTX, atau buat profil klien baru.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setErr("");
            setShowModal(true);
          }}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Buat Klien Baru
        </button>
      </div>

      {/* Per-Client Cards Grid */}
      {loading && Object.keys(configs).length === 0 ? (
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-xs text-zinc-400">
          Memuat daftar konfigurasi klien...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clients.map((cid) => {
            const cfg = configs[cid];
            const mediaSpk = (cfg?.media_and_spokesperson || {}) as {
              custom_tier?: { enabled?: boolean; excel_column_name?: string };
            };
            const tierCol = mediaSpk.custom_tier?.enabled
              ? mediaSpk.custom_tier.excel_column_name || `TIER ${cid.toUpperCase()}`
              : "Tier Standar";
            const adhocCount = cfg?.adhoc_columns?.length ?? 0;

            return (
              <div
                key={cid}
                onClick={() => onOpenClient(cid)}
                className="group flex cursor-pointer flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xs transition hover:border-blue-300 hover:shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <span className="rounded-lg bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-600">
                      {cfg?.focus_type?.replace(/_/g, " ") || "client"}
                    </span>
                  </div>

                  <h3 className="mt-3 text-sm font-bold text-zinc-900 group-hover:text-blue-700">
                    {cfg?.client_name || cid.toUpperCase()}
                  </h3>
                  <p className="mt-0.5 font-mono text-[11px] text-zinc-400">
                    clients/{cid}/config.yaml
                  </p>

                  <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                      <Tag className="h-3 w-3" />
                      {tierCol}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 font-medium text-purple-700">
                      <Layers className="h-3 w-3" />
                      {adhocCount} Kolom Ad-Hoc
                    </span>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3 text-xs">
                  <span className="text-[11px] font-semibold uppercase text-zinc-500">
                    ID: {cid}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-zinc-600 group-hover:text-blue-700">
                    Atur Config <ArrowRight className="h-3 w-3" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create New Client Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-zinc-900">Buat Profil Klien Baru</h2>
                  <p className="text-xs text-zinc-500">Otomatis membuat config.yaml di folder clients/.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-3.5">
              <div>
                <label className="mb-1 block text-xs font-semibold text-zinc-700">
                  ID Klien (huruf kecil tanpa spasi)
                </label>
                <input
                  type="text"
                  value={newClientId}
                  onChange={(e) => setNewClientId(e.target.value)}
                  placeholder="Contoh: mandiri, telkom, bca"
                  autoFocus
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-zinc-700">
                  Nama Resmi Klien
                </label>
                <input
                  type="text"
                  value={newClientName}
                  onChange={(e) => setNewClientName(e.target.value)}
                  placeholder="Contoh: Bank Mandiri (Persero) Tbk"
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-zinc-700">
                    Fokus Monitoring
                  </label>
                  <select
                    value={newFocusType}
                    onChange={(e) =>
                      setNewFocusType(
                        e.target.value as "brand_only" | "brand_and_competitor" | "crisis"
                      )
                    }
                    className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  >
                    <option value="brand_and_competitor">Brand + Kompetitor</option>
                    <option value="brand_only">Brand Only</option>
                    <option value="crisis">Crisis / Issue</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-zinc-700">
                    Kolom Custom Tier
                  </label>
                  <input
                    type="text"
                    value={newTierCol}
                    onChange={(e) => setNewTierCol(e.target.value)}
                    placeholder="Default: TIER <ID>"
                    className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-zinc-700">
                  Daftar Kompetitor (opsional, pisah koma)
                </label>
                <input
                  type="text"
                  value={newCompetitors}
                  onChange={(e) => setNewCompetitors(e.target.value)}
                  placeholder="Contoh: BRI, BNI, BCA, BTN"
                  className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              {err && (
                <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{err}</span>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" />
                  {submitting ? "Menyimpan..." : "Simpan Klien"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
