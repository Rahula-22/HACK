"""
DocumentProcessor — Smart Financial PDF Pipeline (Stages 1–4).

Stage 1: Smart Parsing   — text detection + OCR for scanned pages
Stage 2: Table Extraction — Camelot (lattice/stream) → pdfplumber fallback
Stage 3: Structuring      — section detection, table-preserving chunking, metadata
Stage 4: Keyword Marking  — financial priority flags on every chunk
"""

import os
import re
from typing import List, Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# ─── Financial vocabulary for Stage 4 ────────────────────────────────────────

FINANCIAL_KEYWORDS = [
    "revenue", "turnover", "net profit", "ebitda", "borrowings", "debt",
    "finance cost", "interest expense", "total assets", "total liabilities",
    "cash flow", "operating profit", "gross profit", "depreciation",
    "amortization", "net worth", "equity", "reserves", "capital",
    "expenditure", "income", "balance sheet", "profit and loss",
    "interest coverage", "current ratio", "working capital", "fixed assets",
    "intangible", "goodwill", "deferred tax", "minority interest",
]

# ─── Section heading patterns for Stage 3 ────────────────────────────────────

SECTION_PATTERNS = [
    (r"balance\s+sheet",                          "Balance Sheet"),
    (r"profit\s+(?:and|&)\s+loss",                "Profit and Loss"),
    (r"income\s+statement",                       "Profit and Loss"),
    (r"statement\s+of\s+profit",                  "Profit and Loss"),
    (r"cash\s+flow",                              "Cash Flow Statement"),
    (r"notes\s+to\s+(?:the\s+)?(?:accounts|financial)", "Notes to Accounts"),
    (r"independent\s+auditor",                    "Auditor Report"),
    (r"report\s+of\s+the\s+(?:board|director)",   "Director Report"),
    (r"management\s+discussion",                  "Management Discussion"),
    (r"significant\s+accounting\s+polic",         "Accounting Policies"),
    (r"schedule\s+of\s+(?:assets|liabilities|expenses|income)", "Financial Schedule"),
    (r"segment\s+(?:report|information)",         "Segment Report"),
]


class DocumentProcessor:
    """
    Handles loading and processing of PDF/CSV/Excel/TXT documents.

    Stages applied to PDFs:
      1 – Smart parsing: extract text; fall back to OCR for scanned pages.
      2 – Table extraction: Camelot (lattice then stream) → pdfplumber fallback.
      3 – Section-aware structuring: detect headings; tables are kept whole.
      4 – Financial keyword marking: high-priority flag on financial chunks.
    """

    # Tables larger than this (chars) are split with header repeated per chunk
    MAX_TABLE_CHUNK = 4000

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 300):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    # ─── Stage 1: Smart Page Parsing ─────────────────────────────────────────

    def _is_scanned(self, text: str) -> bool:
        """True when extracted text is too sparse — likely a scanned image page."""
        return len((text or "").strip()) < 80

    def _ocr_page(self, page) -> str:
        """
        OCR a pdfplumber page via pytesseract.
        Returns '' when pytesseract / Tesseract is unavailable.
        """
        try:
            import pytesseract  # noqa: F401
            img = page.to_image(resolution=200).original
            return pytesseract.image_to_string(img, lang="eng").strip()
        except Exception:
            return ""

    # ─── Stage 3: Section Detection ──────────────────────────────────────────

    def _detect_section(self, text: str) -> Optional[str]:
        """Return the section label if a recognised financial heading is found."""
        text_lower = text.lower()
        for pattern, label in SECTION_PATTERNS:
            if re.search(pattern, text_lower):
                return label
        return None

    # ─── Stage 4: Financial Keyword Marking ──────────────────────────────────

    def _is_financial(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in FINANCIAL_KEYWORDS)

    # ─── Stage 2: Table Extraction ───────────────────────────────────────────

    def _extract_tables_camelot(
        self, source: str, page_num: int, section: str
    ) -> List[Document]:
        """
        Try Camelot (lattice first, then stream) for structured table extraction.
        Returns [] when Camelot / Ghostscript is unavailable.
        """
        docs: List[Document] = []
        try:
            import camelot  # noqa: F401
        except ImportError:
            return docs

        for flavor in ("lattice", "stream"):
            try:
                tables = camelot.read_pdf(
                    source,
                    pages=str(page_num),
                    flavor=flavor,
                    suppress_stdout=True,
                )
                for i, tbl in enumerate(tables):
                    df = tbl.df
                    if df.empty or len(df) < 2:
                        continue
                    rows = [
                        " | ".join(str(c) for c in df.iloc[r])
                        for r in range(len(df))
                    ]
                    content = (
                        f"[TABLE · Page {page_num} · Section: {section} · {flavor}]\n"
                        + "\n".join(rows)
                    )
                    docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": source,
                                "page": page_num,
                                "section": section,
                                "chunk_type": "table",
                                "table_index": i,
                                "table_flavor": flavor,
                                "is_financial": True,
                                "priority": "high",
                                "row_labels": list(df.iloc[:, 0].astype(str)),
                                "column_labels": [str(c) for c in df.iloc[0]],
                            },
                        )
                    )
            except Exception:
                continue
            if docs:
                break  # lattice succeeded; don't try stream
        return docs

    def _extract_tables_pdfplumber(
        self, page, source: str, page_num: int, section: str
    ) -> List[Document]:
        """pdfplumber table extraction — used when Camelot is unavailable or fails."""
        docs: List[Document] = []
        try:
            tables = page.extract_tables()
        except Exception:
            return docs

        for i, table in enumerate(tables or []):
            rows: List[str] = []
            col_labels: List[str] = []
            row_labels: List[str] = []
            for j, row in enumerate(table):
                if not row:
                    continue
                cells = [
                    str(c).strip().replace("\n", " ") if c else "" for c in row
                ]
                if j == 0:
                    col_labels = cells
                else:
                    row_labels.append(cells[0] if cells else "")
                rows.append(" | ".join(cells))
            if not rows:
                continue
            content = (
                f"[TABLE · Page {page_num} · Section: {section}]\n"
                + "\n".join(rows)
            )
            is_fin = self._is_financial(content)
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": source,
                        "page": page_num,
                        "section": section,
                        "chunk_type": "table",
                        "table_index": i,
                        "table_flavor": "pdfplumber",
                        "is_financial": is_fin,
                        "priority": "high" if is_fin else "normal",
                        "row_labels": row_labels,
                        "column_labels": col_labels,
                    },
                )
            )
        return docs

    def _extract_page_tables(
        self, page, source: str, page_num: int, section: str
    ) -> List[Document]:
        """Stage 2: Camelot → pdfplumber fallback."""
        docs = self._extract_tables_camelot(source, page_num, section)
        if not docs:
            docs = self._extract_tables_pdfplumber(page, source, page_num, section)
        return docs

    # ─── PDF Loading ──────────────────────────────────────────────────────────

    def load_pdf(self, file_path: str) -> List[Document]:
        """
        Stages 1–4: Load PDF with OCR fallback, structured table extraction,
        section detection, and financial priority marking.

        Returns a mixed list of:
          - Table Documents  (chunk_type='table')  — preserved whole in chunking
          - Text Documents   (chunk_type='text')   — split by text splitter
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        print(f"Loading PDF: {file_path}")

        try:
            import pdfplumber
        except ImportError:
            print(
                "pdfplumber not installed — falling back to PyPDFLoader. "
                "Install with: pip install pdfplumber"
            )
            return PyPDFLoader(file_path).load()

        documents: List[Document] = []
        current_section = "General"

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"  {total_pages} pages found")

            for page_num, page in enumerate(pdf.pages):
                page_label = page_num + 1

                # ── Stage 1: extract text (or OCR for scanned pages) ──────────
                try:
                    raw_text = page.extract_text() or ""
                except Exception:
                    raw_text = ""

                if self._is_scanned(raw_text):
                    ocr_text = self._ocr_page(page)
                    if ocr_text:
                        raw_text = ocr_text
                        print(f"    Page {page_label}: OCR used (scanned page)")

                # ── Stage 3: detect section heading ──────────────────────────
                found = self._detect_section(raw_text)
                if found:
                    current_section = found

                # ── Stage 2: extract tables ───────────────────────────────────
                table_docs = self._extract_page_tables(
                    page, file_path, page_label, current_section
                )
                documents.extend(table_docs)

                # ── Stage 4: build text document with priority marking ────────
                if raw_text.strip():
                    is_fin = self._is_financial(raw_text)
                    documents.append(
                        Document(
                            page_content=raw_text.strip(),
                            metadata={
                                "source": file_path,
                                "page": page_label,
                                "section": current_section,
                                "chunk_type": "text",
                                "is_financial": is_fin,
                                "priority": "high" if is_fin else "normal",
                            },
                        )
                    )

        print(f"  Extracted {len(documents)} raw documents from PDF")
        return documents

    def load_pdfs_from_directory(self, directory: str) -> List[Document]:
        """Load all PDFs from a directory."""
        all_docs: List[Document] = []
        if not os.path.exists(directory):
            os.makedirs(directory)
            return all_docs

        pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
        if not pdf_files:
            print(f"No PDF files found in {directory}")
            return all_docs

        for pdf_file in pdf_files:
            try:
                all_docs.extend(self.load_pdf(os.path.join(directory, pdf_file)))
            except Exception as e:
                print(f"Error loading {pdf_file}: {e}")

        print(f"Total raw documents loaded: {len(all_docs)}")
        return all_docs

    # ─── Stage 3: Section-Aware Chunking ─────────────────────────────────────

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Stage 3 chunking rules:
          - Table docs  → kept whole (or split with repeated header for large tables)
          - Text docs   → split normally by RecursiveCharacterTextSplitter
          - Every chunk inherits section, is_financial, and priority metadata.
        """
        if not documents:
            return []

        table_docs = [d for d in documents if d.metadata.get("chunk_type") == "table"]
        text_docs  = [d for d in documents if d.metadata.get("chunk_type") != "table"]

        print(
            f"Splitting {len(text_docs)} text docs; "
            f"preserving {len(table_docs)} table docs..."
        )

        # Split text documents normally
        split_text: List[Document] = []
        if text_docs:
            split_text = self.text_splitter.split_documents(text_docs)
            for doc in split_text:
                doc.metadata.setdefault("section", "General")
                if "is_financial" not in doc.metadata:
                    doc.metadata["is_financial"] = self._is_financial(doc.page_content)
                doc.metadata["priority"] = (
                    "high" if doc.metadata.get("is_financial") else "normal"
                )

        # Handle oversized table docs
        final_tables: List[Document] = []
        for doc in table_docs:
            if len(doc.page_content) <= self.MAX_TABLE_CHUNK:
                final_tables.append(doc)
            else:
                final_tables.extend(self._split_table_doc(doc))

        all_chunks = final_tables + split_text
        print(
            f"Created {len(all_chunks)} chunks "
            f"({len(final_tables)} table, {len(split_text)} text)"
        )
        return all_chunks

    def _split_table_doc(self, doc: Document) -> List[Document]:
        """Split a large table Document, repeating the header row on each sub-chunk."""
        lines = doc.page_content.split("\n")
        header     = lines[0] if lines else ""
        col_header = lines[1] if len(lines) > 1 else ""
        body_lines = lines[2:] if len(lines) > 2 else lines[1:]

        chunks: List[Document] = []
        current: List[str] = [header, col_header]

        for line in body_lines:
            if (
                len("\n".join(current + [line])) > self.MAX_TABLE_CHUNK
                and len(current) > 2
            ):
                chunks.append(
                    Document(
                        page_content="\n".join(current),
                        metadata=doc.metadata.copy(),
                    )
                )
                current = [header, col_header, line]
            else:
                current.append(line)

        if current:
            chunks.append(
                Document(
                    page_content="\n".join(current),
                    metadata=doc.metadata.copy(),
                )
            )
        return chunks

    # ─── Pipeline helpers ─────────────────────────────────────────────────────

    def process_pdf(self, file_path: str) -> List[Document]:
        """Load + chunk a single PDF."""
        return self.split_documents(self.load_pdf(file_path))

    def process_directory(self, directory: str) -> List[Document]:
        """Load + chunk all PDFs in a directory."""
        return self.split_documents(self.load_pdfs_from_directory(directory))

    # ─── Structured / Text document loaders ──────────────────────────────────

    def load_csv(self, file_path: str) -> List[Document]:
        """Load a CSV file (one Document per 30-row chunk)."""
        import csv
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        print(f"Loading CSV: {file_path}")
        rows: List[str] = []
        headers: List[str] = []
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            for row in reader:
                rows.append("  |  ".join(f"{k}: {v}" for k, v in row.items() if v))

        ROWS_PER_CHUNK = 30
        docs: List[Document] = []
        for i in range(0, len(rows), ROWS_PER_CHUNK):
            batch = rows[i : i + ROWS_PER_CHUNK]
            content = (
                f"[CSV Data from {os.path.basename(file_path)}]\n"
                f"Columns: {', '.join(headers)}\n\n"
                + "\n".join(batch)
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "type": "csv",
                        "row_start": i,
                        "chunk_type": "text",
                        "is_financial": self._is_financial(content),
                    },
                )
            )
        print(f"Loaded CSV → {len(docs)} document(s)")
        return docs

    def load_excel(self, file_path: str) -> List[Document]:
        """Load an Excel file (one Document per sheet)."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required: pip install pandas openpyxl")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        print(f"Loading Excel: {file_path}")
        xl = pd.ExcelFile(file_path)
        docs: List[Document] = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet).fillna("")
            lines = [
                f"Sheet: {sheet}",
                f"Columns: {', '.join(str(c) for c in df.columns)}",
            ]
            for _, row in df.iterrows():
                line = "  |  ".join(
                    f"{col}: {val}" for col, val in row.items() if str(val).strip()
                )
                if line:
                    lines.append(line)
            content = "\n".join(lines)
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "type": "excel",
                        "sheet": sheet,
                        "chunk_type": "text",
                        "is_financial": self._is_financial(content),
                    },
                )
            )
        print(f"Loaded Excel → {len(docs)} sheet(s)")
        return docs

    def load_text(self, file_path: str) -> List[Document]:
        """Load a plain-text file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return [
            Document(
                page_content=content,
                metadata={
                    "source": file_path,
                    "type": "text",
                    "chunk_type": "text",
                    "is_financial": self._is_financial(content),
                },
            )
        ]

    def load_any(self, file_path: str) -> List[Document]:
        """Auto-detect file type and load accordingly."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self.load_pdf(file_path)
        elif ext == ".csv":
            return self.load_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            return self.load_excel(file_path)
        elif ext == ".txt":
            return self.load_text(file_path)
        else:
            print(f"Unsupported file type: {ext} — skipping {file_path}")
            return []

    def process_file(self, file_path: str) -> List[Document]:
        """Load and chunk any supported file."""
        return self.split_documents(self.load_any(file_path))

    def process_directory_all(self, directory: str) -> List[Document]:
        """Load and chunk ALL supported document types from a directory."""
        SUPPORTED = {".pdf", ".csv", ".xlsx", ".xls", ".txt"}
        all_documents: List[Document] = []

        if not os.path.exists(directory):
            os.makedirs(directory)
            return all_documents

        files = [
            f
            for f in os.listdir(directory)
            if os.path.splitext(f)[1].lower() in SUPPORTED
        ]
        if not files:
            print(f"No supported files found in {directory}")
            return all_documents

        for fname in files:
            try:
                all_documents.extend(self.load_any(os.path.join(directory, fname)))
            except Exception as e:
                print(f"Error loading {fname}: {e}")

        print(f"Total documents loaded from directory: {len(all_documents)}")
        return self.split_documents(all_documents)
