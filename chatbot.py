import json
import re
import os
from typing import List, Tuple, Optional, Dict
from langchain_core.documents import Document
from models import VectorDatabase
from financial_extractor import FinancialExtractor
import config


class CreditDecisioningEngine:
    """
    AI-powered Corporate Credit Decisioning Engine for Indian Banks.
    Analyzes financial documents and generates Credit Appraisal Memos (CAM)
    using RAG-based retrieval and Groq LLM.
    """

    SYSTEM_PROMPT = (
        "You are a Senior Credit Officer at a leading Indian bank with deep expertise in:\n"
        "- Corporate credit appraisal and risk assessment\n"
        "- Indian banking regulations (RBI guidelines, Basel III, IRAC norms)\n"
        "- Financial statement analysis (Balance Sheet, P&L, Cash Flow, CMA data)\n"
        "- Key financial ratios: DSCR, TOL/TNW, Current Ratio, Interest Coverage, PAT Margin\n"
        "- Industry benchmarking and sector-specific credit norms\n"
        "- NPA classification and early warning signals\n\n"
        "Always provide precise, data-backed credit analysis using formal banking terminology. "
        "Cite specific figures from the documents when available."
    )

    def __init__(self, groq_api_key: Optional[str] = None):
        self.vector_db = VectorDatabase(config.VECTORSTORE_DIRECTORY)
        self.chat_history: List[Tuple[str, str]] = []
        self.groq_client = None
        self.api_key = groq_api_key or config.GROQ_API_KEY or os.getenv("GROQ_API_KEY")

        if self.api_key:
            self._initialize_groq_client(self.api_key)
    
    def _initialize_groq_client(self, api_key: str) -> None:
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=api_key)
            print("Groq client initialized successfully")
        except TypeError:
            try:
                from groq import Groq
                import httpx
                self.groq_client = Groq(api_key=api_key, http_client=httpx.Client())
                print("Groq client initialized with custom http client")
            except Exception as inner_e:
                print(f"Warning: Could not initialize Groq client: {inner_e}")
                self.groq_client = None
        except Exception as e:
            print(f"Warning: Could not initialize Groq client: {e}")
            self.groq_client = None

    def set_groq_api_key(self, api_key: str) -> None:
        self.api_key = api_key
        self._initialize_groq_client(api_key)
        if not self.groq_client:
            raise Exception("Failed to initialize Groq client. Please check your API key.")

    def load_knowledge_base(self) -> bool:
        return self.vector_db.load_vectorstore()

    def add_documents_to_knowledge_base(self, documents: List[Document]) -> None:
        self.vector_db.add_documents(documents)

    def retrieve_context(self, query: str, k: int = None) -> List[Document]:
        """Stage 5 — hybrid retrieval (semantic + keyword + priority boosting)."""
        k = k or config.NUM_RETRIEVED_DOCS
        return self.vector_db.hybrid_search(query, k=k)

    def format_context(self, documents: List[Document]) -> str:
        if not documents:
            return "No relevant financial information found in the uploaded documents."
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get('source', 'Unknown')
            page = doc.metadata.get('page', '')
            page_info = f", Page {page}" if page else ""
            context_parts.append(
                f"[Source {i}: {os.path.basename(source)}{page_info}]\n{doc.page_content}\n"
            )
        return "\n".join(context_parts)

    # ─── Credit Analyst Chat ──────────────────────────────────────────────────

    def chat(self, user_message: str) -> Tuple[str, List[Document]]:
        """RAG-based credit analysis Q&A."""
        docs = self.retrieve_context(user_message)
        context = self.format_context(docs)

        if context == "No relevant financial information found in the uploaded documents.":
            prompt = (
                f"A credit analyst asked: \"{user_message}\"\n\n"
                "No relevant financial data was found in the uploaded documents. "
                "Briefly explain what additional documents or data would help answer this question."
            )
        else:
            prompt = (
                f"**Financial Context from Documents:**\n{context}\n\n"
                f"**Analyst Query:** {user_message}\n\n"
                "**Instructions:**\n"
                "- Answer based strictly on the financial data provided\n"
                "- Use precise credit/banking terminology suitable for Indian banks\n"
                "- Cite specific figures and ratios when available\n"
                "- Express monetary values in Indian convention (Lakhs/Crores) if applicable\n"
                "- If data is insufficient, state what additional information is required\n\n"
                "**Your Analysis:**"
            )

        response = self._call_groq(prompt)
        self.chat_history.append((user_message, response))
        if len(self.chat_history) > config.MAX_HISTORY_LENGTH:
            self.chat_history = self.chat_history[-config.MAX_HISTORY_LENGTH:]
        return response, docs

    # ─── CAM Generation ──────────────────────────────────────────────────────

    def generate_cam(
        self,
        company_name: str,
        loan_amount: str,
        loan_purpose: str,
        loan_tenor: str = "",
    ) -> str:
        """Generate a full Credit Appraisal Memo (CAM)."""
        queries = [
            f"{company_name} financial performance revenue profit EBITDA",
            f"{company_name} total debt borrowings liabilities balance sheet net worth",
            f"{company_name} cash flow operations DSCR debt repayment",
            f"{company_name} business operations promoters management background",
            f"{company_name} industry risk factors competitors market position",
            f"{company_name} total expenditure expenses operating cost purchase employee finance",
        ]
        all_docs = self._deduplicated_retrieval(queries, k=4)
        context = self.format_context(all_docs[:14])

        cam_prompt = f"""You are a Senior Credit Officer drafting a formal Credit Appraisal Memo (CAM) for a credit committee.

**Proposed Facility Details:**
- Borrower: {company_name}
- Proposed Facility Amount: ₹{loan_amount}
- Purpose of Facility: {loan_purpose}
- Tenor: {loan_tenor if loan_tenor else "As per proposal"}

**Financial & Business Context Extracted from Submitted Documents:**
{context}

Generate a comprehensive, well-structured CAM using the following template. Where document data is available, use it precisely. Where data is absent, note "Not available in submitted documents."

---

# CREDIT APPRAISAL MEMORANDUM
**Date:** {self._today()}
**Reference No:** CAM/{company_name[:3].upper()}/2025-26

## 1. EXECUTIVE SUMMARY
Summarise: borrower identity, proposed facility, purpose, key financial strengths/weaknesses, and the final recommendation (Approve / Decline / Conditional Approval).

## 2. BORROWER PROFILE
- Company name, CIN, date of incorporation, registered office
- Promoter/promoter group background
- Nature of business and product/service description
- Industry segment and business model

## 3. MANAGEMENT ASSESSMENT
- Key management personnel (MD, CFO, etc.) and their experience
- Corporate governance practices
- Track record with existing lenders (if available)

## 4. FINANCIAL ANALYSIS
### 4.1 Income Statement Highlights (Last 2–3 Years)
Provide a markdown table with: FY, Revenue, EBITDA, EBITDA%, PAT, PAT%, Depreciation, Interest.

### 4.2 Balance Sheet Summary
Provide a markdown table with: FY, Total Assets, Net Worth, Total Debt, Current Assets, Current Liabilities.

### 4.3 Key Financial Ratios
| Ratio | FY Value | Benchmark | Assessment |
|-------|----------|-----------|------------|
| Debt Service Coverage Ratio (DSCR) | | ≥ 1.25x | |
| Current Ratio | | ≥ 1.33x | |
| Debt-to-Equity (TOL/TNW) | | ≤ 3.0x | |
| Interest Coverage Ratio | | ≥ 2.0x | |
| PAT Margin (%) | | Sector norm | |
| Return on Equity (ROE) | | Sector norm | |

Fill each cell from the document context; mark "N/A" if unavailable.

### 4.4 Cash Flow Analysis
Summarise operating, investing, and financing cash flows and comment on free cash flow adequacy for debt servicing.

## 5. CREDIT RISK ASSESSMENT
### 5.1 Industry / Sector Risk
### 5.2 Business Risk
### 5.3 Financial Risk
### 5.4 Management & Promoter Risk
### 5.5 External / Macro Risk

## 6. RISK MITIGANTS
- Primary security proposed
- Collateral / additional security
- Personal / corporate guarantees
- Key financial covenants

## 7. RECOMMENDED TERMS & CONDITIONS
- Facility Type & Amount: ₹{loan_amount}
- Tenor: {loan_tenor if loan_tenor else "TBD"}
- Interest Rate: [MCLR/Repo Rate + spread; e.g., Repo + 2.50%]
- Repayment Schedule: [Monthly EMI / Bullet / Structured]
- Security (Primary): [Hypothecation / Mortgage]
- Security (Collateral): [FD / Property / Pledge]
- Financial Covenants (suggested): DSCR ≥ 1.25x; DE Ratio ≤ X; Minimum Net Worth ≥ ₹Y Cr
- Conditions Precedent: [List 3–5 CPs]

## 8. RECOMMENDATION
**[RECOMMENDED FOR APPROVAL / RECOMMENDED FOR REJECTION / CONDITIONAL APPROVAL]**

State clear rationale with supporting data points from the financial analysis.

---
*This CAM has been prepared based on documents submitted by the borrower. The bank reserves the right to seek additional information.*"""

        return self._call_groq(cam_prompt, max_tokens=3500)

    # ─── Financial Metrics Extraction ────────────────────────────────────────

    def extract_financial_metrics(self) -> Dict:
        """Extract key financial KPIs from uploaded documents and return as a dict."""
        queries = [
            "revenue total income net sales annual turnover",
            "EBITDA operating profit gross profit margin",
            "net profit PAT profit after tax",
            "total debt borrowings term loans working capital",
            "DSCR debt service coverage annual repayment",
            "current ratio current assets current liabilities liquidity",
            "interest paid finance cost interest expense",
            "shareholder equity net worth reserves surplus",
            "total assets fixed assets capital employed",
            "total expenditure total expenses operating expenses cost of goods sold purchases",
            "employee benefit expense staff cost other expenses depreciation amortisation",
        ]
        all_docs = self._deduplicated_retrieval(queries, k=4)
        context = self.format_context(all_docs[:20])

        prompt = f"""You are a credit analyst. From the financial context below, extract key financial metrics.

Return ONLY a valid JSON object with these exact keys (use null for unavailable values):
{{
  "company_name": null,
  "financial_year": null,
  "currency": "INR",
  "revenue": null,
  "total_expenditure": null,
  "ebitda": null,
  "ebitda_margin_pct": null,
  "net_profit": null,
  "pat_margin_pct": null,
  "total_debt": null,
  "net_worth": null,
  "total_assets": null,
  "current_ratio": null,
  "debt_equity_ratio": null,
  "interest_coverage_ratio": null,
  "dscr": null,
  "roce_pct": null
}}

Financial Context:
{context}

Return only the JSON object, no commentary."""

        raw = self._call_groq(prompt, max_tokens=1000, temperature=0.1)
        metrics: Dict = {}
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                metrics = json.loads(match.group())
        except Exception:
            pass

        # Fallback: compute derived metrics from base numbers when LLM left them null
        revenue = metrics.get("revenue")
        ebitda = metrics.get("ebitda")
        net_profit = metrics.get("net_profit")
        net_worth = metrics.get("net_worth")
        total_debt = metrics.get("total_debt")

        if metrics.get("ebitda_margin_pct") is None and revenue and ebitda:
            try:
                metrics["ebitda_margin_pct"] = round((float(ebitda) / float(revenue)) * 100, 2)
            except (ValueError, ZeroDivisionError):
                pass

        if metrics.get("pat_margin_pct") is None and revenue and net_profit:
            try:
                metrics["pat_margin_pct"] = round((float(net_profit) / float(revenue)) * 100, 2)
            except (ValueError, ZeroDivisionError):
                pass

        if metrics.get("debt_equity_ratio") is None and total_debt and net_worth:
            try:
                metrics["debt_equity_ratio"] = round(float(total_debt) / float(net_worth), 2)
            except (ValueError, ZeroDivisionError):
                pass

        return metrics

    # ─── Structured Financial Extraction (Stages 6–8) ────────────────────────

    def extract_structured_financials(self) -> Dict:
        """
        Stages 6 + 7 + 8 — structured extraction with full explainability.

        Returns:
        {
            "extracted_financials": { field: {value, page, snippet} },
            "validation":           { "ratios": {...}, "risk_flags": [...] },
            "traceability":         { field: {value, page, snippet, source_file} },
            "source_docs_used":     int
        }
        """
        if not self.groq_client:
            return {"error": "Groq client not initialised. Please set your API key."}

        # Use financial-specific queries to maximise recall of relevant chunks
        queries = [
            "revenue total income net sales annual turnover",
            "net profit PAT profit after tax bottom line",
            "EBITDA operating profit earnings before interest tax depreciation",
            "total debt borrowings term loans working capital facilities",
            "interest expense finance cost interest paid",
            "total assets fixed assets capital employed",
            "total liabilities current liabilities long term liabilities",
            "cash flow from operations investing financing activities",
        ]
        all_docs = self._deduplicated_retrieval(queries, k=5)

        extractor = FinancialExtractor(
            groq_client=self.groq_client,
            groq_model=config.GROQ_MODEL,
        )
        return extractor.build_report(all_docs)

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _deduplicated_retrieval(self, queries: List[str], k: int = 4) -> List[Document]:
        """Retrieve docs for multiple queries, deduplicated by content."""
        all_docs: List[Document] = []
        seen: set = set()
        for q in queries:
            for doc in self.retrieve_context(q, k=k):
                key = doc.page_content[:120]
                if key not in seen:
                    seen.add(key)
                    all_docs.append(doc)
        return all_docs

    def _call_groq(
        self,
        prompt: str,
        max_tokens: int = None,
        temperature: float = None,
    ) -> str:
        if not self.groq_client:
            return "⚠️ Groq API client not initialized. Please check your API key."
        try:
            resp = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=config.GROQ_MODEL,
                temperature=temperature if temperature is not None else config.GROQ_TEMPERATURE,
                max_tokens=max_tokens or config.GROQ_MAX_TOKENS,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"❌ Error generating response: {str(e)}"

    @staticmethod
    def _today() -> str:
        from datetime import date
        return date.today().strftime("%d %B %Y")

    def clear_history(self) -> None:
        self.chat_history = []

    def get_history(self) -> List[Tuple[str, str]]:
        return self.chat_history


# Backward-compatible alias
PDFChatbot = CreditDecisioningEngine
