# Phase 3 — Development Tracker & Implementation Log (Newstent)

> **Konteks Dokumen:** Dokumen pelacakan (*tracking*) teknis untuk seluruh pekerjaan **Phase 3: Core Development** proyek **Newstent — Analyst Workflow Automation Tool**. Seluruh *task* mengacu pada [BRD.md](../phase-1-requirements/BRD.md), [SRS.md](../phase-1-requirements/SRS.md), dan [SAD.md](../phase-2-design/SAD.md).

---

## Ringkasan Progres Sprint

| Sprint | Fokus Utama | Target Direktori | Status | Progres |
| :--- | :--- | :--- | :--- | :---: |
| **Sprint 0** | Workspace Cleanup, Scaffolding 3 Lapis, & Dependensi | Root, `src/`, `backend/`, `frontend/`, `clients/` | ✅ Selesai | 5 / 5 |
| **Sprint 1** | SQLite 4-Tabel, Ingestion `.xls`, Pre-Cleaning, Cutoff `00:00`, 3-Lapis Deduplikasi, & Media Lookup | `src/db/`, `src/cleaning/`, `tests/` | ✅ Selesai | 9 / 9 |
| **Sprint 2** | 3-Pass Cloud AI Engine, Dynamic Ad-Hoc Schema, Spokesperson Fallback, & Multi-Model Fallback | `src/ai_engine/`, `tests/` | ✅ Selesai | 7 / 7 |
| **Sprint 3** | Auto-Pivot Engine, Kurasi Kompetitor, `report_payload.json`, & Triple Deliverables (`.xlsx`, `.pptx/.pdf`, *Wording*) | `src/pivot/`, `src/generators/`, `tests/` | ✅ Selesai | 7 / 7 |
| **Sprint 4** | FastAPI REST + SSE Backend & Next.js Local Web UI (Interactive QC 4-Tab, Ad-Hoc Form, Column Picker) | `backend/`, `frontend/`, `tests/` | ✅ Selesai | 7 / 7 |

---

## Sprint 0: Workspace Cleanup & Project Foundation ✅

**Tujuan:** Membersihkan sisa konfigurasi *legacy* di luar ketentuan Phase 2, menata struktur direktori 3 lapis, menyiapkan profil klien default, serta mendefinisikan dependensi Python.

| ID | Status | Task | File / Target | Catatan / Verifikasi |
| :--- | :---: | :--- | :--- | :--- |
| **S0-01** | [x] | Audit seluruh file workspace terhadap `README.md`, `SRS.md`, dan `SAD.md` | Seluruh repo | Ditemukan variabel *crawling* API Newstensity usang di `.env` & `.env.example`, serta `.gitignore` belum mencakup Next.js & runtime `data/` |
| **S0-02** | [x] | Bersihkan & perbarui `.env.example` dan `.env` ke skema Cloud AI 3-Pass + SQLite + FastAPI/Next.js | `.env.example`, `.env` | Menghapus `NEWSTENSITY_JWT_TOKEN`, `DEFAULT_TOPIC_IDS`, `DEFAULT_DATE_FROM/TO`, `MAX_NEWS_PER_TOPIC`; diganti `DEEPSEEK_*`, `OPENROUTER_*`, `GROQ_*`, `GEMINI_*`, `SQLITE_DB_PATH`, `BACKEND_*` |
| **S0-03** | [x] | Perbarui `.gitignore` untuk Python, Next.js/Node.js, SQLite, & output runtime | `.gitignore` | Menambahkan `node_modules/`, `frontend/.next/`, `data/jobs/`, `data/uploads/`, `*.db*`, `*.xlsx/*.pptx/*.pdf` (kecuali template di `clients/`) |
| **S0-04** | [x] | Scaffolding struktur 3 lapis (`src/`, `backend/`, `frontend/`), subfolder runtime `data/`, & profil klien default BRI | `src/*`, `backend/main.py`, `frontend/.gitkeep`, `clients/bri/config.yaml`, `tests/__init__.py` | Menghapus `.gitkeep` usang di `clients/`, `src/`, `tests/`; struktur 100% sesuai `SAD.md` Bab 4 & 7 |
| **S0-05** | [x] | Buat konfigurasi proyek & daftar dependensi Python standar `SRS.md` Bab 8 | `pyproject.toml`, `requirements.txt` | Mencakup `pandas`, `python-calamine`, `xlsxwriter`, `openpyxl`, `rapidfuzz`, `openai`, `google-genai`, `pydantic`, `PyYAML`, `python-pptx`, `fastapi`, `uvicorn`, `pytest` |

---

## Sprint 1: Pre-Cleaning Engine, SQLite State DB, & Media Lookup ✅

**Tujuan:** Membangun seluruh fondasi deterministik (0 token AI) mulai dari *environment/config loader*, database SQLite 4 tabel, pembacaan `.xls with Statements`, validasi *cutoff* `00:00`, deduplikasi 3 lapis, pre-filter regex, *custom media tier* lookup, hingga cek silang `Req Upload` & `Takedown`.
**Referensi:** `SRS.md` (FR-01, FR-02, NFR-03, NFR-04), `SAD.md` (Bab 2 & 3).

| ID | Status | Task | File / Target | Kriteria Selesai (*Definition of Done*) |
| :--- | :---: | :--- | :--- | :--- |
| **S1-01** | [x] | Setup Python `.venv` & install seluruh dependensi dari `requirements.txt` | `.venv/` | `pytest`, `fastapi`, `pandas`, `python-calamine` terpasang & lolos import tanpa error |
| **S1-02** | [x] | Buat Settings & Client Config Loader (Pydantic + PyYAML) | `src/settings.py`, `src/config_loader.py` | Validasi ketat `clients/<client_id>/config.yaml` + `config_version_hash()` |
| **S1-03** | [x] | Implementasi SQLite Local State DB (4 tabel + operasi CRUD/upsert) | `src/db/database.py`, `src/db/repositories.py` | Tabel `takeout_registry`, `negative_issue_memory`, `media_master_hypestat`, `ai_batch_cache` (WAL mode + chunked upsert) |
| **S1-04** | [x] | Implementasi Excel Ingestion `.xls with Statements` (`python-calamine`) + relasi `ID` $\leftrightarrow$ `Statements` | `src/cleaning/ingestion.py` | Membaca sheet `News` & `Statements` (single/multi-file), validasi kolom wajib, dan attach *Spokesperson* Tingkat 1 |
| **S1-05** | [x] | Implementasi Split `Date`/`Time`, Filter *Cutoff* Jam Otomatis, & Flag `00:00` (`Flag_Cutoff_00`) | `src/cleaning/cutoff.py` | Memecah `Date` $\rightarrow$ `Date` & `Time`, menandai `Lewat Jam Cutoff`, dan memberi flag `CEK_CUTOFF_00:00` |
| **S1-06** | [x] | Implementasi Sanitasi *Crawling Noise* (`Content`) & Pre-Filter Regex *Spam*/Iklan | `src/cleaning/sanitizer.py` | Menghapus pola `"Baca Juga: ..."`, membuat `Content_Snippet`, dan auto-takeout `Iklan - ...` serta pola SEO KUR/PKH |
| **S1-07** | [x] | Implementasi 3-Lapis Deduplikasi (`Normalized URL`, Same-Media `Title+Content` $\ge 90\%$, Cross-Media `Cluster_ID`) | `src/cleaning/url_utils.py`, `src/cleaning/deduplicator.py` | Lapis 1 & 2 auto-takeout, judul mirip isi beda dapat `CEK_MIRIP_JUDUL`, Lapis 3 mengelompokkan `Cluster_ID` tanpa membuang media berbeda |
| **S1-08** | [x] | Implementasi Media Master Seeder/Lookup (*Custom Tier*, Hypestat, `Newswire`/`Media Bazar`) & Cek Silang `Req Upload`/`Takedown` + Sync `takeout_registry` | `src/cleaning/media_lookup.py`, `src/cleaning/url_matcher.py` | Import CSV/XLSX master media, override *Custom Tier* klien, auto-takeout `Newswire`, match `Takedown` masuk `takeout_registry`, match `Req Upload` terlaporkan |
| **S1-09** | [x] | Integrasi orkestrator `PreCleaningPipeline` & Unit Test lengkap Sprint 1 | `src/cleaning/pipeline.py`, `tests/test_sprint1_cleaning.py` | 4/4 unit test `pytest` lolos mencakup seluruh skenario & *edge case* Sprint 1 |

---

## Sprint 2: 3-Pass Cloud AI Engine & Spokesperson Fallback ✅

**Tujuan:** Membangun mesin AI 3-Pass yang cepat ($< 3$ menit untuk 800 baris), hemat token (Integer ID Mapping, Smart Snippet, Cluster representative, SQLite `ai_batch_cache`), tahan gangguan (multi-model fallback), serta mendukung kolom *ad-hoc* dinamis.
**Referensi:** `SRS.md` (Bab 2, FR-03), `SAD.md` (Bab 3B, 4, & 5).

| ID | Status | Task | File / Target | Kriteria Selesai (*Definition of Done*) |
| :--- | :---: | :--- | :--- | :--- |
| **S2-01** | [x] | Implementasi Multi-Model Async LLM Client + Retry & Fallback Chain | `src/ai_engine/client.py` | Mendukung DeepSeek (primary) $\rightarrow$ Qwen/OpenRouter $\rightarrow$ Llama/Groq $\rightarrow$ Gemini dengan *exponential backoff* & pelacakan token/biaya |
| **S2-02** | [x] | Implementasi Dynamic Pydantic Schema Builder (mendukung `adhoc_columns` dari `config.yaml`) | `src/ai_engine/schemas.py` | Skema output JSON Pass 1 otomatis menyertakan kolom *ad-hoc* dinamis tanpa ubah kode inti |
| **S2-03** | [x] | Implementasi Pass 1: Micro-Batch Classification & Extraction (25–35 baris/call, `asyncio`, Integer `idx`, `ai_batch_cache`) | `src/ai_engine/pass1_classifier.py` | Mengembalikan klasifikasi lengkap + *Cluster Fan-Out* ke anggota `Cluster_ID`, 0 kebocoran URL/hash ID, & hook progress SSE |
| **S2-04** | [x] | Implementasi Logika 3-Tingkat *Spokesperson & Jabatan* (`Statements` $\rightarrow$ `Content` $\rightarrow$ `"0"`) | `src/ai_engine/spokesperson.py` | 100% baris `Keep` terisi narasumber (Tier 1/2) atau `"0"` (0 sel *blank/null*) |
| **S2-05** | [x] | Implementasi Pass 2: Global Newstrend Normalization & `negative_issue_memory` Consistency | `src/ai_engine/pass2_normalizer.py` | Menyeragamkan variasi *Newstrend* (kalimat aktif, `max_words`, hint `"Kasus..."`/`"Tanggapan..."`), mengunci sentimen negatif berulang, & menyimpan ke SQLite |
| **S2-06** | [x] | Implementasi Pass 3: Narrative & Wording Engine dari `report_payload.json` | `src/ai_engine/pass3_narrative.py` | Menghasilkan `narrative.json` berbasis angka terverifikasi saja (URL otomatis dibersihkan sebelum dikirim ke LLM) |
| **S2-07** | [x] | Orkestrator `AIEnginePipeline` & Unit Test 3-Pass AI Engine | `src/ai_engine/pipeline.py`, `tests/test_sprint2_ai_engine.py` | 7/7 unit test total (`pytest`) lulus dengan 0 warnings |

---

## Sprint 3: Auto-Pivot Engine & Triple-Deliverable Generators ✅

**Tujuan:** Menghasilkan `report_payload.json` sebagai *Single Source of Truth* dan merakit 3 *deliverable* klien (`.xlsx`, `.pptx`/`.pdf`, dan Teks *Wording*) secara deterministik dengan 0% *mismatch* Media–URL dan 0 selisih angka.
**Referensi:** `SRS.md` (FR-04, FR-05, NFR-03), `SAD.md` (Bab 6 & 7D).

| ID | Status | Task | File / Target | Kriteria Selesai (*Definition of Done*) |
| :--- | :---: | :--- | :--- | :--- |
| **S3-01** | [x] | Implementasi Auto-Pivot Engine (Tipe Media, `Newstrends`/`Nama_Isu` vs Sentimen, `Spokesperson` Rilis, Timeline, Ad-Hoc) | `src/pivot/engine.py` | 0% selisih hitung terhadap agregasi manual `pandas`/Excel |
| **S3-02** | [x] | Implementasi Kurasi 2–3 Berita Positif & Negatif Kompetitor (POV Kompetitor + Prioritas Tier & Hypestat) | `src/pivot/competitor.py` | Pasangan `ID`, `Title`, `Media Name`, `Media Tier`, `Page/URL` diambil langsung dari DataFrame asli |
| **S3-03** | [x] | Implementasi `report_payload.json` Builder (*Single Source of Truth*) | `src/pivot/payload.py` | Menghasilkan struktur JSON sesuai `SAD.md` Bab 6A (termasuk `social_media_optional: null`) |
| **S3-04** | [x] | Implementasi Output 1 — Excel Generator (`xlsxwriter` workbook baru + `openpyxl` template injection) | `src/generators/excel_generator.py` | Sheet `News_Clean`, `Takeout_Spam`, `Statements`, & `Pivot` dengan rumus dinamis (`COUNTIF`/`COUNTIFS`/`SUM`), *Conditional Formatting*, *auto-width*, *clickable URL*, *Column Picker*, bebas `#REF!` |
| **S3-05** | [x] | Implementasi Output 2 — Report Visual Generator (`.pptx` via `python-pptx` + chart + opsi ekspor `.pdf`) | `src/generators/pptx_generator.py` | Injeksi grafik & tabel berita terverifikasi anti-mismatch ke template PPTX klien |
| **S3-06** | [x] | Implementasi Output 3 — Teks *Wording* Pengantar Email Generator (`.txt` / string) | `src/generators/wording_generator.py` | Merender *Wording* terstruktur langsung dari `report_payload.json` + `narrative.json` (100% sinkron angka dengan PPTX) |
| **S3-07** | [x] | Unit Test Auto-Pivot & Triple Deliverables | `tests/test_sprint3_deliverables.py` | Verifikasi 0 `#REF!`, 0 mismatch Media–URL, *Column Picker*, *template injection*, & sinkronisasi angka lintas Excel/PPTX/Wording (8/8 passed) |

---

## Sprint 4: Local Web UI (FastAPI + Next.js) & Interactive QC ✅

**Tujuan:** Membungkus Core Engine menjadi aplikasi web lokal yang ramah analis non-teknis dengan *real-time progress*, tabel QC mirip Excel (4 tab), editor konfigurasi & kolom *ad-hoc*, serta *Column Picker* ekspor 1-klik.
**Referensi:** `SRS.md` (FR-06), `SAD.md` (Bab 7).

| ID | Status | Task | File / Target | Kriteria Selesai (*Definition of Done*) |
| :--- | :---: | :--- | :--- | :--- |
| **S4-01** | [x] | Implementasi Job Manager & FastAPI Endpoints (`upload`, `qc`, `clients/config`, `media-master/import`, `export`) | `backend/jobs.py`, `backend/main.py`, `tests/test_sprint4_backend.py` | Seluruh 6 kelompok endpoint di `SAD.md` Bab 7B berjalan & teruji via `TestClient` (9/9 passed) |
| **S4-02** | [x] | Implementasi SSE Live Progress Streaming (`GET /api/process/{job_id}/stream`) | `backend/jobs.py`, `backend/main.py` | Mengirim event `progress`/`done`/`error` per tahap & per batch secara *real-time* ke browser |
| **S4-03** | [x] | Inisialisasi Next.js App (`frontend/`) dengan TypeScript & Tailwind CSS | `frontend/package.json`, `frontend/src/app/*`, `frontend/src/lib/api.ts` | Production build (`next build`) sukses 0 error & terhubung ke FastAPI `http://127.0.0.1:8000` |
| **S4-04** | [x] | Implementasi Halaman Upload `.xls with Statements`, Pemilihan Klien, Input *Cutoff*, Opsional `Req Upload`/`Takedown`, & Live Progress Bar (SSE) | `frontend/src/components/UploadPanel.tsx` | Upload *drag-and-drop* memicu job & menampilkan progres SSE langsung |
| **S4-05** | [x] | Implementasi Interactive Spreadsheet QC Table (4 Tab Filter: `00:00`, `Takeout & Alasan Spam`, `Rilis & Spokesperson 0`, `Mirip Judul`) | `frontend/src/components/QCTablePanel.tsx` | Analis dapat *inline edit* & simpan revisi yang langsung *sync* ke SQLite `takeout_registry` & `report_payload.json` |
| **S4-06** | [x] | Implementasi Form Config Klien + Kolom *Ad-Hoc* & Import Media Master UI | `frontend/src/components/SettingsPanel.tsx` | Analis bisa tambah/ubah `adhoc_columns` & unggah file master media tanpa edit YAML manual |
| **S4-07** | [x] | Implementasi Client Export *Column Picker* & Panel Unduh/Salin 3 Output Utama (`.xlsx`, `.pptx/.pdf`, Copy *Wording*) | `frontend/src/components/ExportPanel.tsx`, `frontend/src/app/page.tsx` | Analis dapat memilih kolom Excel klien dan mengunduh/menyalin ketiga output dalam 1 klik |

---

## Changelog / Log Implementasi

### 2026-11-26 — Peningkatan Anti-Stale `ai_batch_cache`, Isolasi `takeout_registry`, & Insert Berita Manual (Req Upload)
- **Ringkasan:** Mencegah *stale cache* saat prompt/model berubah, menyinkronkan koreksi manual QC ke `ai_batch_cache`, memperbaiki isolasi per klien pada `takeout_registry`, serta memindahkan fitur *Req Upload* ke tombol `+ Tambah Berita` di Tabel QC.
- **Perubahan Utama:**
  - `src/ai_engine/pass1_classifier.py` & `src/ai_engine/pipeline.py`: Menambahkan `PASS1_PROMPT_VERSION = "p1_v1"`, `resolve_active_model_name()`, pembaruan `_make_cache_key()` (`report_id + config_hash + prompt_version + model_name`), serta prioritas lookup `human_qc` (`make_human_qc_cache_key(report_id, client_id)`) agar perubahan prompt/model hanya mengulang klasifikasi AI biasa tanpa menimpa koreksi analis.
  - `backend/jobs.py` (`apply_qc_edits` via `PATCH /api/qc/{job_id}`): Upsert otomatis seluruh koreksi field AI (`Sentiment`, `Newstrends`, `Nama_Isu`, `Content_Type`, `Status_Takeout`, `Alasan_Spam`, `Spokesperson`, `Jabatan`, & `adhoc`) ke `ai_batch_cache` dengan `"source": "human_qc"`, sekaligus menyinkronkan `ID` perwakilan klaster (`Is_Cluster_Rep == True`) bila baris termasuk `Cluster_ID`.
  - `src/db/database.py` & `src/db/repositories.py`: Memperbarui `takeout_registry` ke composite `PRIMARY KEY (client_id, report_id)` + migrasi otomatis tanpa hilang data, sehingga artikel dengan `ID` sama pada klien berbeda terisolasi penuh.
  - `backend/jobs.py`, `backend/main.py`, `frontend/src/components/QCTablePanel.tsx`, & `UploadPanel.tsx`: Menambahkan endpoint `POST /api/qc/{job_id}/rows` & modal **`+ Tambah Berita (Req Upload)`** di Tabel QC (auto-lookup `client_media_tier` dari domain URL), serta menyederhanakan form Upload Project.
  - `frontend/src/components/NewProjectModal.tsx`: Menambahkan indikator wajib (`*`), atribut `required`, dan placeholder dropdown `Pilih Klien...` / `Pilih Tipe...`.
  - `src/pivot/competitor.py`: Perbaikan fallback `Oplah/Daily Visitor` jika kolom tidak tersedia di DataFrame.
  - `tests/`: Menambahkan unit test `test_takeout_registry_per_client_isolation_and_migration`, `test_ai_batch_cache_prompt_model_invalidation_and_human_qc_precedence`, `test_qc_patch_syncs_human_qc_and_cluster_rep_to_ai_batch_cache`, & test `POST /api/qc/{job_id}/rows` — total **14/14 passed** & `tsc --noEmit` **0 error**.

### 2026-11-25 — Penyelarasan Media Tier, Takedown Registry, Sentiment/Newstrend Brief, & Excel-Style QC Filter
- **Ringkasan:** Penyelarasan arsitektur & UX Phase 4 sebelum QA penuh: per-client Custom Media Tier override, manajemen Takedown Registry di Konfigurasi Klien, panduan Sentiment & Newstrend Brief, serta Sorting & AutoFilter ala Excel di Tabel QC.
- **Perubahan Utama:**
  - **Custom Media Tier Per Klien (`client_media_tier`):** Menambahkan tabel SQLite `client_media_tier` (`src/db/database.py`, `src/db/repositories.py`), mekanisme lookup Prioritas 1 (override klien) $\rightarrow$ Prioritas 2 (fallback `Media Tier` bawaan raw `.xls`) + `DEFAULT_NEWSWIRE_DOMAINS` di backend (`src/cleaning/media_lookup.py`), endpoint `GET/POST /api/clients/{client_id}/custom-tier/*`, serta mengganti menu Master Media global di `SettingsPanel.tsx` menjadi kartu opsional **Import Custom Media Tier** (BNI ter-seed 13.022 entri unik).
  - **Sentiment Brief (POV Klien) & Global Newstrend Brief ("All Client"):** Dukungan konfigurasi brief sentimen per klien (termasuk JSON importer & aturan BNI di `clients/bni/config.yaml`) serta panduan pembuatan & clustering Newstrend di Pass 1 & Pass 2 (`src/config_loader.py`, `pass1_classifier.py`, `pass2_normalizer.py`, `SettingsPanel.tsx`).
  - **Takedown Registry di Konfigurasi Klien & Collapsible Upload URLs:** Endpoint `GET/POST/DELETE /api/clients/{client_id}/takedowns`, kartu manajemen Daftar URL Takedown Klien di `SettingsPanel.tsx`, dan lipatan opsional Req Upload & Takedown Dadakan (dengan badge jumlah takedown aktif) di `UploadPanel.tsx`.
  - **Excel-Style Sorting & AutoFilter di Tabel QC:** Klik header untuk sorting (terbaru/terlama & A–Z/Z–A), tombol cepat **Terbaru ↓ / Terlama ↑**, baris AutoFilter dropdown/teks per kolom (termasuk kolom Ad-Hoc), dan tombol **Reset Filter & Sort** di `QCTablePanel.tsx`.

### 2026-11-24 — Iterasi UI/UX: Project-Centric Workspace & Smart PPTX Updater
- **Ringkasan:** Mengubah arsitektur Web UI menjadi **Project-Centric (1 Kasus = 1 Project persisten)** bergaya *light SaaS* (tanpa panel chat kanan) + fitur *Smart PPTX Template Element Auto-Recognition*.
- **Perubahan Utama:**
  - `src/db/database.py`, `src/db/repositories.py`, `backend/jobs.py`, & `backend/main.py`: Tabel SQLite `projects`, endpoint `GET/POST/DELETE /api/projects`, relasi `project_id` pada `/api/upload`, serta *disk rehydration* agar project lama tetap bisa dibuka & di-QC meski backend di-restart.
  - `frontend/`: Redesign penuh bergaya *AutomiQ* (Top Bar, Breadcrumb Project Switcher, Far-Left Icon Rail, Left Project Panel + `NewProjectModal`, dan kanvas *dot-grid* full-width tanpa panel chat kanan).
  - `src/generators/pptx_template_updater.py`: Pengenalan & pembaruan otomatis grafik/teks *in-place* pada template `.pptx` klien (termasuk melepas tautan eksternal Google Sheets).

### 2026-11-24 — Sprint 4 Selesai (Phase 3 Core Development Complete ✅)
- **Ringkasan:** Menyelesaikan Layer 2 (FastAPI REST + SSE Backend) dan Layer 3 (Next.js Local Web UI dengan 4-Tab Interactive Spreadsheet QC, Form Kolom Ad-Hoc, Manajemen Multi-Klien, Import Media Master, & Client Export Column Picker).
- **Perubahan Utama:**
  - `backend/jobs.py` & `backend/main.py`: Job Manager asinkron + endpoint REST/SSE (`/api/upload`, `/api/process/{job_id}/stream`, `/api/qc/{job_id}`, `/api/clients` `GET`/`POST`, `/api/clients/{client_id}/config`, `/api/media-master/import`, `/api/export/{job_id}`).
  - `clients/bni/config.yaml`: Menambahkan profil klien default kedua (`BNI` dengan `TIER BNI` & *wondr by BNI*).
  - `tests/test_sprint4_backend.py`: Integration test end-to-end FastAPI (`TestClient`, termasuk pembuatan profil klien baru) — total **9/9 passed, 0 warnings**.
  - `frontend/`: Aplikasi Next.js 15 + TypeScript + Tailwind CSS (`UploadPanel.tsx`, `QCTablePanel.tsx`, `ExportPanel.tsx`, `SettingsPanel.tsx` dengan form *"+ Buat Profil Klien Baru"*, `page.tsx`, `api.ts`).
  - Verifikasi `npm run build --prefix frontend`: **Compiled & Type-Checked 0 errors**.

### 2026-11-24 — Sprint 3 Selesai
- **Ringkasan:** Menyelesaikan Auto-Pivot Engine, Kurasi Kompetitor, `report_payload.json` (*Single Source of Truth*), dan seluruh *Triple-Deliverable Generators* (`.xlsx`, `.pptx`/`.pdf`, & Teks *Wording*).
- **Perubahan Utama:**
  - `src/pivot/engine.py`, `competitor.py`, & `payload.py`: Agregasi Pivot deterministik (Tipe Media, Custom Tier, `Newstrends`/`Nama_Isu`, `Spokesperson` Rilis termasuk `"0"`, Timeline, Ad-Hoc) + kurasi 2–3 berita kompetitor prioritas Tier & Hypestat.
  - `src/generators/excel_generator.py`: Output 1 via `xlsxwriter` (4 sheet, rumus dinamis `COUNTIF`/`COUNTIFS`/`SUM`, *Conditional Formatting*, *Native Chart*, *Column Picker*) + *template injection* via `openpyxl`.
  - `src/generators/pptx_generator.py`: Output 2 via `python-pptx` + `matplotlib` chart, tabel berita kompetitor anti-mismatch dengan *clickable hyperlink*, plus helper ekspor `.pdf` via LibreOffice.
  - `src/generators/wording_generator.py`: Output 3 Teks *Wording* 100% sinkron angka dengan PPTX (blok Sosmed opsional).
  - Verifikasi unit test (`tests/test_sprint3_deliverables.py` + Sprint 1–2): **8/8 passed, 0 warnings**.

### 2026-11-24 — Sprint 2 Selesai
- **Ringkasan:** Menyelesaikan seluruh 3-Pass Cloud AI Engine modular beserta *multi-model fallback*, *dynamic ad-hoc schema*, *SQLite batch cache*, *3-tier spokesperson resolver*, dan *negative issue memory*.
- **Perubahan Utama:**
  - `src/ai_engine/client.py`: Async `MultiModelLLMClient` (DeepSeek $\rightarrow$ Qwen/OpenRouter $\rightarrow$ Llama/Groq $\rightarrow$ Gemini) dengan *exponential backoff* & estimator biaya Off-Peak/Peak.
  - `src/ai_engine/schemas.py`: `build_pass1_batch_schema()` dinamis dari `config.yaml` (`adhoc_columns`), `Pass2NormalizationResponse`, dan `Pass3NarrativeOutput`.
  - `src/ai_engine/pass1_classifier.py`: Micro-batching `asyncio`, Integer ID Mapping (0 URL/hash ID dikirim ke LLM), `ai_batch_cache` SQLite, *Cluster Fan-Out*, dan *progress callback* untuk SSE.
  - `src/ai_engine/spokesperson.py`: 3-Tier Fallback (`Statements` $\rightarrow$ `Content` $\rightarrow$ `"0"`).
  - `src/ai_engine/pass2_normalizer.py`: Standardisasi *Newstrend* global + penguncian sentimen negatif melalui `negative_issue_memory`.
  - `src/ai_engine/pass3_narrative.py` & `src/ai_engine/pipeline.py`: Narrative engine terverifikasi + orkestrator `AIEnginePipeline`.
  - Verifikasi unit test (`tests/test_sprint2_ai_engine.py` + Sprint 1): **7/7 passed, 0 warnings**.

### 2026-11-24 — Sprint 1 Selesai
- **Ringkasan:** Menyelesaikan seluruh fondasi deterministik (0 token AI) untuk ingestion, pre-cleaning, SQLite 4 tabel, media lookup, dan sinkronisasi takeout.
- **Perubahan Utama:**
  - Setup `.venv` Python 3.11.9 dan instalasi seluruh dependensi `requirements.txt`.
  - Menambahkan `src/settings.py` dan `src/config_loader.py` (validasi Pydantic `config.yaml` + `config_version_hash()`).
  - Membangun SQLite State DB 4 tabel (`src/db/database.py` & `src/db/repositories.py`) dengan WAL mode dan *chunked upsert* untuk ribuan domain media.
  - Membangun paket `src/cleaning/`: `url_utils.py`, `ingestion.py` (`python-calamine` + Tier-1 Spokesperson), `cutoff.py` (split `Date/Time` + flag `00:00`), `sanitizer.py` (*noise stripping* + regex *spam* pre-filter), `deduplicator.py` (3-lapis + `Cluster_ID`), `media_lookup.py` (*Custom Tier* + Hypestat + auto-takeout `Newswire`), `url_matcher.py` (`Req Upload`/`Takedown` + sync `takeout_registry`), dan orkestrator `pipeline.py`.
  - Verifikasi unit test (`tests/test_sprint1_cleaning.py`): **4/4 passed, 0 warnings**.

### 2026-11-24 — Sprint 0 Selesai
- **Ringkasan:** Memulai Phase 3 dengan pembersihan file di luar ketentuan Phase 2 dan penataan fondasi repositori.
- **Perubahan Utama:**
  - Memperbarui `.env.example` & `.env` (menghapus variabel *crawling* API Newstensity usang, mengganti ke konfigurasi 3-Pass Cloud AI + SQLite + FastAPI/Next.js).
  - Memperbarui `.gitignore` untuk Python, Next.js/Node.js, SQLite, dan direktori runtime `data/`.
  - Menata struktur 3 lapis: `src/` (`db/`, `cleaning/`, `ai_engine/`, `pivot/`, `generators/`), `backend/main.py`, `frontend/`, `clients/bri/config.yaml`, `tests/`, dan subfolder runtime `data/`.
  - Menambahkan `pyproject.toml` & `requirements.txt` sesuai *tech stack* `SRS.md` Bab 8.
  - Membuat dokumen pelacakan ini (`docs/phase-3-development/DEV_TRACKER.md`).
