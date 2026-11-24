"""Comprehensive unit tests for Sprint 1: Settings, Config Loader, SQLite 4-Tables, & Pre-Cleaning Pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.cleaning.media_lookup import import_media_master_file
from src.cleaning.pipeline import PreCleaningPipeline
from src.cleaning.url_utils import extract_domain, normalize_url
from src.config_loader import load_client_config, save_client_config
from src.db.database import StateDatabase
from src.db.repositories import (
    AIBatchCacheRepo,
    MediaMasterRecord,
    MediaMasterRepo,
    NegativeIssueMemoryRepo,
    NegativeIssueRecord,
    TakeoutRecord,
    TakeoutRegistryRepo,
)


def _create_sample_excel(path: Path) -> Path:
    """Create a realistic Newstensity `.xlsx` export with `News` and `Statements` sheets."""
    syndicated_body = (
        "PT Bank Rakyat Indonesia (Persero) Tbk terus memperkuat penyaluran Kredit Usaha Rakyat "
        "bagi pelaku usaha mikro kecil dan menengah di seluruh Indonesia sepanjang kuartal keempat "
        "tahun ini demi mendorong pertumbuhan ekonomi kerakyatan nasional secara berkelanjutan. "
        "Baca Juga: Promo Diskon Belanja Akhir Tahun."
    )

    news_rows = [
        # 1. Valid Tier 1 article with Statement (will be cluster rep for syndicated release)
        {
            "ID": "NEWS-001",
            "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM Naik Kelas",
            "Content": syndicated_body,
            "Date": "2026-11-19 10:15",
            "Media Name": "Kompas.com",
            "Page/URL": "https://www.kompas.com/ekonomi/bri-kur-umkm?utm_source=google&page=1",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRI KUR",
        },
        # 2. Exact Normalized URL Duplicate of NEWS-001 (m. subdomain + different utm)
        {
            "ID": "NEWS-002",
            "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM Naik Kelas",
            "Content": syndicated_body,
            "Date": "2026-11-19 10:20",
            "Media Name": "Kompas.com",
            "Page/URL": "http://m.kompas.com/ekonomi/bri-kur-umkm/?utm_medium=social",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRI KUR",
        },
        # 3. Cross-media syndicated release (different media: BeritaSatu -> MUST KEEP & join same Cluster_ID)
        {
            "ID": "NEWS-003",
            "Title": "BRI Perkuat Penyaluran KUR untuk UMKM Nasional",
            "Content": syndicated_body,
            "Date": "2026-11-19 11:00",
            "Media Name": "BeritaSatu.com",
            "Page/URL": "https://www.beritasatu.com/ekonomi/bri-perkuat-kur",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRI KUR",
        },
        # 4. Same-media near-duplicate (Title >= 90% AND Content >= 90% -> Takeout)
        {
            "ID": "NEWS-004",
            "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM Naik Kelas!",
            "Content": syndicated_body,
            "Date": "2026-11-19 11:30",
            "Media Name": "Kompas.com",
            "Page/URL": "https://www.kompas.com/ekonomi/bri-kur-umkm-republish",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRI KUR",
        },
        # 5. Same-media similar title BUT different content (Update angka -> MUST KEEP + Flag_Near_Dup)
        {
            "ID": "NEWS-005",
            "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM Naik Kelas",
            "Content": (
                "Berbeda dengan laporan sebelumnya, kali ini BRI merinci realisasi penyaluran "
                "pembiayaan khusus sektor pertanian dan perikanan di wilayah timur Indonesia yang "
                "tumbuh 24 persen secara tahunan dengan rasio kredit bermasalah terjaga rendah."
            ),
            "Date": "2026-11-19 12:00",
            "Media Name": "Kompas.com",
            "Page/URL": "https://www.kompas.com/ekonomi/bri-kur-bagian-2",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRI KUR",
        },
        # 6. Default 00:00 time (MUST KEEP + Flag_Cutoff_00 = CEK_CUTOFF_00:00)
        {
            "ID": "NEWS-006",
            "Title": "Layanan Digital BRImo Catat Rekor Transaksi Harian",
            "Content": "Pengguna aktif aplikasi BRImo terus meningkat pesat sepanjang November 2026.",
            "Date": "2026-11-19 00:00",
            "Media Name": "Detik.com",
            "Page/URL": "https://finance.detik.com/moneter/brimo-rekor",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "BRImo",
        },
        # 7. After cutoff 15:00 WIB -> Takeout ('Lewat Jam Cutoff')
        {
            "ID": "NEWS-007",
            "Title": "BRI Gelar Pelatihan Ekspor UMKM di Surabaya",
            "Content": "Pelatihan ekspor diikuti ratusan pengusaha binaan BRI wilayah Jawa Timur.",
            "Date": "2026-11-19 16:30",
            "Media Name": "Bisnis.com",
            "Page/URL": "https://ekonomi.bisnis.com/bri-ekspor-surabaya",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 1",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "UMKM Ekspor",
        },
        # 8. Regex Pre-Filter Spam (Iklan media cetak) -> Takeout
        {
            "ID": "NEWS-008",
            "Title": "Iklan - PENGUMUMAN LELANG ASET BRI CABANG BANDUNG",
            "Content": "Pengumuman lelang eksekusi hak tanggungan berdasarkan ketentuan perundang-undangan.",
            "Date": "2026-11-19 08:00",
            "Media Name": "Pikiran Rakyat",
            "Page/URL": "https://www.pikiran-rakyat.com/iklan/lelang-bri",
            "Media Type": "print",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 2",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "neutral",
            "Newstrends": "Iklan",
        },
        # 9. Regex Pre-Filter SEO KUR -> Takeout
        {
            "ID": "NEWS-009",
            "Title": "Cek Tabel Angsuran KUR BRI November 2026 Plafon 50 Juta",
            "Content": "Berikut simulasi cicilan per bulan untuk pinjaman modal usaha.",
            "Date": "2026-11-19 09:00",
            "Media Name": "Tribunnews.com",
            "Page/URL": "https://www.tribunnews.com/bisnis/tabel-angsuran-kur-bri",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 2",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "neutral",
            "Newstrends": "KUR",
        },
        # 10. Newswire domain (via media_master_hypestat) -> Auto-Takeout Newswire
        {
            "ID": "NEWS-010",
            "Title": "PR Newswire: BRI Announces Green Financing Milestone",
            "Content": "Press release distributed via global newswire service.",
            "Date": "2026-11-19 10:00",
            "Media Name": "PR Newswire",
            "Page/URL": "https://www.prnewswire.com/news-releases/bri-green",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 3",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "positive",
            "Newstrends": "Green Financing",
        },
        # 11. Client Takedown URL -> Takeout + persisted to SQLite takeout_registry
        {
            "ID": "NEWS-011",
            "Title": "Isu Sensitif Cabang Daerah",
            "Content": "Berita sensitif yang sudah dimoderasi/takedown oleh klien.",
            "Date": "2026-11-19 13:00",
            "Media Name": "PortalLokal.id",
            "Page/URL": "https://portallokal.id/kasus-cabang-daerah?utm_source=wa",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 3",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "negative",
            "Newstrends": "Kasus",
        },
        # 12. Historical Takeout from previous Daily Report (Monthly Sync test)
        {
            "ID": "NEWS-012",
            "Title": "Berita Negatif Lama yang Sudah Di-Takeout Kemarin",
            "Content": "Konten berita negatif lama.",
            "Date": "2026-11-18 14:00",
            "Media Name": "PortalLama.id",
            "Page/URL": "https://portallama.id/berita-negatif-lama",
            "Media Type": "online",
            "Media Type Detail": "Organik",
            "Media Tier": "Tier 3",
            "Oplah/Daily Visitor": 0,
            "Sentiment": "negative",
            "Newstrends": "Kasus Lama",
        },
    ]

    statements_rows = [
        {
            "Report id": "NEWS-001",
            "Name": "Sunarso",
            "Position": "Direktur Utama BRI",
            "Sentiment": "positive",
            "Quote": "BRI berkomitmen mendorong UMKM naik kelas melalui penyaluran KUR.",
        },
        {
            "Report id": "NEWS-011",
            "Name": "Oknum",
            "Position": "Staf",
            "Sentiment": "negative",
            "Quote": "Kutipan dari berita yang di-takeout.",
        },
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(news_rows).to_excel(writer, sheet_name="News", index=False)
        pd.DataFrame(statements_rows).to_excel(writer, sheet_name="Statements", index=False)
    return path


def test_url_normalization_and_domain_extraction() -> None:
    u1 = "https://www.Kompas.com/ekonomi/read/123/?utm_source=fb&page=2#section"
    u2 = "http://m.kompas.com/ekonomi/read/123"
    assert normalize_url(u1) == normalize_url(u2)
    assert extract_domain(u1) == "kompas.com"
    assert extract_domain("amp.beritasatu.com/ekonomi/abc") == "beritasatu.com"


def test_client_config_loader_and_roundtrip(tmp_path: Path) -> None:
    cfg = load_client_config("bri", clients_dir=Path("clients"))
    assert cfg.client_id == "bri"
    assert cfg.media_and_spokesperson.custom_tier.excel_column_name == "TIER BRI"
    assert len(cfg.adhoc_columns) == 2
    assert len(cfg.config_version_hash()) == 16

    saved_path = save_client_config(cfg, clients_dir=tmp_path)
    assert saved_path.exists()
    reloaded = load_client_config("bri", clients_dir=tmp_path)
    assert reloaded.config_version_hash() == cfg.config_version_hash()


def test_sqlite_four_tables_repositories(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / "test_state.db")

    # 1. takeout_registry
    takeout_repo = TakeoutRegistryRepo(db)
    takeout_repo.upsert_many(
        [
            TakeoutRecord(
                report_id="R1",
                client_id="bri",
                page_url="https://example.com/bad",
                normalized_url="example.com/bad",
                alasan_spam="Takeout Negatif Sensitif",
                is_sensitive_negative=True,
            )
        ]
    )
    by_id, by_url = takeout_repo.get_by_client("bri")
    assert "R1" in by_id
    assert "example.com/bad" in by_url
    assert by_id["R1"].is_sensitive_negative is True

    # 2. negative_issue_memory
    neg_repo = NegativeIssueMemoryRepo(db)
    neg_repo.upsert_many(
        [
            NegativeIssueRecord(
                issue_hash="H1",
                client_id="bri",
                nama_isu="Dugaan Fraud Cabang X",
                canonical_newstrend="Kasus Dugaan Fraud di Cabang X",
            )
        ]
    )
    issues = neg_repo.list_by_client("bri")
    assert len(issues) == 1
    assert issues[0].locked_sentiment == "negative"

    # 3. media_master_hypestat
    media_repo = MediaMasterRepo(db)
    media_repo.upsert_many(
        [
            MediaMasterRecord(
                domain="beritasatu.com",
                media_name="BeritaSatu",
                tier_bino="Tier 1",
                client_custom_tiers={"bni": "Tier 2"},
                media_type_detail="Organik",
                hypestat_daily_visitor=250000,
            )
        ]
    )
    # Merge another client custom tier without overwriting existing 'bni' tier
    media_repo.upsert_many(
        [
            MediaMasterRecord(
                domain="beritasatu.com",
                client_custom_tiers={"bri": "Tier 2"},
            )
        ],
        merge_custom_tiers=True,
    )
    media_map = media_repo.get_all_map()
    assert media_map["beritasatu.com"].client_custom_tiers == {"bni": "Tier 2", "bri": "Tier 2"}
    assert media_map["beritasatu.com"].hypestat_daily_visitor == 250000

    # 4. ai_batch_cache
    cache_repo = AIBatchCacheRepo(db)
    cache_repo.set_many({"k1": {"sentiment": "positive", "nama_isu": "KUR"}})
    cached = cache_repo.get_many(["k1", "missing"])
    assert "k1" in cached and cached["k1"]["sentiment"] == "positive"
    assert "missing" not in cached


def test_full_sprint1_precleaning_pipeline(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / "pipeline_state.db")

    # Seed media_master_hypestat via CSV import
    media_csv = tmp_path / "media_master.csv"
    pd.DataFrame(
        [
            {
                "domain": "https://www.beritasatu.com",
                "media_name": "BeritaSatu.com",
                "tier_bino": "Tier 1",
                "TIER BRI": "Tier 2",
                "media_type_detail": "Organik",
                "hypestat_daily_visitor": 300000,
            },
            {
                "domain": "prnewswire.com",
                "media_name": "PR Newswire",
                "tier_bino": "Tier 3",
                "TIER BRI": "Tier 3",
                "media_type_detail": "Newswire",
                "hypestat_daily_visitor": 50000,
            },
        ]
    ).to_csv(media_csv, index=False)
    imported_count = import_media_master_file(
        media_csv, MediaMasterRepo(db), custom_tier_client_key="bri"
    )
    assert imported_count == 2

    # Seed 1 historical takeout record (simulating Daily -> Monthly sync)
    TakeoutRegistryRepo(db).upsert_many(
        [
            TakeoutRecord(
                report_id="NEWS-012",
                client_id="bri",
                page_url="https://portallama.id/berita-negatif-lama",
                normalized_url="portallama.id/berita-negatif-lama",
                alasan_spam="Takeout Negatif Sensitif (Daily)",
                is_sensitive_negative=True,
            )
        ]
    )

    excel_path = _create_sample_excel(tmp_path / "sample_newstensity.xlsx")
    pipeline = PreCleaningPipeline(db=db, clients_dir=Path("clients"))

    result = pipeline.run(
        excel_paths=excel_path,
        client_id="bri",
        cutoff_datetime="2026-11-19 15:00",
        req_upload_urls=[
            "https://www.beritasatu.com/ekonomi/bri-perkuat-kur?utm_campaign=pr",
            "https://media-belum-tercrawl.com/rilis-bri",
        ],
        takedown_urls=["https://portallokal.id/kasus-cabang-daerah"],
    )

    df = result.news_df.set_index("ID")

    # Verify Keep vs Takeout per scenario
    assert df.loc["NEWS-001", "Status_Takeout"] == "Keep"
    assert df.loc["NEWS-001", "Spokesperson"] == "Sunarso"
    assert df.loc["NEWS-001", "Jabatan"] == "Direktur Utama BRI"
    assert bool(df.loc["NEWS-001", "Has_Statement"]) is True
    assert "Baca Juga" not in df.loc["NEWS-001", "Content_Clean"]

    # Layer 1: Exact Normalized URL Duplicate
    assert df.loc["NEWS-002", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-002", "Alasan_Spam"] == "Duplikat URL Persis"

    # Layer 3: Cross-Media Syndicated Release -> KEPT, same Cluster_ID, Custom Tier applied, Req Upload matched
    assert df.loc["NEWS-003", "Status_Takeout"] == "Keep"
    assert df.loc["NEWS-003", "Cluster_ID"] == df.loc["NEWS-001", "Cluster_ID"]
    assert bool(df.loc["NEWS-001", "Is_Cluster_Rep"]) is True
    assert bool(df.loc["NEWS-003", "Is_Cluster_Rep"]) is False
    assert df.loc["NEWS-003", "TIER BRI"] == "Tier 2"  # Custom Tier overrides Bino Tier 1!
    assert df.loc["NEWS-003", "Oplah/Daily Visitor"] == 300000
    assert df.loc["NEWS-003", "Status_Req_Upload"] == "Matched (Req Upload)"

    # Layer 2: Same-media exact near-duplicate (Title >= 90% AND Content >= 90%)
    assert df.loc["NEWS-004", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-004", "Alasan_Spam"] == "Duplikat Media Sama"

    # Layer 2: Same-media similar title BUT different content -> KEPT + Flag_Near_Dup
    assert df.loc["NEWS-005", "Status_Takeout"] == "Keep"
    assert df.loc["NEWS-005", "Flag_Near_Dup"] == "CEK_MIRIP_JUDUL"

    # Cutoff 00:00 Guard -> KEPT + Flag_Cutoff_00
    assert df.loc["NEWS-006", "Status_Takeout"] == "Keep"
    assert df.loc["NEWS-006", "Date"] == "2026-11-19"
    assert df.loc["NEWS-006", "Time"] == "00:00"
    assert df.loc["NEWS-006", "Flag_Cutoff_00"] == "CEK_CUTOFF_00:00"

    # After Cutoff 15:00 -> Takeout
    assert df.loc["NEWS-007", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-007", "Alasan_Spam"] == "Lewat Jam Cutoff"

    # Regex Pre-Filters
    assert df.loc["NEWS-008", "Status_Takeout"] == "Takeout"
    assert "Iklan" in df.loc["NEWS-008", "Alasan_Spam"]
    assert df.loc["NEWS-009", "Status_Takeout"] == "Takeout"
    assert "SEO" in df.loc["NEWS-009", "Alasan_Spam"]

    # Auto-Takeout Newswire
    assert df.loc["NEWS-010", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-010", "Alasan_Spam"] == "Takeout - Newswire"

    # Client Takedown -> Takeout + persisted to SQLite takeout_registry
    assert df.loc["NEWS-011", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-011", "Alasan_Spam"] == "Takeout - Daftar Takedown Klien"
    by_id, _ = TakeoutRegistryRepo(db).get_by_client("bri")
    assert "NEWS-011" in by_id

    # Historical Takeout Sync (Daily -> Monthly)
    assert df.loc["NEWS-012", "Status_Takeout"] == "Takeout"
    assert df.loc["NEWS-012", "Alasan_Spam"] == "Takeout Negatif Sensitif (Daily)"

    # Statements sheet synced (NEWS-011 statement removed, NEWS-001 statement kept)
    assert list(result.statements_df["Report id"]) == ["NEWS-001"]

    # Req Upload summary
    assert result.url_match_summary.req_upload_total == 2
    assert result.url_match_summary.req_upload_matched == 1
    assert result.url_match_summary.req_upload_unmatched_urls == [
        "https://media-belum-tercrawl.com/rilis-bri"
    ]

    # Overall Stats
    assert result.stats.total_raw == 12
    assert result.stats.total_keep == 4  # NEWS-001, NEWS-003, NEWS-005, NEWS-006
    assert result.stats.total_takeout == 8
    assert result.stats.flagged_cutoff_00 == 1
    assert result.stats.flagged_near_dup == 1
    assert result.stats.ai_cluster_reps == 3  # NEWS-001, NEWS-005, NEWS-006 (NEWS-003 shares cluster with NEWS-001)
    assert result.stats.tier1_spokesperson_filled == 1
