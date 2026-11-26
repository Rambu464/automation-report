"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutGrid,
  Plus,
  Building2,
  FolderKanban,
  Search,
  CheckCircle2,
  Trash2,
  UploadCloud,
  Table2,
  Download,
  Sparkles,
  Clock,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  GitBranch,
  SlidersHorizontal,
  X,
  User,
  Settings,
  Cpu,
} from "lucide-react";
import {
  ProjectItem,
  QCResponse,
  deleteProject,
  fetchClients,
  fetchProjects,
  fetchQCData,
} from "@/lib/api";
import WorkflowCanvas, { WorkflowNodeId } from "@/components/WorkflowCanvas";
import UploadPanel from "@/components/UploadPanel";
import QCTablePanel from "@/components/QCTablePanel";
import ExportPanel from "@/components/ExportPanel";
import SettingsPanel from "@/components/SettingsPanel";
import ClientsGrid from "@/components/ClientsGrid";
import ModelConfigPanel from "@/components/ModelConfigPanel";
import SystemSettingsPanel from "@/components/SystemSettingsPanel";
import NewProjectModal from "@/components/NewProjectModal";

export type AppShellMode = "home" | "project" | "clients" | "client_detail" | "settings";
export type ProjectStep = "canvas" | "upload" | "preclean" | "ai" | "qc" | "export";

interface AppShellProps {
  mode: AppShellMode;
  projectId?: string;
  step?: ProjectStep;
  clientId?: string;
}

export default function AppShell({
  mode,
  projectId = "",
  step = "canvas",
  clientId = "",
}: AppShellProps) {
  const router = useRouter();
  const [configDrawerOpen, setConfigDrawerOpen] = useState<boolean>(true);

  const [clients, setClients] = useState<string[]>(["bni", "bri"]);
  const [selectedClient, setSelectedClient] = useState<string>("bni");

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectSearch, setProjectSearch] = useState<string>("");
  const [showNewModal, setShowNewModal] = useState<boolean>(false);

  const [qcData, setQcData] = useState<QCResponse | null>(null);
  const [loadingQc, setLoadingQc] = useState<boolean>(false);

  const activeProject = useMemo(
    () => (mode === "project" ? projects.find((p) => p.project_id === projectId) || null : null),
    [mode, projects, projectId]
  );

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.client_id.toLowerCase().includes(q) ||
        p.report_type.toLowerCase().includes(q)
    );
  }, [projects, projectSearch]);

  const reloadClients = async (selectId?: string) => {
    try {
      const list = await fetchClients();
      if (list.length > 0) {
        setClients(list);
        if (selectId) setSelectedClient(selectId);
        else if (!list.includes(selectedClient)) setSelectedClient(list[0]);
      }
    } catch {
      // Backend might be starting
    }
  };

  const reloadProjects = async () => {
    try {
      const list = await fetchProjects();
      setProjects(list);
    } catch {
      // Backend might be offline initially
    }
  };

  useEffect(() => {
    reloadClients();
    reloadProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadActiveProjectQC = async (jobId: string) => {
    if (!jobId) {
      setQcData(null);
      return;
    }
    setLoadingQc(true);
    try {
      const data = await fetchQCData(jobId);
      setQcData(data);
    } catch {
      setQcData(null);
    } finally {
      setLoadingQc(false);
    }
  };

  useEffect(() => {
    if (activeProject?.client_id) {
      setSelectedClient(activeProject.client_id);
    }
    if (activeProject?.latest_job_id) {
      loadActiveProjectQC(activeProject.latest_job_id);
    } else {
      setQcData(null);
    }
  }, [activeProject?.project_id, activeProject?.latest_job_id, activeProject?.client_id]);

  // URL Navigation helpers (real Next.js App Router paths!)
  const goHome = () => router.push("/");
  const goClients = () => router.push("/clients");
  const goClientDetail = (cid: string) => router.push(`/clients/${cid}`);
  const goSettings = () => router.push("/settings");
  const goProject = (pid: string, targetStep: ProjectStep = "canvas") => {
    if (targetStep === "canvas") router.push(`/projects/${pid}`);
    else router.push(`/projects/${pid}/${targetStep}`);
  };

  const handleSelectWorkflowNode = (nodeId: WorkflowNodeId) => {
    if (!projectId) return;
    if (nodeId === "upload") goProject(projectId, "upload");
    else if (nodeId === "preclean") goProject(projectId, "preclean");
    else if (nodeId === "ai") goProject(projectId, "ai");
    else if (nodeId === "qc") goProject(projectId, "qc");
    else goProject(projectId, "export");
  };

  const handleProjectCreated = (prj: ProjectItem) => {
    setProjects((prev) => [prj, ...prev]);
    setSelectedClient(prj.client_id);
    setShowNewModal(false);
    goProject(prj.project_id, "canvas");
  };

  const handleDeleteProject = async (e: React.MouseEvent, targetProjectId: string) => {
    e.stopPropagation();
    await deleteProject(targetProjectId);
    setProjects((prev) => prev.filter((p) => p.project_id !== targetProjectId));
    if (projectId === targetProjectId) {
      goHome();
    }
  };

  const handleJobCompleted = async (newJobId: string) => {
    await reloadProjects();
    await loadActiveProjectQC(newJobId);
    if (projectId) goProject(projectId, "canvas");
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900">
      {/* Top Global Header */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4">
        <button
          type="button"
          onClick={goHome}
          className="flex items-center gap-2.5 text-left transition hover:opacity-85"
          title="Kembali ke Home Projects (/)"
        >
          <span className="text-base font-bold tracking-tight text-zinc-900">Newstent</span>
          <span className="hidden rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500 sm:inline">
            Analyst Studio
          </span>
        </button>

        {/* Center Search */}
        <div className="relative mx-4 hidden w-full max-w-md md:block">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
          <input
            type="text"
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
            placeholder="Cari project atau kasus..."
            className="w-full rounded-xl border border-zinc-200 bg-zinc-50 py-1.5 pl-9 pr-3 text-xs text-zinc-800 placeholder:text-zinc-400 focus:border-blue-400 focus:bg-white focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2.5">
          <div className="hidden text-right sm:block">
            <div className="text-xs font-semibold leading-tight text-zinc-800">Analis</div>
            <div className="text-[10px] text-zinc-400">Binokular Local</div>
          </div>
          <div
            title="Akun Analis Lokal"
            className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-200 bg-zinc-100 text-zinc-600"
          >
            <User className="h-4 w-4" />
          </div>
        </div>
      </header>

      {/* Secondary Breadcrumb Bar */}
      <div className="flex h-12 flex-wrap items-center justify-between gap-2 border-b border-zinc-200 bg-white px-4">
        <div className="flex items-center gap-2 text-xs">
          {mode === "settings" ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-zinc-800">
              <Settings className="h-4 w-4 text-blue-600" />
              <span>Pengaturan Sistem &amp; API Keys</span>
            </span>
          ) : mode === "clients" || mode === "client_detail" ? (
            <>
              <button
                type="button"
                onClick={goClients}
                className="inline-flex items-center gap-1.5 font-medium text-zinc-500 transition hover:text-blue-700"
              >
                <Building2 className="h-4 w-4" />
                <span>Konfigurasi Klien</span>
              </button>
              {mode === "client_detail" && clientId && (
                <>
                  <span className="text-zinc-300">/</span>
                  <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-bold uppercase text-blue-700">
                    {clientId}
                  </span>
                </>
              )}
            </>
          ) : (
            <button
              type="button"
              onClick={goHome}
              className="inline-flex items-center gap-1.5 font-medium text-zinc-500 transition hover:text-blue-700"
            >
              <FolderKanban className="h-4 w-4" />
              <span>Projects</span>
            </button>
          )}

          {mode === "project" && activeProject && (
            <>
              <span className="text-zinc-300">/</span>
              <div className="flex items-center gap-2">
                <select
                  value={activeProject.project_id}
                  onChange={(e) => goProject(e.target.value, "canvas")}
                  className="rounded-lg border border-transparent bg-transparent py-1 pr-2 text-xs font-semibold text-zinc-900 hover:border-zinc-200 focus:outline-none"
                >
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">
                  {activeProject.client_id}
                </span>
                <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-zinc-600">
                  {activeProject.report_type}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Right side: Status badge + Refresh + Config Drawer Toggle */}
        {mode === "project" && activeProject && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-[11px] font-medium text-zinc-600">
              {activeProject.status === "completed" ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  Saved
                </>
              ) : (
                <>
                  <Clock className="h-3.5 w-3.5 text-zinc-400" />
                  {activeProject.status}
                </>
              )}
            </span>

            {activeProject.latest_job_id && (
              <button
                type="button"
                onClick={() => loadActiveProjectQC(activeProject.latest_job_id)}
                title="Muat ulang data project"
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-[11px] font-medium text-zinc-600 transition hover:bg-zinc-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingQc ? "animate-spin" : ""}`} />
                Refresh
              </button>
            )}

            <button
              type="button"
              onClick={() => setConfigDrawerOpen((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition ${
                configDrawerOpen
                  ? "border-blue-300 bg-blue-50 text-blue-700"
                  : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              <Cpu className="h-3.5 w-3.5" />
              Model AI
            </button>
          </div>
        )}
      </div>

      {/* Main Split Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Far-Left Slim Icon Rail (All icons grouped at top) */}
        <aside className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-zinc-200 bg-white py-3">
          <button
            type="button"
            title="Home — Semua Project (/)"
            onClick={goHome}
            className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${
              mode === "home" || mode === "project"
                ? "bg-blue-50 text-blue-700"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>

          <button
            type="button"
            title="Konfigurasi Klien (/clients)"
            onClick={goClients}
            className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${
              mode === "clients" || mode === "client_detail"
                ? "bg-blue-50 text-blue-700"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            <Building2 className="h-4 w-4" />
          </button>

          <button
            type="button"
            title="Pengaturan Sistem & API Keys (/settings)"
            onClick={goSettings}
            className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${
              mode === "settings"
                ? "bg-blue-50 text-blue-700"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            <Settings className="h-4 w-4" />
          </button>
        </aside>

        {/* Main Full-Width Canvas */}
        <main className="bg-dot-grid flex-1 overflow-y-auto p-5">
          {mode === "settings" ? (
            <SystemSettingsPanel />
          ) : mode === "clients" ? (
            <ClientsGrid
              clients={clients}
              onOpenClient={goClientDetail}
              onClientCreated={async (newId) => {
                await reloadClients(newId);
              }}
            />
          ) : mode === "client_detail" ? (
            <div className="mx-auto max-w-6xl space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={goClients}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Kembali ke Daftar Klien
                </button>
              </div>
              <SettingsPanel clientId={clientId || selectedClient} />
            </div>
          ) : mode === "home" ? (
            /* Home Dashboard: All Projects Grid */
            <div className="mx-auto max-w-6xl space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
                <div>
                  <h1 className="text-xl font-bold text-zinc-900">Projects Dashboard</h1>
                  <p className="mt-1 text-xs text-zinc-500">
                    Pilih kasus yang sudah tersimpan untuk melanjutkan QC / Ekspor, atau buat Project baru.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowNewModal(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700"
                >
                  <Plus className="h-4 w-4" />
                  Buat Project Baru
                </button>
              </div>

              {filteredProjects.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-zinc-300 bg-white/80 p-12 text-center">
                  <FolderKanban className="mx-auto mb-3 h-10 w-10 text-zinc-300" />
                  <h2 className="text-sm font-semibold text-zinc-700">Belum ada Project</h2>
                  <p className="mt-1 text-xs text-zinc-400">
                    Klik <strong>Buat Project Baru</strong> untuk mulai mengolah kasus media monitoring.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredProjects.map((p) => (
                    <div
                      key={p.project_id}
                      onClick={() => goProject(p.project_id, "canvas")}
                      className="group flex cursor-pointer flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xs transition hover:border-blue-300 hover:shadow-md"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="rounded-lg bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">
                              {p.client_id}
                            </span>
                            <span className="rounded-lg bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-zinc-600">
                              {p.report_type}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteProject(e, p.project_id)}
                            title="Hapus Project"
                            className="rounded p-1 text-zinc-300 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        <h3 className="mt-3 text-sm font-bold text-zinc-900 group-hover:text-blue-700">
                          {p.name}
                        </h3>
                        {p.cutoff_datetime && (
                          <p className="mt-1 text-[11px] text-zinc-500">
                            Cutoff: {p.cutoff_datetime} WIB
                          </p>
                        )}
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3 text-xs">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            p.status === "completed"
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-zinc-100 text-zinc-600"
                          }`}
                        >
                          {p.status === "completed"
                            ? `${p.total_clean} Clean / ${p.total_takeout} Takeout`
                            : "Draft (Belum diproses)"}
                        </span>
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-zinc-500 group-hover:text-blue-700">
                          Buka <ArrowRight className="h-3 w-3" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : !activeProject ? (
            <div className="mx-auto mt-16 max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-xs">
              <p className="text-sm font-semibold text-zinc-700">Memuat project...</p>
              <button
                type="button"
                onClick={goHome}
                className="mt-4 rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                Kembali ke Projects
              </button>
            </div>
          ) : (
            /* Active Project Workspace (URL: /projects/[projectId] or /projects/[projectId]/[step]) */
            <div className="mx-auto max-w-7xl space-y-4">
              {/* Single-source Document Canvas Tabs backed by Real Routes */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => goProject(activeProject.project_id, "canvas")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
                      step === "canvas"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <GitBranch className="h-3.5 w-3.5 text-blue-600" />
                    Workflow Canvas
                  </button>

                  <button
                    type="button"
                    onClick={() => goProject(activeProject.project_id, "upload")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
                      step === "upload"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <UploadCloud className="h-3.5 w-3.5 text-blue-600" />
                    Upload &amp; Proses
                  </button>

                  <button
                    type="button"
                    disabled={!qcData}
                    onClick={() => goProject(activeProject.project_id, "qc")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      step === "qc"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <Table2 className="h-3.5 w-3.5 text-emerald-600" />
                    Tabel QC Interaktif
                    {qcData && (
                      <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-700">
                        {qcData.tab_counts.all}
                      </span>
                    )}
                  </button>

                  <button
                    type="button"
                    disabled={!qcData}
                    onClick={() => goProject(activeProject.project_id, "export")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      step === "export"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <Download className="h-3.5 w-3.5 text-sky-600" />
                    Ekspor 3 Output
                  </button>
                </div>

                {step !== "canvas" && (
                  <button
                    type="button"
                    onClick={() => goProject(activeProject.project_id, "canvas")}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Kembali ke Kanvas
                  </button>
                )}
              </div>

              {step === "canvas" && (
                <WorkflowCanvas
                  project={activeProject}
                  qcData={qcData}
                  onSelectNode={handleSelectWorkflowNode}
                />
              )}

              {step === "upload" && (
                <UploadPanel project={activeProject} onJobCompleted={handleJobCompleted} />
              )}

              {step === "preclean" && (
                <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-zinc-900">
                        Detail Pre-Cleaning &amp; Media Tier Lookup
                      </h2>
                      <p className="text-xs text-zinc-500">
                        Ringkasan hasil deterministik (0 Token AI) — Deduplikasi 3-Lapis, Cutoff, &amp; Custom Media Tier.
                      </p>
                    </div>
                    {qcData && (
                      <button
                        type="button"
                        onClick={() => goProject(activeProject.project_id, "qc")}
                        className="rounded-xl bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-zinc-800"
                      >
                        Buka di Tabel QC →
                      </button>
                    )}
                  </div>
                  {qcData ? (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                        <div className="text-xs font-semibold text-zinc-500">Volume &amp; Takeout</div>
                        <div className="mt-2 space-y-1 text-xs">
                          <div>Raw Data: <strong>{qcData.report_payload.meta.total_raw}</strong></div>
                          <div className="text-emerald-700">Keep (Clean): <strong>{qcData.report_payload.meta.total_clean}</strong></div>
                          <div className="text-rose-600">Takeout: <strong>{qcData.report_payload.meta.total_takeout}</strong></div>
                          <div>Flag 00:00: <strong>{qcData.tab_counts.cutoff_00}</strong></div>
                          <div>Mirip Judul: <strong>{qcData.tab_counts.near_dup}</strong></div>
                        </div>
                      </div>
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                        <div className="text-xs font-semibold text-zinc-500">Distribusi Custom Tier</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {Object.entries(qcData.report_payload.media_breakdown.by_custom_tier).map(([k, v]) => (
                            <div key={k} className="flex justify-between">
                              <span>{k}</span>
                              <strong>{v}</strong>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                        <div className="text-xs font-semibold text-zinc-500">Distribusi Tipe Media</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {Object.entries(qcData.report_payload.media_breakdown.by_type).map(([k, v]) => (
                            <div key={k} className="flex justify-between capitalize">
                              <span>{k}</span>
                              <strong>{v}</strong>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-400">Belum ada data diproses. Klik Upload &amp; Proses terlebih dahulu.</p>
                  )}
                </div>
              )}

              {step === "ai" && (
                <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-zinc-900">
                        Detail 3-Pass Cloud AI Engine
                      </h2>
                      <p className="text-xs text-zinc-500">
                        Klasifikasi Sentimen, Standardisasi Newstrends, Spokesperson Tier-2, &amp; Kolom Ad-Hoc.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setConfigDrawerOpen(true)}
                      className="rounded-xl border border-zinc-200 px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                    >
                      Buka Panel Config →
                    </button>
                  </div>
                  {qcData ? (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                        <div className="text-xs font-semibold text-zinc-500">Komposisi Sentimen</div>
                        <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                          <div className="rounded-lg bg-emerald-50 p-2 text-emerald-800">
                            <div className="text-[10px]">Positif</div>
                            <div className="text-base font-bold">{qcData.report_payload.sentiment_summary.positive}</div>
                          </div>
                          <div className="rounded-lg bg-zinc-200/70 p-2 text-zinc-800">
                            <div className="text-[10px]">Netral</div>
                            <div className="text-base font-bold">{qcData.report_payload.sentiment_summary.neutral}</div>
                          </div>
                          <div className="rounded-lg bg-rose-50 p-2 text-rose-800">
                            <div className="text-[10px]">Negatif</div>
                            <div className="text-base font-bold">{qcData.report_payload.sentiment_summary.negative}</div>
                          </div>
                        </div>
                      </div>
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                        <div className="text-xs font-semibold text-zinc-500">Kolom Ad-Hoc Aktif</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {qcData.adhoc_columns.map((c) => (
                            <span key={c} className="rounded-lg bg-purple-100 px-2.5 py-1 text-xs font-semibold text-purple-800">
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-400">Belum ada data diproses. Klik Upload &amp; Proses terlebih dahulu.</p>
                  )}
                </div>
              )}

              {step === "qc" && qcData && (
                <QCTablePanel
                  qcData={qcData}
                  onRefresh={async () => {
                    await loadActiveProjectQC(qcData.job_id);
                    await reloadProjects();
                  }}
                />
              )}

              {step === "export" && qcData && <ExportPanel qcData={qcData} />}
            </div>
          )}
        </main>

        {/* Right Model AI Config Side Panel (ONLY inside active Project) */}
        {mode === "project" && activeProject && configDrawerOpen && (
          <aside className="hidden w-92 shrink-0 flex-col border-l border-zinc-200 bg-white xl:flex">
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-blue-600" />
                <span className="text-xs font-bold text-zinc-900">
                  Konfigurasi Model AI
                </span>
              </div>
              <button
                type="button"
                onClick={() => setConfigDrawerOpen(false)}
                title="Tutup Panel Model AI"
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <ModelConfigPanel
                clientId={activeProject.client_id}
                onGoSystemSettings={goSettings}
                onGoClientConfig={goClientDetail}
              />
            </div>
          </aside>
        )}
      </div>

      {/* Create New Project Modal */}
      <NewProjectModal
        open={showNewModal}
        clients={clients}
        defaultClient={selectedClient}
        onClose={() => setShowNewModal(false)}
        onCreated={handleProjectCreated}
      />
    </div>
  );
}
