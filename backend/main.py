"""FastAPI application for Newstent Local Web UI (Layer 2 — REST API & SSE, SAD.md Section 7B)."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.jobs import JobManager
from src.cleaning.media_lookup import import_media_master_file
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
from src.db.repositories import MediaMasterRepo
from src.settings import AppSettings, get_settings


class QCEditRequest(BaseModel):
    edits: list[dict[str, Any]] = Field(default_factory=list)


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

    # --- 1. Upload & Start Pipeline ---
    @app.post("/api/upload")
    async def upload_excel(
        files: list[UploadFile] = File(...),
        client_id: str = Form("bri"),
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
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return {"job_id": job.job_id, "client_id": job.client_id, "status": job.status}

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
