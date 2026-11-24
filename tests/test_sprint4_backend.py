"""Integration tests for Sprint 4 Backend (FastAPI REST endpoints, SSE progress, QC sync, & Export)."""

from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.jobs import JobManager
from backend.main import create_app
from src.db.database import StateDatabase
from src.db.repositories import TakeoutRegistryRepo
from src.settings import AppSettings


def _make_excel_bytes() -> bytes:
    news_rows = [
        {
            "ID": "API-001",
            "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM",
            "Content": "Penyaluran KUR BRI meningkat tajam sepanjang kuartal keempat.",
            "Date": "2026-11-19 10:00",
            "Media Name": "Kompas.com",
            "Page/URL": "https://kompas.com/bri-kur-api-1",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 500000,
            "Sentiment": "positive",
            "Newstrends": "BRI Salurkan KUR Dorong UMKM",
        },
        {
            "ID": "API-002",
            "Title": "Layanan Digital BRImo Catat Rekor",
            "Content": "Aplikasi BRImo mencatat transaksi harian tertinggi.",
            "Date": "2026-11-19 00:00",
            "Media Name": "Detik.com",
            "Page/URL": "https://detik.com/brimo-api-2",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 400000,
            "Sentiment": "positive",
            "Newstrends": "BRImo Catat Rekor Transaksi",
        },
    ]
    stmt_rows = [
        {
            "Report id": "API-001",
            "Name": "Sunarso",
            "Position": "Direktur Utama BRI",
            "Sentiment": "positive",
            "Quote": "BRI berkomitmen mendorong UMKM.",
        }
    ]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(news_rows).to_excel(writer, sheet_name="News", index=False)
        pd.DataFrame(stmt_rows).to_excel(writer, sheet_name="Statements", index=False)
    return buf.getvalue()


def test_fastapi_full_workflow_upload_sse_qc_config_media_and_export(tmp_path: Path) -> None:
    # Copy bri config into isolated temp clients_dir so PUT tests don't mutate repo files
    clients_dir = tmp_path / "clients"
    (clients_dir / "bri").mkdir(parents=True)
    (clients_dir / "bri" / "config.yaml").write_text(
        Path("clients/bri/config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    settings = AppSettings(
        sqlite_db_path=tmp_path / "api_state.db",
        data_dir=tmp_path / "data",
        clients_dir=clients_dir,
    )
    db = StateDatabase(settings.sqlite_db_path)
    jm = JobManager(settings=settings, db=db)
    app = create_app(settings=settings, job_manager=jm)

    with TestClient(app) as client:
        # 1. Health & Clients + Create New Client Profile
        assert client.get("/api/health").json()["status"] == "ok"
        assert "bri" in client.get("/api/clients").json()["clients"]

        r_new = client.post(
            "/api/clients",
            json={
                "client_id": "mandiri",
                "client_name": "Bank Mandiri",
                "focus_type": "brand_and_competitor",
                "custom_tier_enabled": True,
                "custom_tier_column": "TIER MANDIRI",
                "competitors": ["BRI", "BNI", "BCA"],
            },
        )
        assert r_new.status_code == 201
        assert "mandiri" in client.get("/api/clients").json()["clients"]
        assert client.post(
            "/api/clients",
            json={"client_id": "mandiri", "client_name": "Duplicate"},
        ).status_code == 409

        # 2. Import Media Master CSV
        csv_bytes = (
            "domain,media_name,tier_bino,TIER BRI,media_type_detail,hypestat_daily_visitor\n"
            "kompas.com,Kompas.com,Tier 1,Tier 1,Organik,900000\n"
        ).encode("utf-8")
        r_media = client.post(
            "/api/media-master/import",
            files={"file": ("media.csv", csv_bytes, "text/csv")},
            data={"custom_tier_client_key": "bri"},
        )
        assert r_media.status_code == 200
        assert r_media.json()["records_upserted"] == 1

        # 3. Upload Excel & run pipeline (skip_ai=true for offline deterministic test)
        r_up = client.post(
            "/api/upload",
            files={"files": ("newstensity.xlsx", _make_excel_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"client_id": "bri", "cutoff_datetime": "2026-11-19 15:00", "skip_ai": "true"},
        )
        assert r_up.status_code == 200
        job_id = r_up.json()["job_id"]

        # 4. SSE stream completes with 'done'
        with client.stream("GET", f"/api/process/{job_id}/stream") as resp:
            assert resp.status_code == 200
            stream_body = "".join(resp.iter_text())
        assert "event: done" in stream_body

        # Wait briefly if needed (SSE 'done' already guarantees completion)
        for _ in range(10):
            if client.get(f"/api/jobs/{job_id}/status").json()["status"] == "completed":
                break
            time.sleep(0.05)

        # 5. GET QC Data (check 4-tab counts, including 00:00 flag)
        qc = client.get(f"/api/qc/{job_id}").json()
        assert qc["tab_counts"]["all"] == 2
        assert qc["tab_counts"]["cutoff_00"] == 1

        # 6. PATCH QC Data (mark API-002 as Takeout -> syncs SQLite takeout_registry & updates payload)
        r_patch = client.patch(
            f"/api/qc/{job_id}",
            json={
                "edits": [
                    {
                        "ID": "API-002",
                        "Status_Takeout": "Takeout",
                        "Alasan_Spam": "Takeout Manual Analis",
                        "is_sensitive_negative": True,
                    }
                ]
            },
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["report_payload"]["meta"]["total_clean"] == 1
        assert r_patch.json()["report_payload"]["meta"]["total_takeout"] == 1
        by_id, _ = TakeoutRegistryRepo(db).get_by_client("bri")
        assert "API-002" in by_id

        # 7. GET & PUT Client Config (add an Ad-Hoc column dynamically) + Upload PPTX Template
        cfg_data = client.get("/api/clients/bri/config").json()
        cfg_data["adhoc_columns"].append(
            {"name": "Sub_Program", "description": "Nama program khusus BRI"}
        )
        r_put = client.put("/api/clients/bri/config", json=cfg_data)
        assert r_put.status_code == 200
        assert any(c["name"] == "Sub_Program" for c in r_put.json()["config"]["adhoc_columns"])

        from pptx import Presentation

        pptx_buf = io.BytesIO()
        Presentation().save(pptx_buf)
        r_tpl = client.post(
            "/api/clients/bri/template-pptx",
            files={
                "file": (
                    "bri_template.pptx",
                    pptx_buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        assert r_tpl.status_code == 200
        assert (clients_dir / "bri" / "template_daily.pptx").exists()

        # 8. Export Triple Deliverables (with Column Picker) & Download
        r_exp = client.post(
            f"/api/export/{job_id}",
            json={"selected_columns": ["ID", "Date", "Title", "Media Name", "TIER BRI", "Sentiment"]},
        )
        assert r_exp.status_code == 200
        exp = r_exp.json()
        assert "Total Pemberitaan Bersih: 1 berita" in exp["wording_text"]

        assert client.get(exp["excel_url"]).status_code == 200
        assert client.get(exp["pptx_url"]).status_code == 200
        assert client.get(exp["wording_url"]).status_code == 200
