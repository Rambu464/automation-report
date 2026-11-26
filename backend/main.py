"""FastAPI application for Newstent Local Web UI (Layer 2 — REST API & SSE, SAD.md Section 7B)."""

from __future__ import annotations

import asyncio
import hashlib
import re
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.jobs import JobManager
from src.cleaning.media_lookup import import_client_custom_tier_file, import_media_master_file
from src.cleaning.url_utils import normalize_url
from src.config_loader import (
    AdhocColumnConfig,
    ClientConfig,
    CompetitorsConfig,
    CustomTierConfig,
    MediaAndSpokespersonConfig,
    list_clients,
    load_client_config,
    save_client_config,
)
from src.db.database import StateDatabase
from src.db.repositories import (
    ClientMediaTierRepo,
    MediaMasterRepo,
    ProjectRecord,
    ProjectRepo,
    TakeoutRecord,
    TakeoutRegistryRepo,
)
from src.settings import AppSettings, get_settings


class QCEditRequest(BaseModel):
    edits: list[dict[str, Any]] = Field(default_factory=list)


class AddQCRowRequest(BaseModel):
    page_url: str = ""
    media_name: str = ""
    title: str = Field(..., min_length=2)
    date: str = ""
    time: str = "12:00"
    media_type: str = "online"
    media_tier: str = ""
    sentiment: Literal["positive", "neutral", "negative"] = "positive"
    newstrends: str = ""
    nama_isu: str = ""
    content_type: Literal["Rilis", "Organik"] = "Rilis"
    spokesperson: str = "0"
    jabatan: str = "0"
    adhoc: dict[str, str] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    selected_columns: list[str] | None = None
    export_pdf: bool = False


class CreateClientRequest(BaseModel):
    client_id: str = Field(..., min_length=2, max_length=40)
    client_name: str = Field(..., min_length=2, max_length=120)
    focus_type: Literal["brand_only", "brand_and_competitor", "crisis"] = "brand_and_competitor"
    custom_tier_enabled: bool = True
    custom_tier_column: str = ""
    competitors: list[str] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    client_id: str = Field(..., min_length=1, max_length=40)
    report_type: Literal["daily", "weekly", "monthly", "crisis"] = "daily"
    cutoff_datetime: str = ""


class UpdateSystemAISettingsRequest(BaseModel):
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    ai_provider_order: list[str] | None = None
    ai_batch_size: int | None = Field(default=None, ge=5, le=100)
    ai_max_concurrency: int | None = Field(default=None, ge=1, le=12)


class RunPrecleanRequest(BaseModel):
    cutoff_datetime: str | None = None


class AddTakedownsRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    alasan_spam: str = "Takeout - Daftar Takedown Klien"
    is_sensitive_negative: bool = True


def create_app(
    settings: AppSettings | None = None,
    job_manager: JobManager | None = None,
) -> FastAPI:
    cfg_settings = settings or get_settings()
    db = StateDatabase(cfg_settings.sqlite_db_path)
    jm = job_manager if job_manager is not None else JobManager(settings=cfg_settings, db=db)

    app = FastAPI(
        title="Newstent Automation API",
        version="1.0.0",
        description="Local FastAPI backend for Newstent Analyst Workflow Automation Tool.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.job_manager = jm
    app.state.settings = cfg_settings
    app.state.db = db

    @app.get("/api/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "newstent-backend"}

    @app.get("/api/system/ai-status")
    def get_system_ai_status() -> dict[str, Any]:
        s = get_settings()
        provider_map = {
            "deepseek": {
                "id": "deepseek",
                "name": "DeepSeek",
                "model": s.deepseek_primary_model,
                "pro_model": s.deepseek_pro_model,
                "configured": bool(s.deepseek_api_key.strip()),
            },
            "openrouter": {
                "id": "openrouter",
                "name": "Qwen via OpenRouter",
                "model": s.openrouter_model,
                "configured": bool(s.openrouter_api_key.strip()),
            },
            "groq": {
                "id": "groq",
                "name": "Llama 3.3 via Groq",
                "model": s.groq_model,
                "configured": bool(s.groq_api_key.strip()),
            },
            "gemini": {
                "id": "gemini",
                "name": "Google Gemini",
                "model": s.gemini_model,
                "configured": bool(s.gemini_api_key.strip()),
            },
        }
        order = s.get_provider_order()
        return {
            "providers": [provider_map[pid] for pid in order],
            "provider_order": order,
            "ai_batch_size": s.ai_batch_size,
            "ai_max_concurrency": s.ai_max_concurrency,
            "ai_max_retries": s.ai_max_retries,
        }

    @app.put("/api/system/ai-settings")
    def update_system_ai_settings(req: UpdateSystemAISettingsRequest) -> dict[str, Any]:
        env_path = Path(".env")
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        updates: dict[str, str] = {}
        if req.deepseek_api_key is not None and req.deepseek_api_key.strip():
            updates["DEEPSEEK_API_KEY"] = req.deepseek_api_key.strip()
        if req.openrouter_api_key is not None and req.openrouter_api_key.strip():
            updates["OPENROUTER_API_KEY"] = req.openrouter_api_key.strip()
        if req.groq_api_key is not None and req.groq_api_key.strip():
            updates["GROQ_API_KEY"] = req.groq_api_key.strip()
        if req.gemini_api_key is not None and req.gemini_api_key.strip():
            updates["GEMINI_API_KEY"] = req.gemini_api_key.strip()
        if req.ai_provider_order is not None:
            allowed = ("deepseek", "openrouter", "groq", "gemini")
            cleaned: list[str] = []
            for p in req.ai_provider_order:
                pid = str(p).strip().lower()
                if pid in allowed and pid not in cleaned:
                    cleaned.append(pid)
            for pid in allowed:
                if pid not in cleaned:
                    cleaned.append(pid)
            updates["AI_PROVIDER_ORDER"] = ",".join(cleaned)
        if req.ai_batch_size is not None:
            updates["AI_BATCH_SIZE"] = str(req.ai_batch_size)
        if req.ai_max_concurrency is not None:
            updates["AI_MAX_CONCURRENCY"] = str(req.ai_max_concurrency)

        if updates:
            seen: set[str] = set()
            new_lines: list[str] = []
            for line in lines:
                matched_key = None
                for k in updates:
                    if line.startswith(f"{k}="):
                        matched_key = k
                        break
                if matched_key:
                    new_lines.append(f"{matched_key}={updates[matched_key]}")
                    seen.add(matched_key)
                else:
                    new_lines.append(line)
            for k, v in updates.items():
                if k not in seen:
                    new_lines.append(f"{k}={v}")
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            get_settings.cache_clear()
            jm.settings = get_settings()

        return {"status": "saved", "ai_status": get_system_ai_status()}

    # --- 0. Persistent Projects (1 Kasus = 1 Project) ---
    project_repo = ProjectRepo(db)

    @app.get("/api/projects")
    def get_projects() -> dict[str, Any]:
        return {"projects": [asdict(p) for p in project_repo.list_all()]}

    @app.post("/api/projects", status_code=201)
    def create_project(req: CreateProjectRequest) -> dict[str, Any]:
        try:
            load_client_config(req.client_id, clients_dir=cfg_settings.clients_dir)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        rec = ProjectRecord(
            project_id=f"prj_{uuid.uuid4().hex[:10]}",
            name=req.name.strip(),
            client_id=req.client_id.strip().lower(),
            report_type=req.report_type,
            cutoff_datetime=req.cutoff_datetime.strip(),
        )
        project_repo.create(rec)
        return {"status": "created", "project": asdict(rec)}

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        rec = project_repo.get(project_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Project tidak ditemukan: {project_id}")
        return {"project": asdict(rec)}

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict[str, Any]:
        if not project_repo.delete(project_id):
            raise HTTPException(status_code=404, detail=f"Project tidak ditemukan: {project_id}")
        return {"status": "deleted", "project_id": project_id}

    # --- 1. Step-by-Step 3-Stage Pipeline (Stage Raw -> Pre-Clean -> 3-Pass AI) + One-Shot Upload ---
    @app.post("/api/projects/{project_id}/stage-raw")
    async def stage_raw_files(
        project_id: str,
        files: list[UploadFile] = File(...),
        client_id: str = Form("bri"),
        cutoff_datetime: str = Form(""),
    ) -> dict[str, Any]:
        if not files:
            raise HTTPException(status_code=400, detail="Minimal 1 file .xls/.xlsx harus diunggah.")
        file_blobs: list[tuple[str, bytes]] = []
        for f in files:
            data = await f.read()
            if data:
                file_blobs.append((f.filename or "upload.xlsx", data))
        if not file_blobs:
            raise HTTPException(status_code=400, detail="File yang diunggah kosong.")

        try:
            return jm.stage_raw_job(
                project_id=project_id,
                client_id=client_id,
                file_blobs=file_blobs,
                cutoff_datetime=cutoff_datetime,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/run-preclean")
    def run_preclean_stage(job_id: str, body: RunPrecleanRequest | None = None) -> dict[str, Any]:
        try:
            return jm.run_preclean_stage(
                job_id=job_id,
                cutoff_datetime=body.cutoff_datetime if body else None,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/preclean-preview")
    def get_preclean_preview(job_id: str) -> dict[str, Any]:
        try:
            return jm.get_preclean_preview(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/run-ai")
    async def run_ai_stage(job_id: str) -> dict[str, Any]:
        try:
            job = jm.start_ai_stage(job_id)
            return {"job_id": job.job_id, "status": job.status}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/upload")
    async def upload_excel(
        files: list[UploadFile] = File(...),
        client_id: str = Form("bri"),
        project_id: str = Form(""),
        cutoff_datetime: str = Form(""),
        req_upload_urls: str = Form(""),
        takedown_urls: str = Form(""),
        skip_ai: bool = Form(False),
    ) -> dict[str, Any]:
        if not files:
            raise HTTPException(status_code=400, detail="Minimal 1 file .xls/.xlsx harus diunggah.")

        file_blobs: list[tuple[str, bytes]] = []
        for f in files:
            data = await f.read()
            if not data:
                continue
            file_blobs.append((f.filename or "upload.xlsx", data))

        if not file_blobs:
            raise HTTPException(status_code=400, detail="File yang diunggah kosong.")

        try:
            job = jm.create_job(
                client_id=client_id,
                file_blobs=file_blobs,
                cutoff_datetime=cutoff_datetime,
                req_upload_urls=req_upload_urls,
                takedown_urls=takedown_urls,
                skip_ai=skip_ai,
                project_id=project_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "client_id": job.client_id,
            "status": job.status,
        }

    # --- 2. SSE Live Progress Stream & Status ---
    @app.get("/api/process/{job_id}/stream")
    async def stream_job_progress(job_id: str) -> StreamingResponse:
        try:
            job = jm.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        async def event_generator() -> AsyncIterator[str]:
            sent_idx = 0
            while True:
                while sent_idx < len(job.events):
                    ev = job.events[sent_idx]
                    sent_idx += 1
                    yield ev.to_sse()
                    if ev.event in {"done", "error"}:
                        return
                if job.status in {"completed", "failed"}:
                    return
                waiter = job._notify
                try:
                    await asyncio.wait_for(waiter.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/jobs/{job_id}/status")
    def get_job_status(job_id: str) -> dict[str, Any]:
        try:
            job = jm.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        latest = job.events[-1] if job.events else None
        return {
            "job_id": job.job_id,
            "client_id": job.client_id,
            "status": job.status,
            "percent": latest.percent if latest else 0,
            "message": latest.message if latest else "",
            "error": job.error,
        }

    # --- 3. Interactive QC Table (GET & PATCH) ---
    @app.get("/api/qc/{job_id}")
    def get_qc_data(job_id: str) -> dict[str, Any]:
        try:
            return jm.load_qc_data(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/qc/{job_id}")
    def patch_qc_data(job_id: str, body: QCEditRequest) -> dict[str, Any]:
        try:
            return jm.apply_qc_edits(job_id, body.edits)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/qc/{job_id}/rows", status_code=201)
    def add_qc_row(job_id: str, body: AddQCRowRequest) -> dict[str, Any]:
        try:
            return jm.add_qc_row(job_id, body.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- 4. Client Config & Ad-Hoc Columns ---
    @app.get("/api/clients")
    def get_clients() -> dict[str, list[str]]:
        return {"clients": list_clients(clients_dir=cfg_settings.clients_dir)}

    @app.post("/api/clients", status_code=201)
    def create_client(req: CreateClientRequest) -> dict[str, Any]:
        slug = re.sub(r"[^a-z0-9_-]+", "_", req.client_id.strip().lower()).strip("_")
        if not slug:
            raise HTTPException(status_code=400, detail="client_id tidak valid.")
        existing = list_clients(clients_dir=cfg_settings.clients_dir)
        if slug in existing:
            raise HTTPException(status_code=409, detail=f"Profil klien '{slug}' sudah ada.")

        tier_col = req.custom_tier_column.strip() or f"TIER {slug.upper()}"
        comp_entities = [c.strip() for c in req.competitors if c.strip()]
        cfg = ClientConfig(
            client_id=slug,
            client_name=req.client_name.strip(),
            focus_type=req.focus_type,
            media_and_spokesperson=MediaAndSpokespersonConfig(
                custom_tier=CustomTierConfig(
                    enabled=req.custom_tier_enabled,
                    client_key=slug,
                    excel_column_name=tier_col,
                    fallback_to_bino_tier=True,
                )
            ),
            adhoc_columns=[
                AdhocColumnConfig(
                    name="Kluster",
                    description="Kelompokkan tema/divisi utama pemberitaan klien",
                ),
                AdhocColumnConfig(
                    name="Paid_Earned",
                    description="Klasifikasikan menjadi 'Paid' (advertorial/rilis berbayar) atau 'Earned' (liputan organik)",
                ),
            ],
            competitors=CompetitorsConfig(
                enabled=bool(comp_entities),
                entities=comp_entities,
            ),
        )
        save_client_config(cfg, clients_dir=cfg_settings.clients_dir)
        return {"status": "created", "client_id": slug, "config": cfg.model_dump(mode="json")}

    @app.get("/api/clients/{client_id}/config")
    def get_client_config(client_id: str) -> dict[str, Any]:
        try:
            cfg = load_client_config(client_id, clients_dir=cfg_settings.clients_dir)
            return cfg.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/clients/{client_id}/config")
    def put_client_config(client_id: str, config: ClientConfig) -> dict[str, Any]:
        if config.client_id != client_id:
            config = config.model_copy(update={"client_id": client_id})
        save_client_config(config, clients_dir=cfg_settings.clients_dir)
        return {"status": "saved", "config": config.model_dump(mode="json")}

    @app.post("/api/clients/{client_id}/template-pptx")
    async def upload_client_pptx_template(
        client_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        try:
            cfg = load_client_config(client_id, clients_dir=cfg_settings.clients_dir)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        filename = (file.filename or "").lower()
        if not filename.endswith(".pptx"):
            raise HTTPException(status_code=400, detail="File template harus berformat .pptx.")

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="File template .pptx kosong.")

        dest = Path(cfg_settings.clients_dir) / client_id / "template_daily.pptx"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)

        rel_path = f"clients/{client_id}/template_daily.pptx"
        cfg.output_templates.pptx_template_path = rel_path
        save_client_config(cfg, clients_dir=cfg_settings.clients_dir)

        return {
            "status": "uploaded",
            "client_id": client_id,
            "template_path": rel_path,
            "size_bytes": len(raw),
        }

    # --- 4b. Per-Client Custom Media Tier Override (`client_media_tier`) ---
    @app.get("/api/clients/{client_id}/custom-tier/status")
    def get_client_custom_tier_status(client_id: str) -> dict[str, Any]:
        repo = ClientMediaTierRepo(db)
        return {
            "client_id": client_id.strip().lower(),
            "total_overrides": repo.count_for_client(client_id),
        }

    @app.post("/api/clients/{client_id}/custom-tier/import")
    async def import_client_custom_tier(
        client_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        suffix = Path(file.filename or "custom_tier.csv").suffix or ".csv"
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="File Custom Media Tier kosong.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)

        try:
            repo = ClientMediaTierRepo(db)
            count = import_client_custom_tier_file(
                tmp_path,
                client_id=client_id,
                repo=repo,
            )
            return {
                "status": "imported",
                "client_id": client_id.strip().lower(),
                "records_upserted": count,
                "total_overrides": repo.count_for_client(client_id),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    # --- 4c. Per-Client Persistent Takedown Registry (`takeout_registry`) ---
    @app.get("/api/clients/{client_id}/takedowns")
    def list_client_takedowns(client_id: str) -> dict[str, Any]:
        cid = client_id.strip().lower()
        repo = TakeoutRegistryRepo(db)
        items = repo.list_by_client(cid)
        return {
            "client_id": cid,
            "count": len(items),
            "items": [asdict(item) for item in items],
        }

    @app.post("/api/clients/{client_id}/takedowns")
    def add_client_takedowns(client_id: str, body: AddTakedownsRequest) -> dict[str, Any]:
        cid = client_id.strip().lower()
        repo = TakeoutRegistryRepo(db)
        alasan = body.alasan_spam.strip() or "Takeout - Daftar Takedown Klien"

        records: list[TakeoutRecord] = []
        seen_norm: set[str] = set()
        for raw_url in body.urls:
            cleaned = str(raw_url or "").strip()
            if not cleaned:
                continue
            norm = normalize_url(cleaned)
            if not norm or norm in seen_norm:
                continue
            seen_norm.add(norm)
            digest = hashlib.sha256(f"{cid}:{norm}".encode("utf-8")).hexdigest()[:12].upper()
            records.append(
                TakeoutRecord(
                    report_id=f"TAKEDOWN-{digest}",
                    client_id=cid,
                    page_url=cleaned,
                    normalized_url=norm,
                    status_takeout="Takeout",
                    alasan_spam=alasan,
                    is_sensitive_negative=bool(body.is_sensitive_negative),
                )
            )

        if not records:
            raise HTTPException(status_code=400, detail="Masukkan minimal 1 URL valid untuk takedown.")

        added = repo.upsert_many(records)
        items = repo.list_by_client(cid)
        return {
            "status": "saved",
            "client_id": cid,
            "added": added,
            "count": len(items),
            "items": [asdict(item) for item in items],
        }

    @app.delete("/api/clients/{client_id}/takedowns")
    def delete_client_takedown(
        client_id: str,
        report_id: str = "",
        normalized_url: str = "",
    ) -> dict[str, Any]:
        cid = client_id.strip().lower()
        if not report_id.strip() and not normalized_url.strip():
            raise HTTPException(
                status_code=400,
                detail="Parameter report_id atau normalized_url wajib diisi.",
            )
        repo = TakeoutRegistryRepo(db)
        deleted = repo.delete_for_client(
            cid,
            report_id=report_id,
            normalized_url=normalized_url,
        )
        items = repo.list_by_client(cid)
        return {
            "status": "deleted" if deleted > 0 else "not_found",
            "deleted": deleted,
            "client_id": cid,
            "count": len(items),
            "items": [asdict(item) for item in items],
        }

    # --- 5. Media Master Import (CSV / XLSX) ---
    @app.post("/api/media-master/import")
    async def import_media_master(
        file: UploadFile = File(...),
        custom_tier_client_key: str = Form(""),
    ) -> dict[str, Any]:
        suffix = Path(file.filename or "media.csv").suffix or ".csv"
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="File master media kosong.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)

        try:
            count = import_media_master_file(
                tmp_path,
                repo=MediaMasterRepo(db),
                custom_tier_client_key=custom_tier_client_key.strip() or None,
            )
            return {"status": "imported", "records_upserted": count}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    # --- 6. Triple-Deliverable Export & Download ---
    @app.get("/api/export/{job_id}")
    def get_existing_export(job_id: str) -> dict[str, Any]:
        try:
            existing = jm.get_existing_export(job_id)
            if existing is None:
                return {"exported": False}
            return {"exported": True, **existing}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/export/{job_id}")
    def export_job(job_id: str, body: ExportRequest | None = None) -> dict[str, Any]:
        req = body or ExportRequest()
        try:
            return jm.export_deliverables(
                job_id=job_id,
                selected_columns=req.selected_columns,
                export_pdf=req.export_pdf,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/export/{job_id}/download/{artifact}")
    def download_artifact(job_id: str, artifact: str) -> FileResponse:
        try:
            job = jm.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        out_dir = job.job_dir / "output"
        patterns = {
            "excel": "*.xlsx",
            "pptx": "*.pptx",
            "pdf": "*.pdf",
            "wording": "*.txt",
        }
        if artifact not in patterns:
            raise HTTPException(status_code=400, detail=f"Tipe artifact tidak dikenal: {artifact}")

        matches = list(out_dir.glob(patterns[artifact]))
        if not matches:
            raise HTTPException(status_code=404, detail=f"File {artifact} belum digenerate.")

        file_path = matches[0]
        return FileResponse(path=str(file_path), filename=file_path.name)

    return app


app = create_app()
