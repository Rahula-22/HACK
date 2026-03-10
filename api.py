"""
FastAPI backend for the AI Corporate Credit Decisioning Engine
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
from chatbot import CreditDecisioningEngine
from document_processor import DocumentProcessor
import config

# ─── App initialisation ──────────────────────────────────────────────────────

app = FastAPI(
    title="AI Corporate Credit Decisioning Engine",
    description="Backend API for AI-powered corporate credit appraisal (Indian Banks)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = CreditDecisioningEngine(groq_api_key=config.GROQ_API_KEY)
engine.load_knowledge_base()

# ─── Pydantic models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    api_key: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[dict]

class CAMRequest(BaseModel):
    company_name: str
    loan_amount: str
    loan_purpose: str
    loan_tenor: Optional[str] = ""

class CAMResponse(BaseModel):
    cam: str

class StatusResponse(BaseModel):
    knowledge_base_loaded: bool
    total_documents: int
    api_key_set: bool

class ApiKeyRequest(BaseModel):
    api_key: str

# ─── Helpers ─────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".txt"}


def _supported(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


def _list_documents() -> List[str]:
    if not os.path.exists(config.PDF_DIRECTORY):
        return []
    return [
        f for f in os.listdir(config.PDF_DIRECTORY)
        if _supported(f) and os.path.isfile(os.path.join(config.PDF_DIRECTORY, f))
    ]

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "healthy", "message": "Credit Decisioning Engine API is running"}


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    vectorstore_path = os.path.join(config.VECTORSTORE_DIRECTORY, "index.faiss")
    docs = _list_documents()
    return StatusResponse(
        knowledge_base_loaded=os.path.exists(vectorstore_path),
        total_documents=len(docs),
        api_key_set=bool(config.GROQ_API_KEY or engine.groq_client is not None),
    )


@app.post("/api/set-api-key")
async def set_api_key(request: ApiKeyRequest):
    try:
        engine.set_groq_api_key(request.api_key)
        return {"success": True, "message": "API key set successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Document management ─────────────────────────────────────────────────────

@app.get("/api/list-documents")
async def list_documents():
    """List all uploaded documents (PDF, CSV, XLSX, TXT)."""
    return {"documents": _list_documents()}


# Keep legacy route for frontend compatibility
@app.get("/api/list-pdfs")
async def list_pdfs():
    return {"pdfs": _list_documents()}


@app.post("/api/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """Upload any supported document (PDF, CSV, XLSX, XLS, TXT)."""
    if not _supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    os.makedirs(config.PDF_DIRECTORY, exist_ok=True)
    dest = os.path.join(config.PDF_DIRECTORY, file.filename)
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"success": True, "message": f"{file.filename} uploaded successfully"}


# Keep legacy route for frontend compatibility
@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    return await upload_document(file)


@app.post("/api/process-documents")
async def process_documents():
    """Process all uploaded documents into the vector knowledge base."""
    try:
        processor = DocumentProcessor(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        chunks = processor.process_directory_all(config.PDF_DIRECTORY)
        if not chunks:
            return {"success": False, "message": "No documents found to process"}
        engine.add_documents_to_knowledge_base(chunks)
        return {
            "success": True,
            "message": f"Processed {len(chunks)} document chunks into the knowledge base",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clear-knowledge-base")
async def clear_knowledge_base():
    try:
        engine.vector_db.clear_vectorstore()
        return {"success": True, "message": "Knowledge base cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Credit Analyst Chat ──────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a credit analysis query and receive a RAG-based response."""
    try:
        if request.api_key:
            engine.set_groq_api_key(request.api_key)
        elif not engine.groq_client and config.GROQ_API_KEY:
            engine.set_groq_api_key(config.GROQ_API_KEY)

        response, sources = engine.chat(request.message)

        formatted_sources = [
            {
                "source": os.path.basename(doc.metadata.get("source", "Unknown")),
                "page": doc.metadata.get("page", "N/A"),
                "content": doc.page_content[:300] + "...",
            }
            for doc in sources
        ]
        return ChatResponse(response=response, sources=formatted_sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clear-chat-history")
async def clear_chat_history():
    engine.clear_history()
    return {"success": True, "message": "Chat history cleared"}


# ─── CAM Generation ──────────────────────────────────────────────────────────

@app.post("/api/generate-cam", response_model=CAMResponse)
async def generate_cam(request: CAMRequest):
    """Generate a full Credit Appraisal Memo (CAM) for the given borrower."""
    try:
        if not engine.groq_client and config.GROQ_API_KEY:
            engine.set_groq_api_key(config.GROQ_API_KEY)

        cam = engine.generate_cam(
            company_name=request.company_name,
            loan_amount=request.loan_amount,
            loan_purpose=request.loan_purpose,
            loan_tenor=request.loan_tenor or "",
        )
        return CAMResponse(cam=cam)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Financial Metrics ────────────────────────────────────────────────────────

@app.get("/api/extract-financials")
async def extract_financials():
    """Extract key financial KPIs from uploaded documents."""
    try:
        if not engine.groq_client and config.GROQ_API_KEY:
            engine.set_groq_api_key(config.GROQ_API_KEY)
        metrics = engine.extract_financial_metrics()
        return {"success": True, "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/extract-structured-financials")
async def extract_structured_financials():
    """
    Stages 6–8: Structured extraction with page-level traceability and risk flags.

    Returns:
      extracted_financials — {field: {value, page, snippet}} for 8 core fields
      validation           — computed ratios + risk flags (Debt/EBITDA, ICR)
      traceability         — source file + page + snippet per extracted value
      source_docs_used     — number of document chunks used for extraction
    """
    try:
        if not engine.groq_client and config.GROQ_API_KEY:
            engine.set_groq_api_key(config.GROQ_API_KEY)
        report = engine.extract_structured_financials()
        return {"success": True, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
