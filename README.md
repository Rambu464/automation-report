# Newstent — Analyst Workflow Automation Tool

Alat bantu otomasi alur kerja analis (*Analyst Workflow Automation Tool*) untuk pengolahan data *media monitoring* **Newstensity (Binokular)**—mulai dari pembersihan *raw data* (`.xls with Statements`), penandaan *Takeout* & *Alasan Spam*, *lookup Custom Media Tier* klien, koreksi sentimen & standardisasi `Newstrends` berbasis Cloud AI, ekstraksi 3-tingkat *Spokesperson*, pembuatan *Pivot Table* & kurasi berita kompetitor, hingga menghasilkan **3 output utama klien: File Excel *Raw Data Cleaned* (`.xlsx`), Report Visual (`.pptx` / `.pdf`), dan Teks *Wording*** melalui **Local Web UI (Next.js + FastAPI)**.

---

## Struktur Direktori Proyek

```text
Newstensity/
├── docs/
│   ├── phase-1-requirements/
│   │   ├── BRD.md                     # Business Requirements Document (Non-Teknis / Operasional)
│   │   └── SRS.md                     # Software Requirements Specification (Teknis Developer & AI)
│   └── phase-2-design/
│       └── SAD.md                     # Software Architecture Document (Desain Sistem, DB, & Web UI)
├── clients/                           # Folder per klien: config.yaml + template PPT/Excel
├── data/                              # Runtime data: raw input, SQLite state DB, & output (ignored Git)
├── src/                               # Layer 1: Core Engine Python modular (Phase 3)
├── backend/                           # Layer 2: FastAPI local server & SSE progress (Phase 3)
├── frontend/                          # Layer 3: Next.js local Web UI & QC Table (Phase 3)
├── tests/                             # Unit test & dataset QA (Phase 4)
├── .env                               # Credentials & API keys lokal (tidak masuk Git)
├── .env.example                       # Contoh variabel environment
├── .gitignore                         # Aturan pengecualian Git standar
└── README.md                          # Ringkasan & panduan navigasi proyek
```

---

## Roadmap SDLC

| Fase | Status | Fokus Utama | Dokumen / Lokasi |
| :--- | :--- | :--- | :--- |
| **Phase 1: Planning & Requirements** | ✅ Selesai | Analisis kebutuhan bisnis (*BRD*) & spesifikasi teknis sistem (*SRS*: FR/NFR, Cloud AI, & estimasi biaya). | [`docs/phase-1-requirements/`](./docs/phase-1-requirements/) |
| **Phase 2: System & Architecture Design** | ✅ Selesai | Desain arsitektur (*SAD*), skema SQLite (4 tabel), 3-Pass AI Engine, `config.yaml` *ad-hoc*, & **Next.js + FastAPI**. | [`docs/phase-2-design/SAD.md`](./docs/phase-2-design/SAD.md) |
| **Phase 3: Core Development** | 🔄 Siap Dimulai | Implementasi 4 Sprint: `Pre-Cleaning`, `AI Engine`, `Auto-Pivot & Triple Deliverables`, & `Local Web UI`. | `src/`, `backend/`, `frontend/` |
| **Phase 4: Testing & Quality Control** | ⏳ Mendatang | Uji akurasi *Takeout/Spokesperson/Newstrend*, validasi 0 selisih Pivot & 0 *mismatch* Media-URL. | `tests/` |
| **Phase 5: Local Deployment & Handover** | ⏳ Mendatang | Paket *one-click launcher* lokal (FastAPI + Next.js) siap pakai sebelum pukul 09.00 WIB. | — |
