"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  LayoutGrid,
  Plus,
  Settings,
  FolderKanban,
  Search,
  CheckCircle2,
  Trash2,
  UploadCloud,
  Table2,
  Download,
  Sparkles,
  Clock,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  GitBranch,
  SlidersHorizontal,
  X,
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
import NewProjectModal from "@/components/NewProjectModal";

type RailView = "home" | "workspace" | "settings";
type CanvasTab = "canvas" | "pipeline" | "preclean" | "ai" | "qc" | "export";

export default function HomePage() {
  const [railView, setRailView] = useState<RailView>("home");
  const [canvasTab, setCanvasTab] = useState<CanvasTab>("canvas");
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [configDrawerOpen, setConfigDrawerOpen] = useState<boolean>(true);

  const [clients, setClients] = useState<string[]>(["bni", "bri"]);
  const [selectedClient, setSelectedClient] = useState<string>("bni");

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string>("");
  const [projectSearch, setProjectSearch] = useState<string>("");
  const [showNewModal, setShowNewModal] = useState<boolean>(false);

  const [qcData, setQcData] = useState<QCResponse | null>(null);
  const [loadingQc, setLoadingQc] = useState<boolean>(false);

  const activeProject = useMemo(
    () => projects.find((p) => p.project_id === activeProjectId) || null,
    [projects, activeProjectId]
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
      // Fallback when backend is starting
    }
  };

  const reloadProjects = async (selectProjectId?: string) => {
    try {
      const list = await fetchProjects();
      setProjects(list);
      if (selectProjectId) {
        setActiveProjectId(selectProjectId);
      }
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
    if (activeProject?.latest_job_id) {
      loadActiveProjectQC(activeProject.latest_job_id);
    } else {
      setQcData(null);
    }
  }, [activeProject?.project_id, activeProject?.latest_job_id]);

  const openProject = (prj: ProjectItem) => {
    setActiveProjectId(prj.project_id);
    setSelectedClient(prj.client_id);
    setRailView("workspace");
    setCanvasTab("canvas");
  };

  const handleSelectWorkflowNode = (nodeId: WorkflowNodeId) => {
    if (nodeId === "upload") setCanvasTab("pipeline");
    else if (nodeId === "preclean") setCanvasTab("preclean");
    else if (nodeId === "ai") setCanvasTab("ai");
    else if (nodeId === "qc") setCanvasTab("qc");
    else setCanvasTab("export");
  };

  const goHome = () => {
    setRailView("home");
    setActiveProjectId("");
    setQcData(null);
  };

  const handleProjectCreated = (prj: ProjectItem) => {
    setProjects((prev) => [prj, ...prev]);
    setActiveProjectId(prj.project_id);
    setSelectedClient(prj.client_id);
    setQcData(null);
    setRailView("workspace");
    setCanvasTab("canvas");
    setShowNewModal(false);
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    await deleteProject(projectId);
    setProjects((prev) => {
      const next = prev.filter((p) => p.project_id !== projectId);
      if (activeProjectId === projectId) {
        setActiveProjectId("");
        setQcData(null);
        setRailView("home");
      }
      return next;
    });
  };

  const handleJobCompleted = async (newJobId: string) => {
    await reloadProjects(activeProjectId);
    await loadActiveProjectQC(newJobId);
    setCanvasTab("canvas");
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900">
      {/* Top Global Header */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4">
        <button
          type="button"
          onClick={goHome}
          className="flex items-center gap-3 text-left transition hover:opacity-85"
          title="Kembali ke Home Projects"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500 text-white shadow-xs">
            <Sparkles className="h-4 w-4" />
          </div>
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
            className="w-full rounded-xl border border-zinc-200 bg-zinc-50 py-1.5 pl-9 pr-3 text-xs text-zinc-800 placeholder:text-zinc-400 focus:border-orange-400 focus:bg-white focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowNewModal(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-zinc-800"
          >
            <Plus className="h-3.5 w-3.5" />
            New Project
          </button>
        </div>
      </header>

      {/* Secondary Breadcrumb Bar (Clean — No Duplicate Tab Buttons!) */}
      <div className="flex h-12 flex-wrap items-center justify-between gap-2 border-b border-zinc-200 bg-white px-4">
        <div className="flex items-center gap-2 text-xs">
          {railView !== "settings" && (
            <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              title={sidebarOpen ? "Sembunyikan Sidebar Project" : "Tampilkan Sidebar Project"}
              className="hidden rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 lg:inline-flex"
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>
          )}

          <button
            type="button"
            onClick={goHome}
            className="inline-flex items-center gap-1.5 font-medium text-zinc-500 transition hover:text-orange-600"
          >
            <FolderKanban className="h-4 w-4" />
            <span>Projects</span>
          </button>

          {railView === "settings" && (
            <>
              <span className="text-zinc-300">/</span>
              <span className="font-semibold text-zinc-800">
                Pengaturan Klien, Master Media &amp; Template PPTX
              </span>
            </>
          )}

          {railView === "workspace" && activeProject && (
            <>
              <span className="text-zinc-300">/</span>
              <div className="flex items-center gap-2">
                <select
                  value={activeProject.project_id}
                  onChange={(e) => {
                    const next = projects.find((p) => p.project_id === e.target.value);
                    if (next) openProject(next);
                  }}
                  className="rounded-lg border border-transparent bg-transparent py-1 pr-2 text-xs font-semibold text-zinc-900 hover:border-zinc-200 focus:outline-none"
                >
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <span className="rounded-md bg-orange-50 px-2 py-0.5 text-[10px] font-bold uppercase text-orange-700">
                  {activeProject.client_id}
                </span>
                <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-zinc-600">
                  {activeProject.report_type}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Right side: Status badge + Refresh only (no duplicate navigation buttons) */}
        {railView === "workspace" && activeProject && (
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
                  ? "border-orange-300 bg-orange-50 text-orange-700"
                  : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Config
            </button>
          </div>
        )}
      </div>

      {/* Main Split Body: Slim Icon Rail + Collapsible Project Sidebar + Full-Width Canvas */}
      <div className="flex flex-1 overflow-hidden">
        {/* Far-Left Slim Icon Rail (All icons grouped at top so Next.js dev badge never overlaps!) */}
        <aside className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-zinc-200 bg-white py-3">
          <button
            type="button"
            title="Home — Semua Project"
            onClick={goHome}
            className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${
              railView === "home" || railView === "workspace"
                ? "bg-orange-50 text-orange-600"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>

          <button
            type="button"
            title="Buat Project Baru"
            onClick={() => setShowNewModal(true)}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-900 text-white shadow-xs transition hover:bg-zinc-800"
          >
            <Plus className="h-4 w-4" />
          </button>

          <button
            type="button"
            title="Config Global Klien, Master Media & Template PPTX"
            onClick={() => setRailView("settings")}
            className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${
              railView === "settings"
                ? "bg-orange-50 text-orange-600"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            <Settings className="h-4 w-4" />
          </button>
        </aside>

        {/* Collapsible Left Project List Sidebar */}
        {railView !== "settings" && sidebarOpen && (
          <aside className="hidden w-68 shrink-0 flex-col border-r border-zinc-200 bg-white lg:flex">
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
              <span className="text-xs font-bold text-zinc-800">Daftar Project</span>
              <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold text-zinc-600">
                {projects.length}
              </span>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto p-3">
              {filteredProjects.length === 0 ? (
                <div className="rounded-xl border border-dashed border-zinc-200 p-4 text-center text-xs text-zinc-400">
                  Belum ada project. Klik <strong>Add New Project +</strong> di bawah untuk mulai.
                </div>
              ) : (
                filteredProjects.map((p) => {
                  const isActive = railView === "workspace" && p.project_id === activeProjectId;
                  return (
                    <div
                      key={p.project_id}
                      onClick={() => openProject(p)}
                      className={`group cursor-pointer rounded-xl border p-3 transition ${
                        isActive
                          ? "border-orange-300 bg-orange-50/60 shadow-2xs"
                          : "border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-xs font-semibold text-zinc-900">
                            {p.name}
                          </div>
                          <div className="mt-1 flex items-center gap-1.5 text-[10px] text-zinc-500">
                            <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-bold uppercase text-zinc-700">
                              {p.client_id}
                            </span>
                            <span className="uppercase">{p.report_type}</span>
                          </div>
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

                      <div className="mt-2.5 flex items-center justify-between text-[11px]">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            p.status === "completed"
                              ? "bg-emerald-50 text-emerald-700"
                              : p.status === "failed"
                              ? "bg-red-50 text-red-700"
                              : "bg-zinc-100 text-zinc-600"
                          }`}
                        >
                          {p.status === "completed" ? "Selesai" : p.status}
                        </span>
                        {p.total_raw > 0 && (
                          <span className="text-zinc-500">
                            <strong className="text-zinc-800">{p.total_clean}</strong> clean
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="border-t border-zinc-100 p-3">
              <button
                type="button"
                onClick={() => setShowNewModal(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-800 transition hover:border-zinc-400 hover:bg-zinc-50"
              >
                Add New Project
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </aside>
        )}

        {/* Main Full-Width Canvas */}
        <main className="bg-dot-grid flex-1 overflow-y-auto p-5">
          {railView === "settings" ? (
            <div className="mx-auto max-w-6xl">
              <SettingsPanel
                clients={clients}
                clientId={selectedClient}
                onSelectClient={setSelectedClient}
                onClientCreated={async (newId) => {
                  await reloadClients(newId);
                }}
              />
            </div>
          ) : railView === "home" || !activeProject ? (
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
                  className="inline-flex items-center gap-2 rounded-xl bg-orange-500 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-orange-600"
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
                      onClick={() => openProject(p)}
                      className="group flex cursor-pointer flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xs transition hover:border-orange-300 hover:shadow-md"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="rounded-lg bg-orange-50 px-2 py-0.5 text-[10px] font-bold uppercase text-orange-700">
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

                        <h3 className="mt-3 text-sm font-bold text-zinc-900 group-hover:text-orange-600">
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
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-zinc-500 group-hover:text-orange-600">
                          Buka <ArrowRight className="h-3 w-3" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Active Project Workspace */
            <div className="mx-auto max-w-7xl space-y-4">
              {/* Single-source Document Canvas Tabs */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCanvasTab("canvas")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
                      canvasTab === "canvas"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <GitBranch className="h-3.5 w-3.5 text-orange-500" />
                    Workflow Canvas
                  </button>

                  <button
                    type="button"
                    onClick={() => setCanvasTab("pipeline")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
                      canvasTab === "pipeline"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <UploadCloud className="h-3.5 w-3.5 text-orange-500" />
                    Upload &amp; Proses
                  </button>

                  <button
                    type="button"
                    disabled={!qcData}
                    onClick={() => setCanvasTab("qc")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      canvasTab === "qc"
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
                    onClick={() => setCanvasTab("export")}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      canvasTab === "export"
                        ? "border-zinc-300 bg-white text-zinc-900 shadow-2xs"
                        : "border-transparent bg-zinc-200/50 text-zinc-600 hover:bg-white/70"
                    }`}
                  >
                    <Download className="h-3.5 w-3.5 text-sky-600" />
                    Ekspor 3 Output
                  </button>
                </div>

                {canvasTab !== "canvas" && (
                  <button
                    type="button"
                    onClick={() => setCanvasTab("canvas")}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Kembali ke Kanvas
                  </button>
                )}
              </div>

              {canvasTab === "canvas" && (
                <WorkflowCanvas
                  project={activeProject}
                  qcData={qcData}
                  onSelectNode={handleSelectWorkflowNode}
                />
              )}

              {canvasTab === "pipeline" && (
                <UploadPanel project={activeProject} onJobCompleted={handleJobCompleted} />
              )}

              {canvasTab === "preclean" && (
                <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-zinc-900">
                        Detail Tahap 2: Pre-Cleaning &amp; Media Tier Lookup
                      </h2>
                      <p className="text-xs text-zinc-500">
                        Ringkasan hasil deterministik (0 Token AI) — Deduplikasi 3-Lapis, Cutoff, &amp; SQLite Master Media.
                      </p>
                    </div>
                    {qcData && (
                      <button
                        type="button"
                        onClick={() => setCanvasTab("qc")}
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

              {canvasTab === "ai" && (
                <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-zinc-900">
                        Detail Tahap 3: 3-Pass Cloud AI Engine
                      </h2>
                      <p className="text-xs text-zinc-500">
                        Klasifikasi Sentimen, Standardisasi Newstrends, Spokesperson Tier-2, &amp; Kolom Ad-Hoc.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setRailView("settings")}
                      className="rounded-xl border border-zinc-200 px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                    >
                      Atur Kolom Ad-Hoc →
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

              {canvasTab === "qc" && qcData && (
                <QCTablePanel
                  qcData={qcData}
                  onRefresh={async () => {
                    await loadActiveProjectQC(qcData.job_id);
                    await reloadProjects(activeProject.project_id);
                  }}
                />
              )}

              {canvasTab === "export" && qcData && <ExportPanel qcData={qcData} />}
            </div>
          )}
        </main>

        {/* Right Config Side Panel (ONLY appears inside an active Project when toggled open) */}
        {railView === "workspace" && activeProject && configDrawerOpen && (
          <aside className="hidden w-96 shrink-0 flex-col border-l border-zinc-200 bg-white xl:flex">
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-orange-500" />
                <span className="text-xs font-bold text-zinc-900">
                  Config Klien ({activeProject.client_id.toUpperCase()})
                </span>
              </div>
              <button
                type="button"
                onClick={() => setConfigDrawerOpen(false)}
                title="Tutup Panel Config"
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <SettingsPanel
                compact
                clients={clients}
                clientId={activeProject.client_id}
                onSelectClient={setSelectedClient}
                onClientCreated={async (newId) => {
                  await reloadClients(newId);
                }}
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
