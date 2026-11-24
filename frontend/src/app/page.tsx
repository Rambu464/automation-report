"use client";

import React, { useEffect, useState } from "react";
import { UploadCloud, Table2, Download, Settings } from "lucide-react";
import { QCResponse, fetchClients, fetchQCData } from "@/lib/api";
import UploadPanel from "@/components/UploadPanel";
import QCTablePanel from "@/components/QCTablePanel";
import ExportPanel from "@/components/ExportPanel";
import SettingsPanel from "@/components/SettingsPanel";

type ActiveTab = "upload" | "qc" | "export" | "settings";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("upload");
  const [clients, setClients] = useState<string[]>(["bni", "bri"]);
  const [selectedClient, setSelectedClient] = useState<string>("bri");
  const [jobId, setJobId] = useState<string>("");
  const [qcData, setQcData] = useState<QCResponse | null>(null);

  const reloadClients = async (selectId?: string) => {
    try {
      const list = await fetchClients();
      if (list.length > 0) {
        setClients(list);
        if (selectId) {
          setSelectedClient(selectId);
        } else if (!list.includes(selectedClient)) {
          setSelectedClient(list[0]);
        }
      }
    } catch {
      // Keep default fallback when backend is starting
    }
  };

  useEffect(() => {
    reloadClients();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshQC = async (targetJobId?: string) => {
    const id = targetJobId || jobId;
    if (!id) return;
    const data = await fetchQCData(id);
    setQcData(data);
  };

  const handleJobCompleted = async (newJobId: string) => {
    setJobId(newJobId);
    await refreshQC(newJobId);
    setActiveTab("qc");
  };

  const navItems: Array<{ id: ActiveTab; label: string; icon: React.ReactNode; disabled?: boolean }> = [
    { id: "upload", label: "1. Upload & Proses", icon: <UploadCloud className="h-4 w-4" /> },
    { id: "qc", label: "2. Tabel QC Interaktif", icon: <Table2 className="h-4 w-4" />, disabled: !qcData },
    { id: "export", label: "3. Ekspor 3 Output", icon: <Download className="h-4 w-4" />, disabled: !qcData },
    { id: "settings", label: "4. Config & Media Master", icon: <Settings className="h-4 w-4" /> },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Newstent <span className="font-normal text-blue-700">Analyst Automation</span>
            </h1>
            <p className="text-xs text-slate-500">
              Binokular Media Monitoring • Pre-Cleaning, 3-Pass Cloud AI, Interactive QC, &amp; Triple Deliverables
            </p>
          </div>

          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                disabled={item.disabled}
                onClick={() => setActiveTab(item.id)}
                className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
                  activeTab === item.id
                    ? "bg-blue-700 text-white shadow-sm"
                    : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {activeTab === "upload" && (
          <UploadPanel
            clients={clients}
            selectedClient={selectedClient}
            onSelectClient={setSelectedClient}
            onJobCompleted={handleJobCompleted}
          />
        )}

        {activeTab === "qc" && qcData && (
          <QCTablePanel qcData={qcData} onRefresh={() => refreshQC()} />
        )}

        {activeTab === "export" && qcData && <ExportPanel qcData={qcData} />}

        {activeTab === "settings" && (
          <SettingsPanel
            clients={clients}
            clientId={selectedClient}
            onSelectClient={setSelectedClient}
            onClientCreated={async (newId) => {
              await reloadClients(newId);
            }}
          />
        )}
      </main>
    </div>
  );
}
