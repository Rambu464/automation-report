"""Background Job Manager for FastAPI (Sprint 4 — orchestrates Sprints 1–3 with SSE progress)."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.ai_engine.client import LLMClientProtocol
from src.ai_engine.pass1_classifier import (
    PASS1_PROMPT_VERSION,
    make_cache_key,
    make_human_qc_cache_key,
    resolve_active_model_name,
)
from src.ai_engine.pipeline import AIEnginePipeline
from src.ai_engine.schemas import Pass3NarrativeOutput
from src.ai_engine.spokesperson import apply_three_tier_spokesperson_fallback
from src.cleaning.ingestion import ingest_excel_files
from src.cleaning.pipeline import PreCleaningPipeline
from src.cleaning.url_utils import extract_domain, normalize_url
from src.config_loader import load_client_config
from src.db.database import StateDatabase
from src.db.repositories import (
    AIBatchCacheRepo,
    ClientMediaTierRepo,
    ProjectRepo,
    TakeoutRecord,
    TakeoutRegistryRepo,
)
from src.generators.excel_generator import generate_cleaned_excel
from src.generators.pptx_generator import export_pptx_to_pdf, generate_pptx_report
from src.generators.wording_generator import render_wording_text, save_wording_text
from src.pivot.payload import build_report_payload, save_report_payload
from src.settings import AppSettings, get_settings


@dataclass
class JobEvent:
    event: str  # "progress" | "done" | "error"
    stage: str
    percent: int
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_sse(self) -> str:
        data = json.dumps(
            {
                "event": self.event,
                "stage": self.stage,
                "percent": self.percent,
                "message": self.message,
                "timestamp": self.timestamp,
            },
            ensure_ascii=False,
        )
        return f"event: {self.event}\ndata: {data}\n\n"


@dataclass
class JobState:
    job_id: str
    client_id: str
    job_dir: Path
    project_id: str = ""
    status: str = "queued"  # queued | running | completed | failed
    cutoff_datetime: str = ""
    req_upload_urls: str = ""
    takedown_urls: str = ""
    skip_ai: bool = False
    error: str = ""
    events: list[JobEvent] = field(default_factory=list)
    url_match_summary: dict[str, Any] = field(default_factory=dict)
    _notify: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def push_event(self, event: str, stage: str, percent: int, message: str) -> None:
        self.events.append(JobEvent(event=event, stage=stage, percent=percent, message=message))
        self._notify.set()
        self._notify = asyncio.Event()


class JobManager:
    """Manages processing jobs, QC persistence, and triple-deliverable exports."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        db: StateDatabase | None = None,
        llm_client: LLMClientProtocol | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db if db is not None else StateDatabase(self.settings.sqlite_db_path)
        self.llm_client = llm_client
        self.project_repo = ProjectRepo(self.db)
        self.jobs_root = self.settings.data_dir / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, JobState] = {}

    def get_job(self, job_id: str) -> JobState:
        if job_id in self._jobs:
            return self._jobs[job_id]
        # Rehydrate persisted job from disk after backend restart!
        job_dir = self.jobs_root / job_id
        meta_file = job_dir / "job_meta.json"
        payload_path = job_dir / "report_payload.json"
        if meta_file.exists() or payload_path.exists():
            meta_info: dict[str, Any] = (
                json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
            )
            payload = (
                json.loads(payload_path.read_text(encoding="utf-8"))
                if payload_path.exists()
                else {}
            )
            p_meta = payload.get("meta") or {}
            status = meta_info.get("status") or ("completed" if payload_path.exists() else "raw_uploaded")
            rehydrated = JobState(
                job_id=job_id,
                client_id=meta_info.get("client_id") or p_meta.get("client_id") or "bri",
                job_dir=job_dir,
                project_id=meta_info.get("project_id", ""),
                status=status,
                cutoff_datetime=meta_info.get("cutoff_datetime") or p_meta.get("cutoff_wib", ""),
                url_match_summary=meta_info.get("url_match_summary") or {},
            )
            self._jobs[job_id] = rehydrated
            return rehydrated
        raise KeyError(f"Job tidak ditemukan: {job_id}")

    @staticmethod
    def _build_raw_preview_dict(
        saved_paths: list[Path],
        raw_news_df: pd.DataFrame,
        raw_stmts_df: pd.DataFrame,
    ) -> dict[str, Any]:
        preview_cols = [
            c
            for c in ("ID", "Date", "Media Name", "Title", "Media Type", "Media Tier", "Sentiment", "Page/URL")
            if c in raw_news_df.columns
        ]
        sample_df = raw_news_df[preview_cols].head(200).fillna("")
        return {
            "files": [
                {"name": p.name, "size_bytes": p.stat().st_size if p.exists() else 0}
                for p in saved_paths
            ],
            "total_raw_news": int(len(raw_news_df)),
            "total_raw_statements": int(len(raw_stmts_df)),
            "columns": [str(c) for c in raw_news_df.columns],
            "rows": sample_df.to_dict(orient="records"),
        }

    def stage_raw_job(
        self,
        project_id: str,
        client_id: str,
        file_blobs: list[tuple[str, bytes]],
        cutoff_datetime: str = "",
    ) -> dict[str, Any]:
        """Stage 1 (Input Raw Data): save uploaded Excel files & extract raw preview (0 AI tokens, no SSE)."""
        load_client_config(client_id, clients_dir=self.settings.clients_dir)

        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_root / job_id
        raw_dir = job_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[Path] = []
        for filename, content in file_blobs:
            safe_name = Path(filename).name
            dest = raw_dir / safe_name
            dest.write_bytes(content)
            saved_paths.append(dest)

        wb = ingest_excel_files(saved_paths)
        raw_preview = self._build_raw_preview_dict(saved_paths, wb.news_df, wb.statements_df)
        (job_dir / "raw_preview.json").write_text(
            json.dumps(raw_preview, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        job = JobState(
            job_id=job_id,
            client_id=client_id,
            job_dir=job_dir,
            project_id=project_id,
            status="raw_uploaded",
            cutoff_datetime=cutoff_datetime,
        )
        self._jobs[job_id] = job
        (job_dir / "job_meta.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "project_id": project_id,
                    "client_id": client_id,
                    "status": "raw_uploaded",
                    "cutoff_datetime": cutoff_datetime,
                    "url_match_summary": {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if project_id:
            self.project_repo.update_status(
                project_id,
                latest_job_id=job_id,
                status="raw_uploaded",
                cutoff_datetime=cutoff_datetime,
                total_raw=raw_preview["total_raw_news"],
                total_clean=0,
                total_takeout=0,
            )

        return {
            "job_id": job_id,
            "project_id": project_id,
            "client_id": client_id,
            "status": "raw_uploaded",
            "cutoff_datetime": cutoff_datetime,
            "raw_preview": raw_preview,
        }

    def run_preclean_stage(
        self,
        job_id: str,
        cutoff_datetime: str | None = None,
    ) -> dict[str, Any]:
        """Stage 2 (Pre-Cleaning & Media Tier): run deterministic Sprint 1 cleaning (0 AI tokens)."""
        job = self.get_job(job_id)
        raw_dir = job.job_dir / "raw"
        excel_paths = sorted(
            [p for p in raw_dir.glob("*") if p.suffix.lower() in {".xls", ".xlsx"}]
        )
        if not excel_paths:
            raise ValueError("File raw Excel belum diunggah pada project ini.")

        if cutoff_datetime is not None:
            job.cutoff_datetime = cutoff_datetime.strip()

        # Ensure raw_preview.json exists even for legacy jobs
        if not (job.job_dir / "raw_preview.json").exists():
            wb = ingest_excel_files(excel_paths)
            raw_preview = self._build_raw_preview_dict(excel_paths, wb.news_df, wb.statements_df)
            (job.job_dir / "raw_preview.json").write_text(
                json.dumps(raw_preview, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)
        pre_pipeline = PreCleaningPipeline(db=self.db, clients_dir=self.settings.clients_dir)
        pre_res = pre_pipeline.run(
            excel_paths=excel_paths,
            client_id=job.client_id,
            cutoff_datetime=job.cutoff_datetime or None,
        )
        news_df = pre_res.news_df
        statements_df = pre_res.statements_df

        for col in ("Nama_Isu", "Content_Type"):
            if col not in news_df.columns:
                news_df[col] = "Organik" if col == "Content_Type" else ""
        for ac in config.adhoc_columns:
            if ac.name not in news_df.columns:
                news_df[ac.name] = ""
        news_df = apply_three_tier_spokesperson_fallback(
            news_df,
            missing_value=config.media_and_spokesperson.spokesperson_missing_value,
        )

        job.url_match_summary = {
            "req_upload_total": pre_res.url_match_summary.req_upload_total,
            "req_upload_matched": pre_res.url_match_summary.req_upload_matched,
            "req_upload_unmatched_urls": pre_res.url_match_summary.req_upload_unmatched_urls,
            "takedown_matched": pre_res.url_match_summary.takedown_matched,
            "historical_takeout_matched": pre_res.url_match_summary.historical_takeout_matched,
        }
        payload = build_report_payload(
            news_df=news_df,
            config=config,
            cutoff_wib=job.cutoff_datetime or "-",
            req_upload_matched=pre_res.url_match_summary.req_upload_matched,
        )
        job.status = "precleaned"
        self._save_job_dataframes(job, news_df, statements_df, payload, narrative=None)

        if job.project_id:
            p_meta = payload["meta"]
            self.project_repo.update_status(
                job.project_id,
                latest_job_id=job.job_id,
                status="precleaned",
                cutoff_datetime=job.cutoff_datetime,
                total_raw=p_meta["total_raw"],
                total_clean=p_meta["total_clean"],
                total_takeout=p_meta["total_takeout"],
            )

        return self.get_preclean_preview(job_id)

    def get_preclean_preview(self, job_id: str) -> dict[str, Any]:
        """Return Before (Raw) vs After (Pre-Cleaned) preview data for Node 2."""
        job = self.get_job(job_id)
        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)
        custom_tier_col = (
            config.media_and_spokesperson.custom_tier.excel_column_name
            if config.media_and_spokesperson.custom_tier.enabled
            else "Media Tier"
        )

        raw_preview_path = job.job_dir / "raw_preview.json"
        if raw_preview_path.exists():
            raw_preview = json.loads(raw_preview_path.read_text(encoding="utf-8"))
        else:
            raw_dir = job.job_dir / "raw"
            excel_paths = sorted(
                [p for p in raw_dir.glob("*") if p.suffix.lower() in {".xls", ".xlsx"}]
            )
            if excel_paths:
                wb = ingest_excel_files(excel_paths)
                raw_preview = self._build_raw_preview_dict(excel_paths, wb.news_df, wb.statements_df)
                raw_preview_path.write_text(
                    json.dumps(raw_preview, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                raw_preview = {
                    "files": [],
                    "total_raw_news": 0,
                    "total_raw_statements": 0,
                    "columns": [],
                    "rows": [],
                }

        cleaned_summary: dict[str, Any] | None = None
        news_path = job.job_dir / "news.json"
        payload_path = job.job_dir / "report_payload.json"
        if news_path.exists() and payload_path.exists():
            rows: list[dict[str, Any]] = json.loads(news_path.read_text(encoding="utf-8"))
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            takeout_reasons: dict[str, int] = {}
            ai_cluster_reps = 0
            for r in rows:
                if r.get("Status_Takeout") != "Keep":
                    reason = str(r.get("Alasan_Spam") or "Takeout Lainnya").strip()
                    takeout_reasons[reason] = takeout_reasons.get(reason, 0) + 1
                elif bool(r.get("Is_Cluster_Rep", True)):
                    ai_cluster_reps += 1

            preview_rows = [
                {
                    "ID": r.get("ID", ""),
                    "Date": r.get("Date", ""),
                    "Time": r.get("Time", ""),
                    "Media Name": r.get("Media Name", ""),
                    "Title": r.get("Title", ""),
                    "Page/URL": r.get("Page/URL", ""),
                    "Status_Takeout": r.get("Status_Takeout", "Keep"),
                    "Alasan_Spam": r.get("Alasan_Spam", ""),
                    "Tier": r.get(custom_tier_col) or r.get("Media Tier", ""),
                    "Flag_Cutoff_00": r.get("Flag_Cutoff_00", ""),
                    "Flag_Near_Dup": r.get("Flag_Near_Dup", ""),
                    "Cluster_ID": r.get("Cluster_ID", ""),
                    "Is_Cluster_Rep": bool(r.get("Is_Cluster_Rep", True)),
                    "Sentiment": r.get("Sentiment", ""),
                }
                for r in rows[:200]
            ]
            cleaned_summary = {
                "total_raw": payload["meta"]["total_raw"],
                "total_clean": payload["meta"]["total_clean"],
                "total_takeout": payload["meta"]["total_takeout"],
                "ai_cluster_reps": ai_cluster_reps,
                "custom_tier_col": custom_tier_col,
                "takeout_reasons": takeout_reasons,
                "by_custom_tier": payload["media_breakdown"]["by_custom_tier"],
                "by_type": payload["media_breakdown"]["by_type"],
                "rows": preview_rows,
            }

        return {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "client_id": job.client_id,
            "status": job.status,
            "cutoff_datetime": job.cutoff_datetime,
            "raw_preview": raw_preview,
            "cleaned_summary": cleaned_summary,
        }

    def start_ai_stage(self, job_id: str) -> JobState:
        """Stage 3 (3-Pass Cloud AI Engine): run AI classification & narrative on pre-cleaned data with SSE."""
        job = self.get_job(job_id)
        if not (job.job_dir / "news.json").exists():
            raise ValueError("Pre-Cleaning belum dijalankan. Jalankan Pre-Cleaning terlebih dahulu.")
        if not self._has_any_ai_key():
            raise ValueError(
                "API key Cloud AI belum diisi. Atur minimal 1 API key di Pengaturan Sistem terlebih dahulu."
            )

        job.events = []
        job.error = ""
        job.status = "running"
        if job.project_id:
            self.project_repo.update_status(job.project_id, status="running")
        job.push_event(
            "progress",
            "ai_engine",
            10,
            "Menyiapkan 3-Pass Cloud AI Engine (Pass 1 Micro-Batch, Spokesperson, Pass 2 Newstrend, Pass 3 Narasi)...",
        )
        asyncio.create_task(self._run_ai_only(job))
        return job

    async def _run_ai_only(self, job: JobState) -> None:
        try:
            config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)
            news_df = pd.read_json(job.job_dir / "news.json")
            stmts_path = job.job_dir / "statements.json"
            statements_df = pd.read_json(stmts_path) if stmts_path.exists() else pd.DataFrame()

            ai_pipeline = AIEnginePipeline(
                db=self.db,
                llm_client=self.llm_client,
                settings=self.settings,
            )

            def _on_ai_progress(done_b: int, total_b: int, msg: str) -> None:
                pct = 15 + int((done_b / max(1, total_b)) * 60)
                job.push_event("progress", "ai_engine", min(pct, 78), msg)

            ai_res = await ai_pipeline.classify_and_normalize(
                news_df=news_df,
                config=config,
                progress_callback=_on_ai_progress,
            )
            news_df = ai_res.news_df

            job.push_event(
                "progress",
                "pivot",
                84,
                f"Pass 1–2 selesai ({ai_res.pass1_stats.cache_hits} cache hit, {ai_res.pass1_stats.llm_classified} LLM). Menyusun Pivot...",
            )
            payload = build_report_payload(
                news_df=news_df,
                config=config,
                cutoff_wib=job.cutoff_datetime or "-",
                req_upload_matched=int(job.url_match_summary.get("req_upload_matched", 0)),
            )

            job.push_event(
                "progress",
                "narrative",
                92,
                "Pass 3: Menyusun Executive Summary & Arah Percakapan Publik...",
            )
            narrative = await ai_pipeline.generate_narrative(payload, config=config)

            job.status = "completed"
            self._save_job_dataframes(job, news_df, statements_df, payload, narrative)
            if job.project_id:
                p_meta = payload["meta"]
                self.project_repo.update_status(
                    job.project_id,
                    latest_job_id=job.job_id,
                    status="completed",
                    total_raw=p_meta["total_raw"],
                    total_clean=p_meta["total_clean"],
                    total_takeout=p_meta["total_takeout"],
                )
            job.push_event(
                "done",
                "completed",
                100,
                f"3-Pass AI Engine selesai! ({ai_res.pass1_stats.cache_hits} cache hit, {ai_res.pass1_stats.llm_classified} klasifikasi baru).",
            )
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            if job.project_id:
                self.project_repo.update_status(job.project_id, status="failed")
            job.push_event("error", "failed", 100, f"Gagal menjalankan 3-Pass AI Engine: {exc}")

    def create_job(
        self,
        client_id: str,
        file_blobs: list[tuple[str, bytes]],
        cutoff_datetime: str = "",
        req_upload_urls: str = "",
        takedown_urls: str = "",
        skip_ai: bool = False,
        project_id: str = "",
    ) -> JobState:
        # Validate client config upfront
        load_client_config(client_id, clients_dir=self.settings.clients_dir)

        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_root / job_id
        raw_dir = job_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[Path] = []
        for filename, content in file_blobs:
            safe_name = Path(filename).name
            dest = raw_dir / safe_name
            dest.write_bytes(content)
            saved_paths.append(dest)

        job = JobState(
            job_id=job_id,
            client_id=client_id,
            job_dir=job_dir,
            project_id=project_id,
            cutoff_datetime=cutoff_datetime,
            req_upload_urls=req_upload_urls,
            takedown_urls=takedown_urls,
            skip_ai=skip_ai,
        )
        self._jobs[job_id] = job
        if project_id:
            self.project_repo.update_status(
                project_id,
                latest_job_id=job_id,
                status="running",
                cutoff_datetime=cutoff_datetime,
            )
        job.push_event("progress", "queued", 5, f"File diterima ({len(saved_paths)} file). Menyiapkan pipeline...")

        asyncio.create_task(self._run_job(job, saved_paths))
        return job

    def _has_any_ai_key(self) -> bool:
        if self.llm_client is not None:
            return True
        s = self.settings
        return any([s.deepseek_api_key, s.openrouter_api_key, s.groq_api_key, s.gemini_api_key])

    async def _run_job(self, job: JobState, excel_paths: list[Path]) -> None:
        job.status = "running"
        try:
            config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)

            # Stage 1: Sprint 1 Deterministic Pre-Cleaning
            job.push_event(
                "progress",
                "pre_cleaning",
                15,
                "Tahap 1/3: Pre-Cleaning, Cutoff 00:00, Deduplikasi 3-Lapis, & Media Tier Lookup...",
            )
            pre_pipeline = PreCleaningPipeline(db=self.db, clients_dir=self.settings.clients_dir)
            pre_res = await asyncio.to_thread(
                pre_pipeline.run,
                excel_paths=excel_paths,
                client_id=job.client_id,
                cutoff_datetime=job.cutoff_datetime or None,
                req_upload_urls=job.req_upload_urls or None,
                takedown_urls=job.takedown_urls or None,
            )
            news_df = pre_res.news_df
            statements_df = pre_res.statements_df
            job.url_match_summary = {
                "req_upload_total": pre_res.url_match_summary.req_upload_total,
                "req_upload_matched": pre_res.url_match_summary.req_upload_matched,
                "req_upload_unmatched_urls": pre_res.url_match_summary.req_upload_unmatched_urls,
                "takedown_matched": pre_res.url_match_summary.takedown_matched,
                "historical_takeout_matched": pre_res.url_match_summary.historical_takeout_matched,
            }
            job.push_event(
                "progress",
                "pre_cleaning_done",
                35,
                f"Pre-Cleaning selesai: {pre_res.stats.total_keep} Keep / {pre_res.stats.total_takeout} Takeout "
                f"({pre_res.stats.ai_cluster_reps} perwakilan klaster untuk AI).",
            )

            # Stage 2: Sprint 2 3-Pass Cloud AI Engine (or deterministic fallback if skip_ai / no API key)
            narrative: Pass3NarrativeOutput | None = None
            if job.skip_ai or not self._has_any_ai_key():
                reason = "Mode Pre-Clean Only dipilih" if job.skip_ai else "API key Cloud AI belum diisi di .env"
                job.push_event(
                    "progress",
                    "ai_skipped",
                    70,
                    f"Tahap 2/3 dilewati ({reason}). Menerapkan 3-Tier Spokesperson default '0'...",
                )
                for col in ("Nama_Isu", "Content_Type"):
                    if col not in news_df.columns:
                        news_df[col] = "Organik" if col == "Content_Type" else ""
                for ac in config.adhoc_columns:
                    if ac.name not in news_df.columns:
                        news_df[ac.name] = ""
                news_df = apply_three_tier_spokesperson_fallback(
                    news_df,
                    missing_value=config.media_and_spokesperson.spokesperson_missing_value,
                )
            else:
                ai_pipeline = AIEnginePipeline(
                    db=self.db,
                    llm_client=self.llm_client,
                    settings=self.settings,
                )

                def _on_ai_progress(done_b: int, total_b: int, msg: str) -> None:
                    pct = 35 + int((done_b / max(1, total_b)) * 45)
                    job.push_event("progress", "ai_engine", min(pct, 80), msg)

                ai_res = await ai_pipeline.classify_and_normalize(
                    news_df=news_df,
                    config=config,
                    progress_callback=_on_ai_progress,
                )
                news_df = ai_res.news_df

            # Stage 3: Sprint 3 Auto-Pivot & report_payload.json
            job.push_event("progress", "pivot", 85, "Tahap 3/3: Menyusun Auto-Pivot & report_payload.json...")
            cutoff_label = job.cutoff_datetime or "-"
            payload = build_report_payload(
                news_df=news_df,
                config=config,
                cutoff_wib=cutoff_label,
                req_upload_matched=pre_res.url_match_summary.req_upload_matched,
            )

            # Optional Pass 3 Narrative if AI enabled
            if not job.skip_ai and self._has_any_ai_key():
                job.push_event("progress", "narrative", 92, "Pass 3: Menyusun Executive Summary & Arah Percakapan...")
                ai_pipeline = AIEnginePipeline(
                    db=self.db,
                    llm_client=self.llm_client,
                    settings=self.settings,
                )
                narrative = await ai_pipeline.generate_narrative(payload, config=config)

            # Persist job state to disk
            self._save_job_dataframes(job, news_df, statements_df, payload, narrative)
            job.status = "completed"
            if job.project_id:
                p_meta = payload["meta"]
                self.project_repo.update_status(
                    job.project_id,
                    latest_job_id=job.job_id,
                    status="completed",
                    total_raw=p_meta["total_raw"],
                    total_clean=p_meta["total_clean"],
                    total_takeout=p_meta["total_takeout"],
                )
            job.push_event("done", "completed", 100, "Selesai! Silakan tinjau data di Tabel QC atau langsung ekspor 3 Output.")

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            if job.project_id:
                self.project_repo.update_status(job.project_id, status="failed")
            job.push_event("error", "failed", 100, f"Gagal memproses job: {exc}")

    def _save_job_dataframes(
        self,
        job: JobState,
        news_df: pd.DataFrame,
        statements_df: pd.DataFrame,
        payload: dict[str, Any],
        narrative: Pass3NarrativeOutput | None,
    ) -> None:
        news_df.to_json(job.job_dir / "news.json", orient="records", force_ascii=False, indent=2)
        statements_df.to_json(job.job_dir / "statements.json", orient="records", force_ascii=False, indent=2)
        save_report_payload(payload, job.job_dir / "report_payload.json")
        (job.job_dir / "job_meta.json").write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "project_id": job.project_id,
                    "client_id": job.client_id,
                    "status": job.status,
                    "cutoff_datetime": job.cutoff_datetime,
                    "url_match_summary": job.url_match_summary,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if narrative is not None:
            (job.job_dir / "narrative.json").write_text(
                narrative.model_dump_json(indent=2), encoding="utf-8"
            )

    def load_qc_data(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        news_path = job.job_dir / "news.json"
        if not news_path.exists():
            raise ValueError("Data QC belum tersedia; job masih berjalan atau gagal.")

        rows: list[dict[str, Any]] = json.loads(news_path.read_text(encoding="utf-8"))
        payload = json.loads((job.job_dir / "report_payload.json").read_text(encoding="utf-8"))
        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)

        columns = list(rows[0].keys()) if rows else []
        tab_counts = {
            "all": len(rows),
            "cutoff_00": sum(1 for r in rows if r.get("Flag_Cutoff_00") == "CEK_CUTOFF_00:00"),
            "takeout": sum(1 for r in rows if r.get("Status_Takeout") != "Keep"),
            "rilis_spk_zero": sum(
                1
                for r in rows
                if r.get("Status_Takeout") == "Keep"
                and str(r.get("Content_Type", "")).strip().lower() == "rilis"
                and str(r.get("Spokesperson", "")).strip() in {"", "0"}
            ),
            "near_dup": sum(1 for r in rows if r.get("Flag_Near_Dup") == "CEK_MIRIP_JUDUL"),
        }

        return {
            "job_id": job_id,
            "client_id": job.client_id,
            "status": job.status,
            "columns": columns,
            "adhoc_columns": [c.name for c in config.adhoc_columns],
            "tab_counts": tab_counts,
            "url_match_summary": job.url_match_summary,
            "report_payload": payload,
            "rows": rows,
        }

    def apply_qc_edits(self, job_id: str, edits: list[dict[str, Any]]) -> dict[str, Any]:
        """Apply analyst inline QC edits, sync sensitive takeouts to SQLite, and regenerate `report_payload.json`."""
        job = self.get_job(job_id)
        news_path = job.job_dir / "news.json"
        if not news_path.exists():
            raise ValueError("Data QC belum tersedia.")

        rows: list[dict[str, Any]] = json.loads(news_path.read_text(encoding="utf-8"))
        row_by_id = {str(r["ID"]): r for r in rows}

        takeout_repo = TakeoutRegistryRepo(self.db)
        cache_repo = AIBatchCacheRepo(self.db)
        new_takeouts: list[TakeoutRecord] = []
        today_str = date.today().isoformat()

        allowed_fields = {
            "Status_Takeout",
            "Alasan_Spam",
            "Sentiment",
            "Newstrends",
            "Nama_Isu",
            "Content_Type",
            "Spokesperson",
            "Jabatan",
        }
        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)
        adhoc_names = [c.name for c in config.adhoc_columns]
        allowed_fields.update(adhoc_names)

        # Map Cluster_ID -> cluster representative row (Is_Cluster_Rep == True)
        cluster_rep_by_cid: dict[str, dict[str, Any]] = {}
        for r in rows:
            cid = str(r.get("Cluster_ID") or "").strip()
            if cid and bool(r.get("Is_Cluster_Rep")):
                cluster_rep_by_cid[cid] = r

        updated_count = 0
        edited_ids: list[str] = []
        edited_id_set: set[str] = set()
        for edit in edits:
            rid = str(edit.get("ID", "")).strip()
            if rid not in row_by_id:
                continue
            target = row_by_id[rid]
            changed_ai_field = False
            for field_name, val in edit.items():
                if field_name in allowed_fields:
                    target[field_name] = val
                    changed_ai_field = True
            updated_count += 1
            if changed_ai_field and rid not in edited_id_set:
                edited_ids.append(rid)
                edited_id_set.add(rid)

            # Sync to SQLite takeout_registry when analyst marks Takeout (especially sensitive negative)
            if target.get("Status_Takeout") == "Takeout" and (
                edit.get("sync_to_monthly", True)
            ):
                new_takeouts.append(
                    TakeoutRecord(
                        report_id=rid,
                        client_id=job.client_id,
                        page_url=str(target.get("Page/URL", "")),
                        normalized_url=normalize_url(str(target.get("Page/URL", ""))),
                        status_takeout="Takeout",
                        alasan_spam=str(target.get("Alasan_Spam", "") or "Takeout Manual QC"),
                        is_sensitive_negative=bool(edit.get("is_sensitive_negative", False))
                        or str(target.get("Sentiment", "")).lower() == "negative",
                        recorded_date=today_str,
                    )
                )
            elif target.get("Status_Takeout") == "Keep":
                takeout_repo.delete_by_report_id(rid, client_id=job.client_id)

        if new_takeouts:
            takeout_repo.upsert_many(new_takeouts)

        # Sync analyst manual QC corrections to SQLite ai_batch_cache (with "source": "human_qc")
        cfg_hash = config.config_version_hash()
        active_model = resolve_active_model_name(
            llm_client=self.llm_client,
            settings=self.settings,
        )

        def _build_human_qc_payload(row: dict[str, Any]) -> dict[str, Any]:
            return {
                "source": "human_qc",
                "status_takeout": str(row.get("Status_Takeout") or "Keep"),
                "alasan_spam": str(row.get("Alasan_Spam") or ""),
                "sentiment": str(row.get("Sentiment") or "neutral").strip().lower(),
                "draft_newstrend": str(row.get("Newstrends") or ""),
                "nama_isu": str(row.get("Nama_Isu") or ""),
                "content_type": str(row.get("Content_Type") or "Organik"),
                "spokesperson": str(row.get("Spokesperson") or ""),
                "jabatan": str(row.get("Jabatan") or ""),
                "adhoc": {col: str(row.get(col) or "") for col in adhoc_names},
                "prompt_version": PASS1_PROMPT_VERSION,
                "model_name": active_model,
            }

        cache_entries: dict[str, dict[str, Any]] = {}
        synced_report_ids: set[str] = set()
        for rid in edited_ids:
            target = row_by_id[rid]
            qc_payload = _build_human_qc_payload(target)
            for key in (
                make_cache_key(
                    rid,
                    cfg_hash,
                    prompt_version=PASS1_PROMPT_VERSION,
                    model_name=active_model,
                ),
                make_human_qc_cache_key(rid, job.client_id),
            ):
                cache_entries[key] = qc_payload
            synced_report_ids.add(rid)

            # If this row belongs to a syndicated cluster, also sync its cluster representative
            cid = str(target.get("Cluster_ID") or "").strip()
            if cid and cid in cluster_rep_by_cid:
                rep_id = str(cluster_rep_by_cid[cid].get("ID", "")).strip()
                if rep_id and rep_id != rid and rep_id not in edited_id_set:
                    for key in (
                        make_cache_key(
                            rep_id,
                            cfg_hash,
                            prompt_version=PASS1_PROMPT_VERSION,
                            model_name=active_model,
                        ),
                        make_human_qc_cache_key(rep_id, job.client_id),
                    ):
                        cache_entries[key] = qc_payload
                    synced_report_ids.add(rep_id)

        if cache_entries:
            cache_repo.set_many(cache_entries)

        # Persist updated news.json and regenerate report_payload.json
        news_df = pd.DataFrame(rows)
        news_df.to_json(news_path, orient="records", force_ascii=False, indent=2)

        payload = build_report_payload(
            news_df=news_df,
            config=config,
            cutoff_wib=job.cutoff_datetime or "-",
            req_upload_matched=int(job.url_match_summary.get("req_upload_matched", 0)),
        )
        save_report_payload(payload, job.job_dir / "report_payload.json")
        if job.project_id:
            p_meta = payload["meta"]
            self.project_repo.update_status(
                job.project_id,
                total_raw=p_meta["total_raw"],
                total_clean=p_meta["total_clean"],
                total_takeout=p_meta["total_takeout"],
            )

        return {
            "updated_count": updated_count,
            "synced_takeouts": len(new_takeouts),
            "synced_ai_cache": len(synced_report_ids),
            "report_payload": payload,
        }

    def add_qc_row(self, job_id: str, row_data: dict[str, Any]) -> dict[str, Any]:
        """Insert a manual Req Upload article directly into the QC table with automatic Custom Media Tier lookup."""
        job = self.get_job(job_id)
        news_path = job.job_dir / "news.json"
        if not news_path.exists():
            raise ValueError("Data QC belum tersedia.")

        rows: list[dict[str, Any]] = json.loads(news_path.read_text(encoding="utf-8"))
        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)

        page_url = str(row_data.get("page_url") or "").strip()
        title = str(row_data.get("title") or "").strip()
        if not title:
            raise ValueError("Judul berita wajib diisi.")

        domain = extract_domain(page_url) if page_url else ""
        media_name = str(row_data.get("media_name") or "").strip() or domain or "Media Manual"
        media_type = str(row_data.get("media_type") or "online").strip().lower() or "online"

        # Auto-lookup Per-Client Custom Media Tier (Priority 1: domain/name in client_media_tier)
        tier_map = ClientMediaTierRepo(self.db).get_map_for_client(job.client_id)
        resolved_tier = (
            tier_map.get(domain)
            or tier_map.get(media_name.lower())
            or str(row_data.get("media_tier") or "").strip()
            or "Tier 3"
        )

        row_date = str(row_data.get("date") or "").strip() or date.today().isoformat()
        row_time = str(row_data.get("time") or "").strip() or "12:00"
        sentiment = str(row_data.get("sentiment") or "positive").strip().lower()
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"
        content_type = str(row_data.get("content_type") or "Rilis").strip() or "Rilis"
        newstrends = str(row_data.get("newstrends") or "").strip()
        nama_isu = str(row_data.get("nama_isu") or "").strip() or newstrends
        spokesperson = str(row_data.get("spokesperson") or "").strip() or "0"
        jabatan = str(row_data.get("jabatan") or "").strip() or "0"
        adhoc_input = row_data.get("adhoc") or {}

        new_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        new_row: dict[str, Any] = {
            "ID": new_id,
            "Title": title,
            "Content": title,
            "Content_Clean": title,
            "Content_Snippet": title,
            "Date": row_date,
            "Time": row_time,
            "Media Name": media_name,
            "Page/URL": page_url,
            "Normalized_URL": normalize_url(page_url) if page_url else "",
            "Media Type": media_type,
            "Media Type Detail": "Organik",
            "Media Tier": resolved_tier,
            "Oplah/Daily Visitor": 0,
            "Sentiment": sentiment,
            "Newstrends": newstrends,
            "Nama_Isu": nama_isu,
            "Content_Type": content_type,
            "Spokesperson": spokesperson,
            "Jabatan": jabatan,
            "Has_Statement": False,
            "Status_Takeout": "Keep",
            "Alasan_Spam": "",
            "Flag_Cutoff_00": "CEK_CUTOFF_00:00" if row_time == "00:00" else "",
            "Flag_Near_Dup": "",
            "Cluster_ID": f"CL-{new_id}",
            "Is_Cluster_Rep": True,
            "Status_Req_Upload": "Manual Insert (Req Upload)",
        }

        if config.media_and_spokesperson.custom_tier.enabled:
            custom_col = config.media_and_spokesperson.custom_tier.excel_column_name
            new_row[custom_col] = resolved_tier

        for ac in config.adhoc_columns:
            new_row[ac.name] = str(adhoc_input.get(ac.name, "") or "").strip()

        # Prepend so the newly added Req Upload row is immediately visible at the top
        rows.insert(0, new_row)

        news_df = pd.DataFrame(rows)
        news_df.to_json(news_path, orient="records", force_ascii=False, indent=2)

        # Increment req_upload_matched count
        job.url_match_summary["req_upload_matched"] = (
            int(job.url_match_summary.get("req_upload_matched", 0)) + 1
        )
        payload = build_report_payload(
            news_df=news_df,
            config=config,
            cutoff_wib=job.cutoff_datetime or "-",
            req_upload_matched=int(job.url_match_summary.get("req_upload_matched", 0)),
        )
        save_report_payload(payload, job.job_dir / "report_payload.json")
        if job.project_id:
            p_meta = payload["meta"]
            self.project_repo.update_status(
                job.project_id,
                total_raw=p_meta["total_raw"],
                total_clean=p_meta["total_clean"],
                total_takeout=p_meta["total_takeout"],
            )

        return {
            "row": new_row,
            "report_payload": payload,
        }

    def export_deliverables(
        self,
        job_id: str,
        selected_columns: list[str] | None = None,
        export_pdf: bool = False,
    ) -> dict[str, Any]:
        """Generate Output 1 (`.xlsx`), Output 2 (`.pptx`/`.pdf`), and Output 3 (`Wording`)."""
        job = self.get_job(job_id)
        news_df = pd.read_json(job.job_dir / "news.json", orient="records")
        stmt_path = job.job_dir / "statements.json"
        statements_df = (
            pd.read_json(stmt_path, orient="records")
            if stmt_path.exists()
            else pd.DataFrame(columns=["Report id", "Name", "Position", "Sentiment", "Quote"])
        )
        payload = json.loads((job.job_dir / "report_payload.json").read_text(encoding="utf-8"))
        nar_path = job.job_dir / "narrative.json"
        narrative = json.loads(nar_path.read_text(encoding="utf-8")) if nar_path.exists() else None
        config = load_client_config(job.client_id, clients_dir=self.settings.clients_dir)

        out_dir = job.job_dir / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        excel_path = generate_cleaned_excel(
            news_df=news_df,
            statements_df=statements_df,
            report_payload=payload,
            config=config,
            output_path=out_dir / f"{config.client_id}_cleaned_{job_id}.xlsx",
            selected_columns=selected_columns,
        )
        pptx_path = generate_pptx_report(
            report_payload=payload,
            narrative=narrative,
            config=config,
            output_path=out_dir / f"{config.client_id}_report_{job_id}.pptx",
        )
        pdf_path = export_pptx_to_pdf(pptx_path, output_dir=out_dir) if export_pdf else None

        wording_text = render_wording_text(payload, narrative, config)
        wording_path = save_wording_text(
            wording_text, out_dir / f"{config.client_id}_wording_{job_id}.txt"
        )

        return {
            "job_id": job_id,
            "excel_url": f"/api/export/{job_id}/download/excel",
            "pptx_url": f"/api/export/{job_id}/download/pptx",
            "pdf_url": f"/api/export/{job_id}/download/pdf" if pdf_path else None,
            "wording_url": f"/api/export/{job_id}/download/wording",
            "wording_text": wording_text,
            "files": {
                "excel": str(excel_path),
                "pptx": str(pptx_path),
                "pdf": str(pdf_path) if pdf_path else None,
                "wording": str(wording_path),
            },
        }

    def get_existing_export(self, job_id: str) -> dict[str, Any] | None:
        """Rehydrate previously generated deliverables from disk so ExportPanel persists across browser refresh."""
        job = self.get_job(job_id)
        out_dir = job.job_dir / "output"
        if not out_dir.exists():
            return None

        excel_matches = list(out_dir.glob("*.xlsx"))
        pptx_matches = list(out_dir.glob("*.pptx"))
        pdf_matches = list(out_dir.glob("*.pdf"))
        wording_matches = list(out_dir.glob("*.txt"))
        if not (excel_matches or pptx_matches or wording_matches):
            return None

        wording_text = (
            wording_matches[0].read_text(encoding="utf-8") if wording_matches else ""
        )
        return {
            "job_id": job_id,
            "excel_url": f"/api/export/{job_id}/download/excel" if excel_matches else "",
            "pptx_url": f"/api/export/{job_id}/download/pptx" if pptx_matches else "",
            "pdf_url": f"/api/export/{job_id}/download/pdf" if pdf_matches else None,
            "wording_url": f"/api/export/{job_id}/download/wording" if wording_matches else "",
            "wording_text": wording_text,
            "files": {
                "excel": str(excel_matches[0]) if excel_matches else None,
                "pptx": str(pptx_matches[0]) if pptx_matches else None,
                "pdf": str(pdf_matches[0]) if pdf_matches else None,
                "wording": str(wording_matches[0]) if wording_matches else None,
            },
        }
