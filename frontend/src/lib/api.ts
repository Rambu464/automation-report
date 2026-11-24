/** Typed REST & SSE client for the local FastAPI backend (Port 8000). */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface JobEventPayload {
  event: "progress" | "done" | "error";
  stage: string;
  percent: number;
  message: string;
  timestamp: string;
}

export interface QCTabCounts {
  all: number;
  cutoff_00: number;
  takeout: number;
  rilis_spk_zero: number;
  near_dup: number;
}

export interface QCRow {
  ID: string;
  Date?: string;
  Time?: string;
  Title?: string;
  "Media Name"?: string;
  "Media Type"?: string;
  "Media Type Detail"?: string;
  "Media Tier"?: string;
  "Page/URL"?: string;
  Sentiment?: string;
  Newstrends?: string;
  Nama_Isu?: string;
  Content_Type?: string;
  Spokesperson?: string;
  Jabatan?: string;
  Status_Takeout?: string;
  Alasan_Spam?: string;
  Flag_Cutoff_00?: string;
  Flag_Near_Dup?: string;
  Status_Req_Upload?: string;
  [key: string]: unknown;
}

export interface QCResponse {
  job_id: string;
  client_id: string;
  status: string;
  columns: string[];
  adhoc_columns: string[];
  tab_counts: QCTabCounts;
  url_match_summary: {
    req_upload_total?: number;
    req_upload_matched?: number;
    req_upload_unmatched_urls?: string[];
    takedown_matched?: number;
    historical_takeout_matched?: number;
  };
  report_payload: {
    meta: {
      client_id: string;
      client_name: string;
      period_label: string;
      cutoff_wib: string;
      total_raw: number;
      total_clean: number;
      total_takeout: number;
      req_upload_matched: number;
    };
    sentiment_summary: { positive: number; neutral: number; negative: number };
    media_breakdown: {
      by_type: Record<string, number>;
      by_custom_tier: Record<string, number>;
      by_detail: Record<string, number>;
    };
  };
  rows: QCRow[];
}

export interface AdhocColumn {
  name: string;
  description: string;
}

export interface ClientConfigData {
  client_id: string;
  client_name: string;
  focus_type: "brand_only" | "brand_and_competitor" | "crisis";
  adhoc_columns: AdhocColumn[];
  [key: string]: unknown;
}

export interface ExportResponse {
  job_id: string;
  excel_url: string;
  pptx_url: string;
  pdf_url: string | null;
  wording_url: string;
  wording_text: string;
}

export interface ProjectItem {
  project_id: string;
  name: string;
  client_id: string;
  report_type: "daily" | "weekly" | "monthly" | "crisis";
  cutoff_datetime: string;
  latest_job_id: string;
  status: "draft" | "running" | "completed" | "failed";
  total_raw: number;
  total_clean: number;
  total_takeout: number;
  created_at: string;
  updated_at: string;
}

export async function fetchProjects(): Promise<ProjectItem[]> {
  const res = await fetch(`${API_BASE}/api/projects`);
  if (!res.ok) throw new Error("Gagal memuat daftar project.");
  const data = await res.json();
  return data.projects || [];
}

export async function createProject(payload: {
  name: string;
  client_id: string;
  report_type: "daily" | "weekly" | "monthly" | "crisis";
  cutoff_datetime: string;
}): Promise<ProjectItem> {
  const res = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Gagal membuat project." }));
    throw new Error(err.detail || "Gagal membuat project.");
  }
  const data = await res.json();
  return data.project;
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Gagal menghapus project.");
}

export interface AIProviderStatus {
  id: string;
  name: string;
  model: string;
  pro_model?: string;
  configured: boolean;
}

export interface SystemAIStatus {
  providers: AIProviderStatus[];
  ai_batch_size: number;
  ai_max_concurrency: number;
  ai_max_retries: number;
}

export async function fetchSystemAIStatus(): Promise<SystemAIStatus> {
  const res = await fetch(`${API_BASE}/api/system/ai-status`);
  if (!res.ok) throw new Error("Gagal memuat status provider AI.");
  return res.json();
}

export async function updateSystemAISettings(payload: {
  deepseek_api_key?: string;
  openrouter_api_key?: string;
  groq_api_key?: string;
  gemini_api_key?: string;
  ai_batch_size?: number;
  ai_max_concurrency?: number;
}): Promise<SystemAIStatus> {
  const res = await fetch(`${API_BASE}/api/system/ai-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Gagal menyimpan pengaturan AI.");
  const data = await res.json();
  return data.ai_status;
}

export async function fetchClients(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/clients`);
  if (!res.ok) throw new Error("Gagal memuat daftar klien dari backend.");
  const data = await res.json();
  return data.clients || ["bri"];
}

export async function createClientProfile(payload: {
  client_id: string;
  client_name: string;
  focus_type: "brand_only" | "brand_and_competitor" | "crisis";
  custom_tier_enabled: boolean;
  custom_tier_column: string;
  competitors: string[];
}): Promise<{ client_id: string; config: ClientConfigData }> {
  const res = await fetch(`${API_BASE}/api/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Gagal membuat profil klien." }));
    throw new Error(err.detail || "Gagal membuat profil klien.");
  }
  return res.json();
}

export async function uploadJob(params: {
  files: File[];
  clientId: string;
  projectId?: string;
  cutoffDatetime: string;
  reqUploadUrls: string;
  takedownUrls: string;
  skipAi: boolean;
}): Promise<{ job_id: string; project_id?: string; client_id: string; status: string }> {
  const form = new FormData();
  for (const f of params.files) {
    form.append("files", f);
  }
  form.append("client_id", params.clientId);
  if (params.projectId) {
    form.append("project_id", params.projectId);
  }
  form.append("cutoff_datetime", params.cutoffDatetime);
  form.append("req_upload_urls", params.reqUploadUrls);
  form.append("takedown_urls", params.takedownUrls);
  form.append("skip_ai", String(params.skipAi));

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload gagal." }));
    throw new Error(err.detail || "Upload gagal.");
  }
  return res.json();
}

export function subscribeJobStream(
  jobId: string,
  onEvent: (ev: JobEventPayload) => void,
  onError: (msg: string) => void
): EventSource {
  const es = new EventSource(`${API_BASE}/api/process/${jobId}/stream`);
  const handle = (e: MessageEvent) => {
    try {
      const parsed: JobEventPayload = JSON.parse(e.data);
      onEvent(parsed);
      if (parsed.event === "done" || parsed.event === "error") {
        es.close();
      }
    } catch {
      // Ignore keep-alive or malformed lines
    }
  };
  es.addEventListener("progress", handle);
  es.addEventListener("done", handle);
  es.addEventListener("error", (e) => {
    if (e instanceof MessageEvent && e.data) {
      handle(e);
    } else {
      es.close();
      onError("Koneksi SSE ke backend terputus.");
    }
  });
  return es;
}

export async function fetchQCData(jobId: string): Promise<QCResponse> {
  const res = await fetch(`${API_BASE}/api/qc/${jobId}`);
  if (!res.ok) throw new Error("Gagal mengambil data QC.");
  return res.json();
}

export async function saveQCEdits(
  jobId: string,
  edits: Array<Record<string, unknown>>
): Promise<{ updated_count: number; synced_takeouts: number }> {
  const res = await fetch(`${API_BASE}/api/qc/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edits }),
  });
  if (!res.ok) throw new Error("Gagal menyimpan revisi QC.");
  return res.json();
}

export async function exportDeliverables(
  jobId: string,
  selectedColumns: string[] | null,
  exportPdf: boolean = false
): Promise<ExportResponse> {
  const res = await fetch(`${API_BASE}/api/export/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selected_columns: selectedColumns,
      export_pdf: exportPdf,
    }),
  });
  if (!res.ok) throw new Error("Gagal menghasilkan 3 Output Klien.");
  return res.json();
}

export async function fetchClientConfig(clientId: string): Promise<ClientConfigData> {
  const res = await fetch(`${API_BASE}/api/clients/${clientId}/config`);
  if (!res.ok) throw new Error(`Gagal memuat config klien '${clientId}'.`);
  return res.json();
}

export async function updateClientConfig(
  clientId: string,
  config: ClientConfigData
): Promise<ClientConfigData> {
  const res = await fetch(`${API_BASE}/api/clients/${clientId}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Gagal menyimpan config klien.");
  const data = await res.json();
  return data.config;
}

export async function importMediaMaster(
  file: File,
  customTierClientKey: string
): Promise<{ records_upserted: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("custom_tier_client_key", customTierClientKey);
  const res = await fetch(`${API_BASE}/api/media-master/import`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Gagal mengimpor master media.");
  return res.json();
}

export async function uploadClientPptxTemplate(
  clientId: string,
  file: File
): Promise<{ template_path: string; size_bytes: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/clients/${clientId}/template-pptx`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Gagal mengunggah template PPTX." }));
    throw new Error(err.detail || "Gagal mengunggah template PPTX.");
  }
  return res.json();
}
