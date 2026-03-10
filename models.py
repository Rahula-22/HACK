import os
from typing import List, Optional
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

class VectorDatabase:
    """
    Manages the vector database for storing and retrieving document embeddings.
    Uses FAISS for efficient similarity search and HuggingFace embeddings.
    """
    
    def __init__(self, persist_directory: str = "data/vectorstore"):
        """
        Initialize the vector database.
        
        Args:
            persist_directory: Directory to save/load the vector database
        """
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'batch_size': 64, 'normalize_embeddings': False}
        )
        self.vectorstore: Optional[FAISS] = None
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
    def create_vectorstore(self, documents: List[Document]) -> None:
        """
        Create a new vector database from documents in batches with progress output.
        
        Args:
            documents: List of LangChain Document objects to embed
        """
        if not documents:
            raise ValueError("No documents provided to create vectorstore")

        BATCH = 100
        total = len(documents)
        print(f"Creating vectorstore with {total} documents (batch size {BATCH})...")

        # Build from first batch, then add subsequent batches
        first_batch = documents[:BATCH]
        print(f"  Embedding batch 1/{(total + BATCH - 1) // BATCH} ({len(first_batch)} docs)...")
        self.vectorstore = FAISS.from_documents(first_batch, self.embeddings)

        for start in range(BATCH, total, BATCH):
            batch = documents[start : start + BATCH]
            batch_num = start // BATCH + 1
            total_batches = (total + BATCH - 1) // BATCH
            print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} docs)...")
            self.vectorstore.add_documents(batch)

        self.save_vectorstore()
        print("Vectorstore created and saved successfully!")
        
    def add_documents(self, documents: List[Document]) -> None:
        """
        Add new documents to existing vectorstore.
        
        Args:
            documents: List of LangChain Document objects to add
        """
        if not documents:
            return
            
        if self.vectorstore is None:
            self.create_vectorstore(documents)
        else:
            print(f"Adding {len(documents)} documents to vectorstore...")
            self.vectorstore.add_documents(documents)
            self.save_vectorstore()
            print("Documents added successfully!")
    
    def load_vectorstore(self) -> bool:
        """
        Load existing vectorstore from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        index_path = os.path.join(self.persist_directory, "index.faiss")
        
        if os.path.exists(index_path):
            print("Loading existing vectorstore...")
            self.vectorstore = FAISS.load_local(
                self.persist_directory, 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            print("Vectorstore loaded successfully!")
            return True
        else:
            # No print - this is normal on first run
            return False
    
    def save_vectorstore(self) -> None:
        """Save the vectorstore to disk."""
        if self.vectorstore is not None:
            self.vectorstore.save_local(self.persist_directory)
            
    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """Semantic similarity search (pure vector)."""
        if self.vectorstore is None:
            return []
        return self.vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 10) -> List[Document]:
        """
        Stage 5 — Hybrid Retrieval.

        Combines:
          1. Semantic similarity via FAISS (pulls 3× candidates for re-ranking)
          2. Keyword-based boosting  (query ∩ document keyword overlap)
          3. Priority boosting       (financial chunks and table chunks ranked higher)

        Scoring weights:
          +3  chunk_type == 'table'
          +2  priority   == 'high'
          +1  is_financial == True
          +1  per shared financial keyword between query and document
        """
        if self.vectorstore is None:
            return []

        _FIN_KW = [
            "revenue", "turnover", "profit", "ebitda", "debt", "borrowings",
            "interest", "assets", "liabilities", "cash", "expenditure",
            "income", "balance sheet", "profit and loss", "net worth",
            "depreciation", "working capital", "capex",
        ]

        # Over-fetch for re-ranking
        candidates = self.vectorstore.similarity_search(query, k=min(k * 3, 60))
        query_lower = query.lower()

        scored: List[tuple] = []
        for doc in candidates:
            score = 0
            if doc.metadata.get("chunk_type") == "table":
                score += 3
            if doc.metadata.get("priority") == "high":
                score += 2
            if doc.metadata.get("is_financial"):
                score += 1
            doc_lower = doc.page_content.lower()
            for kw in _FIN_KW:
                if kw in query_lower and kw in doc_lower:
                    score += 1
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:k]]
    
    def clear_vectorstore(self) -> None:
        """Clear the vector database."""
        self.vectorstore = None
        # Remove files from persist directory
        if os.path.exists(self.persist_directory):
            for file in os.listdir(self.persist_directory):
                file_path = os.path.join(self.persist_directory, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        print("Vectorstore cleared!")
