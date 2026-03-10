"""
FinancialExtractor — Stages 6, 7, 8.

Stage 6: Structured LLM Extraction
    — Returns strict JSON with value + page + snippet for each financial field.
Stage 7: Financial Validation Layer
    — Computes Debt/EBITDA and Interest Coverage; flags breaches with thresholds.
Stage 8: Explainability
    — Every extracted number is traceable to page number, source file, and raw snippet.
"""

import json
import os
import re
from typing import Dict, List, Optional

from langchain_core.documents import Document


class FinancialExtractor:
    """
    Extracts structured financial data from retrieved document chunks,
    validates it against risk thresholds, and provides full traceability.
    """

    # ── Stage 6: fields to extract ────────────────────────────────────────────
    FIELDS = [
        "revenue",
        "net_profit",
        "ebitda",
        "total_debt",
        "interest_expense",
        "total_assets",
        "total_liabilities",
        "cash_flow",
    ]

    # Empty template for fallback
    EMPTY_RESULT: Dict = {
        f: {"value": None, "page": None, "snippet": None} for f in FIELDS
    }

    # ── Stage 7: risk rules ────────────────────────────────────────────────────
    RISK_RULES = [
        {
            "name": "debt_to_ebitda",
            "label": "High Leverage",
            "numerator": "total_debt",
            "denominator": "ebitda",
            "threshold": 5.0,
            "direction": "above",
            "detail_tpl": (
                "Debt/EBITDA = {ratio:.2f}x exceeds safe threshold of 5.0x. "
                "High leverage increases refinancing and default risk."
            ),
        },
        {
            "name": "interest_coverage",
            "label": "Weak Interest Coverage",
            "numerator": "ebitda",
            "denominator": "interest_expense",
            "threshold": 1.5,
            "direction": "below",
            "detail_tpl": (
                "ICR = {ratio:.2f}x is below the minimum threshold of 1.5x. "
                "Insufficient earnings to comfortably service interest."
            ),
        },
    ]

    def __init__(self, groq_client, groq_model: str):
        self.groq_client = groq_client
        self.groq_model = groq_model

    # ─── Stage 6: Structured Extraction ──────────────────────────────────────

    def extract(self, context_docs: List[Document]) -> Dict:
        """
        Stage 6 — Call the LLM with a strict schema and return per-field
        {value, page, snippet} dicts.
        """
        if not context_docs:
            return dict(self.EMPTY_RESULT)

        context = self._build_traceable_context(context_docs)
        schema = dict(self.EMPTY_RESULT)

        prompt = f"""You are a financial data extractor for Indian corporate credit analysis.

Extract the following financial figures from the document excerpts provided.

STRICT RULES:
1. Extract numbers EXACTLY as written — do NOT convert or normalise units.
2. Prefer values from the most recent financial year.
3. "page" must be an integer matching the page number in the excerpt header.
4. "snippet" must be the exact sentence or table row that contains the value (≤120 chars).
5. Do NOT estimate, infer, or calculate any value.
6. Set all three sub-fields to null when a field cannot be found.
7. Return ONLY a single valid JSON object — no markdown fences, no commentary.

Fields to extract: revenue, net_profit, ebitda, total_debt, interest_expense,
total_assets, total_liabilities, cash_flow.

JSON schema (fill in values):
{json.dumps(schema, indent=2)}

Document Excerpts:
{context}"""

        raw = self._call_groq(prompt, max_tokens=1500, temperature=0.0)
        return self._parse_json(raw, schema)

    # ─── Stage 7: Validation ──────────────────────────────────────────────────

    def validate(self, extracted: Dict) -> Dict:
        """
        Stage 7 — Compute Debt/EBITDA and Interest Coverage ratios.
        Append a risk flag for each threshold breach.
        Returns {"ratios": {...}, "risk_flags": [...]}.
        """
        ratios: Dict[str, float] = {}
        risk_flags: List[Dict] = []

        for rule in self.RISK_RULES:
            num = self._numeric(extracted, rule["numerator"])
            den = self._numeric(extracted, rule["denominator"])
            if num is None or den is None or den == 0:
                continue
            ratio = round(num / den, 2)
            ratios[rule["name"]] = ratio
            breached = (
                rule["direction"] == "above" and ratio > rule["threshold"]
            ) or (
                rule["direction"] == "below" and ratio < rule["threshold"]
            )
            if breached:
                risk_flags.append(
                    {
                        "flag": rule["label"],
                        "ratio_name": rule["name"],
                        "computed_value": ratio,
                        "threshold": rule["threshold"],
                        "detail": rule["detail_tpl"].format(ratio=ratio),
                    }
                )

        return {"ratios": ratios, "risk_flags": risk_flags}

    # ─── Stage 8: Full Explainability Report ─────────────────────────────────

    def build_report(self, context_docs: List[Document]) -> Dict:
        """
        Stages 6 + 7 + 8.

        Returns:
        {
            "extracted_financials": { field: {value, page, snippet} },
            "validation":           { "ratios": {...}, "risk_flags": [...] },
            "traceability":         { field: {value, page, snippet, source_file} },
            "source_docs_used":     int
        }
        """
        extracted = self.extract(context_docs)
        validation = self.validate(extracted)

        # Stage 8: build per-field source traceability
        traceability: Dict = {}
        for field, data in extracted.items():
            if not isinstance(data, dict) or data.get("value") is None:
                continue
            page_ref = str(data.get("page", ""))
            # Find the source file for this page
            source_file = next(
                (
                    os.path.basename(d.metadata.get("source", ""))
                    for d in context_docs
                    if str(d.metadata.get("page", "")) == page_ref
                ),
                None,
            )
            traceability[field] = {
                "value": data["value"],
                "page": data.get("page"),
                "snippet": data.get("snippet"),
                "source_file": source_file,
            }

        return {
            "extracted_financials": extracted,
            "validation": validation,
            "traceability": traceability,
            "source_docs_used": len(context_docs),
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _build_traceable_context(self, docs: List[Document]) -> str:
        """Format docs with explicit [Page X | Section | TABLE] headers."""
        parts: List[str] = []
        for doc in docs:
            page = doc.metadata.get("page", "N/A")
            section = doc.metadata.get("section", "")
            is_table = doc.metadata.get("chunk_type") == "table"
            tag = f"Page {page}"
            if section:
                tag += f" | {section}"
            if is_table:
                tag += " | TABLE"
            parts.append(f"[{tag}]\n{doc.page_content}")
        return "\n---\n".join(parts)

    def _numeric(self, extracted: Dict, field: str) -> Optional[float]:
        """Parse a numeric value from a field entry, stripping Indian currency symbols."""
        entry = extracted.get(field, {})
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val is None:
            return None
        try:
            cleaned = re.sub(r"[₹,\s]", "", str(val))
            # Strip common Indian unit suffixes (do NOT scale — just remove label)
            cleaned = re.sub(
                r"(?i)\s*(cr(ore)?|lakh?|lac|mn|million|bn|billion)\s*$", "", cleaned
            )
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _parse_json(self, raw: str, default: Dict) -> Dict:
        """Extract the first JSON object from raw LLM output."""
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return dict(default)

    def _call_groq(
        self, prompt: str, max_tokens: int = 1500, temperature: float = 0.0
    ) -> str:
        try:
            resp = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.groq_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception:
            return ""
