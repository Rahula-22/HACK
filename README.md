# AI Corporate Credit Decisioning Engine

A RAG (Retrieval-Augmented Generation) based AI assistant for Indian banks that analyses corporate financial documents and generates Credit Appraisal Memos (CAMs). Built with Python, FastAPI, React, and Groq AI.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-2.x-009688.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg)
![Groq](https://img.shields.io/badge/Groq-LLaMA--3.3--70B-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Features

- **AI Credit Analyst** — Powered by Groq's LLaMA-3.3-70B for fast, accurate financial analysis
- **Document RAG** — Retrieves relevant context from uploaded corporate financial documents
- **CAM Generation** — Generates full Credit Appraisal Memos in one click
- **8-Stage Smart Financial PDF Pipeline** — OCR, table extraction, structuring, keyword tagging, hybrid retrieval, extraction, validation, and explainability
- **Financial Ratio Extraction** — Automatically identifies key ratios and risk indicators with page-level traceability
- **Risk Flags** — Debt/EBITDA and Interest Coverage Ratio thresholds automatically flagged
- **Fast Semantic Search** — FAISS vector database for millisecond similarity search
- **Multi-format Support** — PDF, CSV, Excel (.xlsx/.xls), and TXT documents

---

## Architecture

| Layer | Technology |
|---|---|
| Frontend UI | React 18 + Vite + TailwindCSS |
| Backend API | FastAPI (Python) |
| LLM | Groq — LLaMA-3.3-70B-Versatile |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector Store | FAISS |
| Document Parsing | pdfplumber + Camelot (tables) + pytesseract (OCR) |

---

## 8-Stage Document Pipeline

| Stage | Name | Description |
|---|---|---|
| 1 | OCR | `pytesseract` fallback for scanned / image-only PDF pages |
| 2 | Table Extraction | Camelot (lattice → stream fallback) with pdfplumber as last resort |
| 3 | Structuring | Section-pattern regex; table chunks kept whole; header repeated on splits |
| 4 | Keyword Tagging | `FINANCIAL_KEYWORDS` → `is_financial` + `priority` metadata on every chunk |
| 5 | Hybrid Retrieval | Semantic similarity + keyword overlap scoring; table & priority score boosts |
| 6 | Extraction | `FinancialExtractor` → `{value, page, snippet}` per core financial field |
| 7 | Validation | Debt/EBITDA (> 5.0×) and ICR (< 1.5×) risk flags |
| 8 | Explainability | Source file + page traceability attached to every extracted value |

---

## Project Structure

```
UGP-main/
├── api.py                   # FastAPI backend — all REST endpoints
├── chatbot.py               # CreditDecisioningEngine — RAG + Groq
├── document_processor.py    # 8-stage document ingestion pipeline
├── financial_extractor.py   # Stages 6–8: extraction, validation, reporting
├── models.py                # FAISS VectorDatabase + hybrid_search()
├── config.py                # All tunable settings
├── main.py                  # Streamlit UI (alternative to React frontend)
├── process_documents.py     # Standalone document processing script
├── requirements.txt
├── data/
│   ├── <your documents>     # Drop PDFs / CSVs / XLSX files here
│   └── vectorstore/         # FAISS index (auto-generated, do not edit)
└── frontend/                # React + Vite frontend
    ├── src/
    ├── package.json
    └── vite.config.js
```

---

## Prerequisites

### System binaries (install before `pip install`)

**Tesseract OCR** — required for Stage 1 (scanned PDF pages)
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- After installing, add the Tesseract folder to your system `PATH`

**Ghostscript** — required by Camelot for Stage 2 (table extraction)
- Windows: https://www.ghostscript.com/releases/
- After installing, add the `bin/` folder to your system `PATH`

### Software
- Python 3.10+
- Node.js 18+ (only needed for the React frontend)
- A Groq API key — get one free at [console.groq.com](https://console.groq.com)

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/ugp.git
cd ugp
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

> **Tip:** If you see a NumPy 2.x conflict (e.g. with torch), run:
> `pip install "numpy<2"`

### 3. Set your Groq API key

Open `config.py` and replace the placeholder:
```python
GROQ_API_KEY = "your_groq_api_key_here"
```

### 4. Install frontend dependencies *(React UI only)*
```bash
cd frontend
npm install
cd ..
```

---

## Running the Application

### Step 1 — Add your documents
Copy any PDF, CSV, or Excel files into the `data/` folder.

### Step 2 — Process documents into the knowledge base
```bash
python process_documents.py
```

This runs the full 8-stage pipeline and saves the FAISS index to `data/vectorstore/`.

> **Important:** Re-run this step every time you add new documents or after clearing the knowledge base.

### Step 3 — Start the backend API
```bash
python api.py
```
- API runs at: `http://localhost:8000`
- Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Step 4 — Start the frontend

**React UI (recommended):**
```bash
cd frontend
npm run dev
```
Runs at `http://localhost:5173`

**Streamlit UI (alternative — no Node.js needed):**
```bash
streamlit run main.py
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | Health check + knowledge base status |
| `POST` | `/api/set-api-key` | Set Groq API key at runtime |
| `GET` | `/api/list-documents` | List all uploaded documents |
| `POST` | `/api/upload-document` | Upload a document (PDF/CSV/XLSX/TXT) |
| `POST` | `/api/process-documents` | Process uploads into the vector store |
| `DELETE` | `/api/clear-knowledge-base` | Clear the FAISS vector store |
| `POST` | `/api/chat` | Send a credit analysis query (RAG response) |
| `DELETE` | `/api/clear-chat-history` | Clear the current chat session history |
| `POST` | `/api/generate-cam` | Generate a full Credit Appraisal Memo |
| `GET` | `/api/extract-financials` | Extract key financial KPIs |
| `GET` | `/api/extract-structured-financials` | Stages 6–8: structured extraction + risk flags |

### Example: Generate a CAM

```bash
curl -X POST http://localhost:8000/api/generate-cam \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Industries Ltd",
    "loan_amount": "₹50 Crore",
    "loan_purpose": "Working capital expansion",
    "loan_tenor": "3 years"
  }'
```

### Example: Extract structured financials (Stages 6–8)

```bash
curl http://localhost:8000/api/extract-structured-financials
```

**Response shape:**
```json
{
  "success": true,
  "report": {
    "extracted_financials": {
      "revenue": { "value": 1200.5, "page": 12, "snippet": "..." }
    },
    "validation": {
      "debt_to_ebitda": 4.2,
      "interest_coverage_ratio": 2.1,
      "risk_flags": []
    },
    "traceability": { ... },
    "source_docs_used": 8
  }
}
```

---

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `2000` | Document chunk size (characters) |
| `CHUNK_OVERLAP` | `300` | Overlap between consecutive chunks |
| `NUM_RETRIEVED_DOCS` | `10` | Number of chunks retrieved per query |
| `HYBRID_RETRIEVAL` | `True` | Enable hybrid (semantic + keyword) search |
| `OCR_ENABLED` | `True` | Enable pytesseract OCR for scanned pages |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID |
| `GROQ_TEMPERATURE` | `0.3` | Lower = more precise financial answers |
| `GROQ_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `RISK_DEBT_TO_EBITDA_MAX` | `5.0` | Risk flag threshold for Debt/EBITDA ratio |
| `RISK_INTEREST_COVERAGE_MIN` | `1.5` | Risk flag threshold for Interest Coverage Ratio |

---

## Supported Document Types

| Format | Use case |
|---|---|
| `.pdf` | Annual Reports, CMA Data, Balance Sheets, Due Diligence Notes |
| `.csv` | Financial data exports, CMA data tables |
| `.xlsx` / `.xls` | Excel financial models, ratio workbooks |
| `.txt` | Plain-text financial notes, credit memos |

---

## Troubleshooting

**`tesseract is not installed or not in PATH`**
Install Tesseract and add it to your system PATH. Set `OCR_ENABLED = False` in `config.py` to disable OCR if not needed.

**`Ghostscript not found` (Camelot error)**
Install Ghostscript and add its `bin/` directory to PATH. Without it, Stage 2 falls back to pdfplumber for table extraction.

**`No documents found to process`**
Ensure your files are placed in the `data/` directory and have a supported extension (`.pdf`, `.csv`, `.xlsx`, `.xls`, `.txt`).

**Knowledge base is empty after re-running**
The vectorstore is persisted at `data/vectorstore/`. Run `python process_documents.py` to rebuild it after adding new documents or clearing the store.

**NumPy version conflict**
```bash
pip install "numpy<2"
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- Built to streamline credit decisioning workflows for Indian banking institutions
- Powered by [Groq](https://groq.com) inference and [LangChain](https://langchain.com) ecosystem
- Vector search by [FAISS](https://github.com/facebookresearch/faiss) (Facebook AI Research)
- Embeddings by [sentence-transformers](https://www.sbert.net/)
