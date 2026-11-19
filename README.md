# Newstent — Media Monitoring & Reporting Automation

Sistem otomasi *end-to-end* untuk pengolahan data *media monitoring* **Newstensity (Binokular)**—mulai dari pembersihan *raw data*, koreksi sentimen & penyeragaman topik (`Newstrends`) berbasis Cloud AI, pembuatan *Pivot Table* otomatis, hingga penyusunan draf laporan **Excel, PowerPoint (`.pptx`), dan Word/Email Body (`.docx`)** sebelum *deadline* pagi pukul **09.00 WIB**.

---

## Struktur Direktori Proyek

```text
Newstensity/
├── docs/
│   ├── phase-1-requirements/
│   │   ├── PROJECT_BASELINE.md        # BRD: Latar belakang bisnis, alur As-Is, bottlenecks, & ROI
│   │   └── SYSTEM_REQUIREMENTS.md     # SRS: SDLC plan, Cloud AI spec, FR/NFR, & estimasi biaya
│   └── phase-2-design/
│       └── ARCHITECTURE_DISCUSSION.md # Catatan desain arsitektur & alur end-to-end pipeline
├── clients/                           # Folder per klien: config.yaml + template PPT & Word (Phase 2/3)
├── data/                              # Runtime data: raw input, SQLite cache, & output report (ignored Git)
├── src/                               # Source code Python modular — Phase 3
├── tests/                             # Unit test & dataset QA — Phase 4
├── .env                               # Credentials & API keys lokal (tidak masuk Git)
├── .env.example                       # Contoh variabel environment
├── .gitignore                         # Aturan pengecualian Git standar
└── README.md                          # Ringkasan & panduan navigasi proyek
```

---

## Roadmap SDLC

| Fase | Status | Fokus Utama | Dokumen / Lokasi |
| :--- | :--- | :--- | :--- |
| **Phase 1: Planning & Requirements** | 🔄 Proses | Analisis kebutuhan bisnis (*As-Is*), spesifikasi sistem (*FR/NFR*), & estimasi biaya Cloud AI. | `docs/phase-1-requirements/` |
| **Phase 2: System & Architecture Design** | 🔄 Persiapan | Desain pipeline *end-to-end*, skema `config.yaml`, SQLite cache, & *placeholder mapping* PPT/Word. | `docs/phase-2-design/` |
| **Phase 3: Core Development** | ⏳ Mendatang | Implementasi modul Python (`Pre-Cleaning`, `AI Engine`, `Auto-Pivot`, `Report Generators`). | `src/` |
| **Phase 4: Testing & Quality Control** | ⏳ Mendatang | Uji akurasi sentimen/Newstrend, validasi angka Pivot 100%, & benchmark SLA/biaya. | `tests/` |
| **Phase 5: Deployment & Scheduling** | ⏳ Mendatang | Otomasi eksekusi pagi (`Task Scheduler` / CLI) untuk $\ge 3$ klien sebelum pukul 09.00 WIB. | — |
