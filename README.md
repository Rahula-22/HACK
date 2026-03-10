# 🏦 AI Corporate Credit Decisioning Engine

A RAG (Retrieval-Augmented Generation) based AI assistant for Indian banks that analyses corporate financial documents and generates Credit Appraisal Memos (CAMs). Built with Python, Streamlit, and Groq AI.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B.svg)
![Groq](https://img.shields.io/badge/Groq-LLaMA--3.3--70B-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Features

- 🤖 **AI Credit Analyst**: Powered by Groq's LLaMA-3.3-70B for fast, accurate financial analysis
- 📚 **Document RAG**: Retrieves relevant context from uploaded corporate financial documents
- 📝 **CAM Generation**: Generates full Credit Appraisal Memos in one click
- 📊 **Financial Ratio Extraction**: Automatically identifies key ratios and risk indicators
- ⚡ **Fast Search**: FAISS vector database for millisecond similarity search
- 🔒 **Private**: Runs locally with your own Groq API key
- 📄 **Source Tracking**: Shows which documents were referenced for each answer

## 🏗️ Architecture

| Layer | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq (LLaMA-3.3-70B-Versatile) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector Store | FAISS |
| Document Parsing | LangChain + PyPDF |
| API (optional) | FastAPI |

## 📦 Installation & Setup

### Prerequisites
- Python 3.10+
- A free Groq API key from [console.groq.com](https://console.groq.com)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ugp.git
   cd ugp
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application**
   - Open `config.py` and add your Groq API key:
     ```python
     GROQ_API_KEY = "your_groq_api_key_here"
     ```
   - Alternatively, set the environment variable `GROQ_API_KEY`.

4. **Add your documents**
   - Place corporate financial PDFs (Annual Reports, CMA Data, Balance Sheets, Due Diligence Notes, Financial Statements) into the `data/` directory.

5. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```

6. **Open your browser**
   - Navigate to `http://localhost:8501`

## 📄 Usage

1. **Configure API Key**
   - Enter your Groq API key in the sidebar if not set in `config.py`.

2. **Load / Process Documents**
   - Place PDFs in the `data/` folder. On first launch, documents are processed automatically and a FAISS vector store is built.
   - You can also upload and process documents directly from the sidebar.

3. **Ask Questions**
   - Type financial analysis questions in the chat input (e.g., *"What is the debt-to-equity ratio?"*, *"Summarise the company's revenue trend over 3 years"*).

4. **Generate a CAM**
   - Click the **Generate CAM** button to produce a full Credit Appraisal Memo from the loaded documents.

## 🗂️ Project Structure

```
├── app.py                  # Streamlit UI entry point
├── api.py                  # FastAPI backend (optional)
├── chatbot.py              # RAG chatbot logic
├── document_processor.py   # PDF ingestion & chunking
├── models.py               # Pydantic / data models
├── config.py               # Configuration settings
├── config.example.py       # Example configuration template
├── process_documents.py    # Standalone document processing script
├── requirements.txt
├── data/
│   └── vectorstore/        # FAISS index (auto-generated)
└── frontend/               # React frontend (optional)
```

## 🛠️ Development

- Use `git` for version control and create a new branch for each feature or bugfix.
- Follow PEP 8 for Python code style.
- Write clear, concise commit messages.
- Submit a pull request for review.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Acknowledgments

- Built to streamline credit decisioning workflows for Indian banking institutions
- Powered by [Groq](https://groq.com) and [LangChain](https://langchain.com)
- Built with ❤️ by [Rahul Ahirwar](https://github.com/Rahula-22)
- Special thanks to the contributors and supporters of this project

