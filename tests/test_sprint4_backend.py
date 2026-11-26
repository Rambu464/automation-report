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

        # 2. Import Per-Client Custom Media Tier CSV (`client_media_tier`)
        csv_bytes = (
            "domain,nama media,TIER BRI\n"
            "kompas.com,Kompas.com,Tier 1\n"
            "detik.com,Detik.com,Tier 2\n"
        ).encode("utf-8")
        r_tier = client.post(
            "/api/clients/bri/custom-tier/import",
            files={"file": ("tier_bri.csv", csv_bytes, "text/csv")},
        )
        assert r_tier.status_code == 200
        assert r_tier.json()["records_upserted"] == 2
        assert client.get("/api/clients/bri/custom-tier/status").json()["total_overrides"] == 2

        # 2b. Per-Client Persistent Takedown Registry CRUD (`takeout_registry`)
        r_td_add = client.post(
            "/api/clients/bri/takedowns",
            json={
                "urls": [
                    "https://www.portal-takedown.id/berita-negatif-1?utm_source=wa",
                    "https://m.portal-takedown.id/berita-negatif-1",
                ],
                "alasan_spam": "Takeout Permintaan Klien",
            },
        )
        assert r_td_add.status_code == 200
        assert r_td_add.json()["added"] == 1  # Deduplicated by normalized_url
        assert r_td_add.json()["count"] == 1
        td_report_id = r_td_add.json()["items"][0]["report_id"]
        assert client.get("/api/clients/bri/takedowns").json()["count"] == 1

        r_td_del = client.delete(
            "/api/clients/bri/takedowns",
            params={"report_id": td_report_id},
        )
        assert r_td_del.status_code == 200
        assert r_td_del.json()["deleted"] == 1
        assert client.get("/api/clients/bri/takedowns").json()["count"] == 0

        # 3. Create Persistent Project & Upload Excel linked to Project (skip_ai=true)
        r_prj = client.post(
            "/api/projects",
            json={
                "name": "Kasus BRI Test 19 Nov",
                "client_id": "bri",
                "report_type": "daily",
                "cutoff_datetime": "2026-11-19 15:00",
            },
        )
        assert r_prj.status_code == 201
        project_id = r_prj.json()["project"]["project_id"]

        r_up = client.post(
            "/api/upload",
            files={"files": ("newstensity.xlsx", _make_excel_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={
                "client_id": "bri",
                "project_id": project_id,
                "cutoff_datetime": "2026-11-19 15:00",
                "skip_ai": "true",
            },
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

        # 6b. POST /api/qc/{job_id}/rows (Manual Req Upload insert with auto Custom Tier lookup)
        r_add = client.post(
            f"/api/qc/{job_id}/rows",
            json={
                "page_url": "https://www.detik.com/finance/bri-req-upload",
                "title": "BRI Catat Rekor Penyaluran KUR Manual Req Upload",
                "date": "2026-11-19",
                "time": "11:30",
                "sentiment": "positive",
                "content_type": "Rilis",
                "newstrends": "BRI Salurkan KUR UMKM",
                "adhoc": {"Kluster": "UMKM & KUR", "Paid_Earned": "Earned"},
            },
        )
        assert r_add.status_code == 201
        added_row = r_add.json()["row"]
        assert added_row["TIER BRI"] == "Tier 2"  # Auto-matched detik.com from client_media_tier!
        assert added_row["Status_Req_Upload"] == "Manual Insert (Req Upload)"
        assert r_add.json()["report_payload"]["meta"]["total_clean"] == 2
        # Clean up the added row by marking it Takeout so downstream export count stays 1
        r_patch_cleanup = client.patch(
            f"/api/qc/{job_id}",
            json={"edits": [{"ID": added_row["ID"], "Status_Takeout": "Takeout", "sync_to_monthly": False}]},
        )
        assert r_patch_cleanup.status_code == 200

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

        # 9. Verify Project persisted stats & disk rehydration after simulated backend restart
        prj_after = client.get(f"/api/projects/{project_id}").json()["project"]
        assert prj_after["status"] == "completed"
        assert prj_after["latest_job_id"] == job_id
        assert prj_after["total_clean"] == 1

        jm._jobs.clear()  # Simulate backend restart
        qc_rehydrated = client.get(f"/api/qc/{job_id}").json()
        assert qc_rehydrated["job_id"] == job_id
        assert qc_rehydrated["report_payload"]["meta"]["total_clean"] == 1


async def test_qc_patch_syncs_human_qc_and_cluster_rep_to_ai_batch_cache(
    tmp_path: Path,
) -> None:
    """Verify PATCH /api/qc/{job_id} upserts edited row AND its cluster rep into ai_batch_cache
    with 'source': 'human_qc', and Pass 1 re-run hits that cache with 0 LLM calls."""
    import json
    import shutil
    from src.ai_engine.pass1_classifier import (
        PASS1_PROMPT_VERSION,
        make_cache_key,
        make_human_qc_cache_key,
        resolve_active_model_name,
        run_pass1_classification,
    )
    from src.config_loader import load_client_config
    from src.db.repositories import AIBatchCacheRepo
    from tests.test_sprint2_ai_engine import MockLLMClient

    clients_dir = tmp_path / "clients"
    shutil.copytree(Path("clients"), clients_dir)

    settings = AppSettings(
        data_dir=tmp_path / "data",
        clients_dir=clients_dir,
        sqlite_db_path=tmp_path / "data" / "qc_cache_test.db",
    )
    db = StateDatabase(settings.sqlite_db_path)
    jm = JobManager(settings=settings, db=db)
    app = create_app(settings=settings, job_manager=jm)

    # Create a completed job containing a 2-row syndicated cluster (REP-001 + MEM-002)
    job_id = "job-cluster-qc"
    job_dir = settings.data_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ID": "REP-001",
            "Title": "BRI Salurkan KUR UMKM",
            "Content_Snippet": "BRI menyalurkan KUR untuk UMKM.",
            "Date": "2026-11-19",
            "Time": "10:00",
            "Media Name": "Kompas.com",
            "Page/URL": "https://kompas.com/bri-kur-1",
            "Media Type": "online",
            "TIER BRI": "Tier 1",
            "Status_Takeout": "Keep",
            "Alasan_Spam": "",
            "Cluster_ID": "CL-9001",
            "Is_Cluster_Rep": True,
            "Has_Statement": False,
            "Sentiment": "positive",
            "Newstrends": "BRI Salurkan KUR",
            "Nama_Isu": "KUR BRI",
            "Content_Type": "Rilis",
            "Spokesperson": "0",
            "Jabatan": "0",
            "Kluster": "UMKM & KUR",
            "Paid_Earned": "Earned",
        },
        {
            "ID": "MEM-002",
            "Title": "BRI Salurkan KUR UMKM Nasional",
            "Content_Snippet": "BRI menyalurkan KUR untuk UMKM.",
            "Date": "2026-11-19",
            "Time": "10:15",
            "Media Name": "Detik.com",
            "Page/URL": "https://detik.com/bri-kur-2",
            "Media Type": "online",
            "TIER BRI": "Tier 1",
            "Status_Takeout": "Keep",
            "Alasan_Spam": "",
            "Cluster_ID": "CL-9001",
            "Is_Cluster_Rep": False,
            "Has_Statement": False,
            "Sentiment": "positive",
            "Newstrends": "BRI Salurkan KUR",
            "Nama_Isu": "KUR BRI",
            "Content_Type": "Rilis",
            "Spokesperson": "0",
            "Jabatan": "0",
            "Kluster": "UMKM & KUR",
            "Paid_Earned": "Earned",
        },
    ]
    (job_dir / "news.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    (job_dir / "statements.json").write_text("[]", encoding="utf-8")
    (job_dir / "report_payload.json").write_text(
        json.dumps({"meta": {"total_raw": 2, "total_clean": 2, "total_takeout": 0}}),
        encoding="utf-8",
    )
    (job_dir / "job_meta.json").write_text(
        json.dumps({"job_id": job_id, "client_id": "bri", "cutoff_datetime": "2026-11-19 15:00"}),
        encoding="utf-8",
    )

    with TestClient(app) as client:
        # Analyst edits non-rep cluster member MEM-002 in QC
        r_patch = client.patch(
            f"/api/qc/{job_id}",
            json={
                "edits": [
                    {
                        "ID": "MEM-002",
                        "Sentiment": "negative",
                        "Newstrends": "Evaluasi Penyaluran KUR BRI oleh Analis",
                        "Nama_Isu": "Evaluasi KUR",
                        "Kluster": "Kebijakan & Evaluasi",
                    }
                ]
            },
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["synced_ai_cache"] == 2  # Both MEM-002 and cluster rep REP-001 synced!

    # Verify both active versioned key and human_qc key exist in SQLite with source == "human_qc"
    cfg = load_client_config("bri", clients_dir=clients_dir)
    cache_repo = AIBatchCacheRepo(db)
    active_model = resolve_active_model_name(settings=settings)
    rep_vkey = make_cache_key("REP-001", cfg.config_version_hash(), PASS1_PROMPT_VERSION, active_model)
    rep_hkey = make_human_qc_cache_key("REP-001", "bri")
    cached = cache_repo.get_many([rep_vkey, rep_hkey])
    assert cached[rep_vkey]["source"] == "human_qc"
    assert cached[rep_hkey]["source"] == "human_qc"
    assert cached[rep_hkey]["sentiment"] == "negative"

    # Re-run Pass 1 with a DIFFERENT prompt version & model -> 0 LLM calls, cluster fan-out uses QC correction!
    mock_llm = MockLLMClient()
    df_rerun = pd.DataFrame(rows)
    df_out, stats = await run_pass1_classification(
        news_df=df_rerun,
        config=cfg,
        llm_client=mock_llm,
        cache_repo=cache_repo,
        prompt_version="p1_v99",
        model_name="groq:llama-3.3-70b-versatile",
    )
    assert stats.human_qc_hits == 1
    assert stats.llm_classified == 0
    assert mock_llm.pass1_call_count == 0
    indexed = df_out.set_index("ID")
    assert indexed.loc["REP-001", "Sentiment"] == "negative"
    assert indexed.loc["MEM-002", "Sentiment"] == "negative"
    assert indexed.loc["MEM-002", "Newstrends"] == "Evaluasi Penyaluran KUR BRI oleh Analis"
    assert indexed.loc["MEM-002", "Kluster"] == "Kebijakan & Evaluasi"
