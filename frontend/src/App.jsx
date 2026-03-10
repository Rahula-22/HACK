import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Send, FileText, CheckCircle, AlertCircle, Loader2, X, Menu,
  Upload, Trash2, RefreshCw, Database, BarChart2, FileCheck,
  TrendingUp, Building2, ChevronDown, ChevronUp, Download
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const API_BASE = 'http://localhost:8000';

// ─── Utility ──────────────────────────────────────────────────────────────────

const SUPPORTED_EXTS = ['.pdf', '.csv', '.xlsx', '.xls', '.txt'];
const isSupported = (name) => SUPPORTED_EXTS.some(e => name.toLowerCase().endsWith(e));

const fileIcon = (name) => {
  if (name.endsWith('.pdf')) return '📄';
  if (name.endsWith('.csv') || name.endsWith('.xlsx') || name.endsWith('.xls')) return '📊';
  return '📝';
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function Notification({ notification }) {
  if (!notification) return null;
  return (
    <div className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 transition-all
      ${notification.type === 'error' ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
      {notification.type === 'error' ? <AlertCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
      {notification.message}
    </div>
  );
}

function MetricCard({ label, value, benchmark, status }) {
  const color = status === 'good' ? 'text-emerald-400' : status === 'warn' ? 'text-amber-400' : 'text-slate-300';
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value ?? '—'}</p>
      {benchmark && <p className="text-xs text-slate-500 mt-1">Benchmark: {benchmark}</p>}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  /* ── State ── */
  const [tab, setTab] = useState('chat');           // 'chat' | 'cam' | 'insights'
  const [showSidebar, setShowSidebar] = useState(false);
  const [notification, setNotification] = useState(null);
  const [status, setStatus] = useState(null);

  // Documents
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Chat
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // CAM form
  const [camForm, setCamForm] = useState({
    company_name: '', loan_amount: '', loan_purpose: '', loan_tenor: ''
  });
  const [camLoading, setCamLoading] = useState(false);
  const [camResult, setCamResult] = useState('');
  const [camExpanded, setCamExpanded] = useState(true);

  // Financial insights
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(false);

  /* ── Lifecycle ── */
  useEffect(() => { fetchStatus(); fetchDocuments(); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  /* ── Helpers ── */
  const notify = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3500);
  };

  async function fetchStatus() {
    try { setStatus((await axios.get(`${API_BASE}/api/status`)).data); } catch { }
  }

  async function fetchDocuments() {
    try {
      const res = await axios.get(`${API_BASE}/api/list-documents`);
      setDocuments(res.data.documents || []);
    } catch { }
  }

  /* ── Document upload ── */
  async function handleFileUpload(e) {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true);
    let ok = 0;
    for (const file of files) {
      if (!isSupported(file.name)) { notify(`${file.name} — unsupported type`, 'error'); continue; }
      try {
        const fd = new FormData();
        fd.append('file', file);
        await axios.post(`${API_BASE}/api/upload-document`, fd);
        ok++;
      } catch (err) { notify(`Failed: ${file.name}`, 'error'); }
    }
    setUploading(false);
    if (ok) { notify(`${ok} file(s) uploaded`); await fetchDocuments(); await fetchStatus(); }
    e.target.value = '';
  }

  async function handleProcess() {
    if (!documents.length) { notify('Upload documents first', 'error'); return; }
    setProcessing(true);
    try {
      const res = await axios.post(`${API_BASE}/api/process-documents`);
      notify(res.data.message || 'Knowledge base built');
      await fetchStatus();
    } catch (err) { notify('Processing failed: ' + err.message, 'error'); }
    finally { setProcessing(false); }
  }

  async function handleClearKB() {
    if (!window.confirm('Clear the knowledge base? You will need to re-process documents.')) return;
    try {
      await axios.delete(`${API_BASE}/api/clear-knowledge-base`);
      notify('Knowledge base cleared');
      await fetchStatus();
    } catch (err) { notify('Failed: ' + err.message, 'error'); }
  }

  /* ── Chat ── */
  async function handleSendChat(e) {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput('');
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setChatLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/api/chat`, { message: msg });
      setMessages(prev => [...prev, {
        role: 'assistant', content: res.data.response, sources: res.data.sources
      }]);
    } catch (err) { notify('Error: ' + err.message, 'error'); }
    finally { setChatLoading(false); }
  }

  /* ── CAM ── */
  async function handleGenerateCAM(e) {
    e.preventDefault();
    if (!camForm.company_name || !camForm.loan_amount || !camForm.loan_purpose) {
      notify('Fill in Company Name, Loan Amount and Purpose', 'error'); return;
    }
    setCamLoading(true);
    setCamResult('');
    try {
      const res = await axios.post(`${API_BASE}/api/generate-cam`, camForm);
      setCamResult(res.data.cam);
      setCamExpanded(true);
    } catch (err) { notify('CAM generation failed: ' + err.message, 'error'); }
    finally { setCamLoading(false); }
  }

  function downloadCAM() {
    const blob = new Blob([camResult], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CAM_${camForm.company_name.replace(/\s+/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ── Financial insights ── */
  async function handleExtractMetrics() {
    setMetricsLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/api/extract-financials`);
      setMetrics(res.data.metrics || {});
    } catch (err) { notify('Extraction failed: ' + err.message, 'error'); }
    finally { setMetricsLoading(false); }
  }

  function ratioStatus(key, val) {
    if (!val || val === 'null') return 'neutral';
    const n = parseFloat(val);
    if (isNaN(n)) return 'neutral';
    if (key === 'current_ratio') return n >= 1.33 ? 'good' : 'warn';
    if (key === 'dscr') return n >= 1.25 ? 'good' : 'warn';
    if (key === 'interest_coverage_ratio') return n >= 2 ? 'good' : 'warn';
    if (key === 'debt_equity_ratio') return n <= 3 ? 'good' : 'warn';
    return 'neutral';
  }

  /* ── Render ── */
  const kbLoaded = status?.knowledge_base_loaded;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <Notification notification={notification} />

      {/* ── Sidebar ───────────────────────────────────────────────────── */}
      <aside className={`
        ${showSidebar ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0 fixed md:relative z-20 w-72 bg-slate-900
        border-r border-slate-800 h-full flex flex-col transition-transform duration-300
      `}>
        {/* Logo */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white leading-tight">Credit Decisioning</h1>
              <p className="text-xs text-slate-400">AI Engine · Indian Banks</p>
            </div>
          </div>
          <button onClick={() => setShowSidebar(false)} className="md:hidden text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* KB Status */}
        <div className={`px-4 py-3 border-b border-slate-800 flex items-center gap-3
          ${kbLoaded ? 'bg-emerald-950/40' : 'bg-amber-950/30'}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center
            ${kbLoaded ? 'bg-emerald-700' : 'bg-amber-700'}`}>
            <Database className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className={`text-xs font-semibold ${kbLoaded ? 'text-emerald-300' : 'text-amber-300'}`}>
              {kbLoaded ? 'Knowledge Base Ready' : 'No Knowledge Base'}
            </p>
            <p className={`text-xs ${kbLoaded ? 'text-emerald-500' : 'text-amber-500'}`}>
              {kbLoaded ? `${status.total_documents} document(s) indexed` : 'Upload & process below'}
            </p>
          </div>
        </div>

        {/* Document management */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Upload */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Upload Documents</p>
            <input ref={fileInputRef} type="file" multiple
              accept=".pdf,.csv,.xlsx,.xls,.txt" onChange={handleFileUpload} className="hidden" />
            <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
              className="w-full border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-xl p-4
                flex flex-col items-center gap-1 transition-colors disabled:opacity-50">
              {uploading
                ? <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                : <Upload className="w-5 h-5 text-blue-400" />}
              <span className="text-xs text-blue-400 font-medium">
                {uploading ? 'Uploading…' : 'Click to upload'}
              </span>
              <span className="text-xs text-slate-500">PDF · CSV · XLSX · TXT</span>
            </button>
          </div>

          {/* File list */}
          {documents.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Documents</p>
                <button onClick={fetchDocuments} className="text-slate-500 hover:text-slate-300">
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
              <ul className="space-y-1 max-h-44 overflow-y-auto pr-1">
                {documents.map((doc, i) => (
                  <li key={i} className="flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg text-xs">
                    <span>{fileIcon(doc)}</span>
                    <span className="truncate text-slate-300" title={doc}>{doc}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Process */}
          <button onClick={handleProcess}
            disabled={processing || uploading || !documents.length}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40
              text-white rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors">
            {processing
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Building…</>
              : <><Database className="w-4 h-4" /> Build Knowledge Base</>}
          </button>

          {kbLoaded && (
            <button onClick={handleClearKB}
              className="w-full py-2 border border-red-800 text-red-400 hover:bg-red-950 rounded-xl
                text-xs font-medium flex items-center justify-center gap-1 transition-colors">
              <Trash2 className="w-3 h-3" /> Clear Knowledge Base
            </button>
          )}

          {documents.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-2">
              Upload financial documents to get started — Annual Reports, CMA Data, Due Diligence Notes, Balance Sheets.
            </p>
          )}
        </div>

        <div className="p-3 border-t border-slate-800 text-center">
          <p className="text-xs text-slate-600">Powered by Groq · FAISS · LangChain</p>
        </div>
      </aside>

      {/* ── Main ──────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Top bar */}
        <header className="bg-slate-900 border-b border-slate-800 px-5 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setShowSidebar(s => !s)}
              className="md:hidden text-slate-400 hover:text-white">
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-white">AI Corporate Credit Decisioning Engine</h2>
            <span className="hidden sm:inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              Online
            </span>
          </div>

          {/* Tabs */}
          <div className="flex bg-slate-800 rounded-lg p-1 gap-1">
            {[
              { id: 'chat',     icon: <Send className="w-3.5 h-3.5" />,      label: 'Analyst Chat' },
              { id: 'cam',      icon: <FileCheck className="w-3.5 h-3.5" />, label: 'Generate CAM' },
              { id: 'insights', icon: <BarChart2 className="w-3.5 h-3.5" />, label: 'Financials' },
            ].map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                  ${tab === t.id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                {t.icon}{t.label}
              </button>
            ))}
          </div>
        </header>

        {/* ── Tab: Analyst Chat ── */}
        {tab === 'chat' && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center max-w-sm">
                    <div className="w-14 h-14 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Building2 className="w-7 h-7 text-white" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-1">Credit Analyst Ready</h3>
                    <p className="text-slate-400 text-sm mb-4">
                      Ask me about financial ratios, borrower risk, industry outlook, or any data in the uploaded documents.
                    </p>
                    <div className="space-y-2 text-xs text-left">
                      {[
                        'What is the DSCR of the borrower?',
                        'Summarise the revenue trend over last 3 years',
                        'What are the key credit risks identified?',
                        'Is the current ratio within acceptable limits?',
                      ].map((q, i) => (
                        <button key={i} onClick={() => setChatInput(q)}
                          className="w-full px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700
                            rounded-lg text-slate-300 text-left transition-colors">
                          {q}
                        </button>
                      ))}
                    </div>
                    {!kbLoaded && (
                      <p className="text-amber-400 text-xs mt-4">
                        ⚠ No knowledge base — upload and process documents first.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-3xl rounded-2xl px-5 py-4 shadow
                    ${msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-800 border border-slate-700 text-slate-100'}`}>
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-2 mb-2">
                        <div className="w-5 h-5 bg-blue-600 rounded-full flex items-center justify-center">
                          <Building2 className="w-3 h-3 text-white" />
                        </div>
                        <span className="text-xs font-semibold text-blue-300">Senior Credit Analyst</span>
                      </div>
                    )}
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    {msg.sources?.length > 0 && (
                      <details className="mt-3 pt-3 border-t border-slate-700">
                        <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-200">
                          📎 Sources ({msg.sources.length})
                        </summary>
                        <div className="mt-2 space-y-1">
                          {msg.sources.map((s, j) => (
                            <div key={j} className="text-xs text-slate-400 bg-slate-900 rounded-lg px-3 py-2">
                              <span className="font-medium text-slate-300">{s.source}</span>
                              {s.page !== 'N/A' && <span className="text-slate-500"> · p.{s.page}</span>}
                              <p className="text-slate-500 mt-0.5 leading-relaxed">{s.content}</p>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-slate-800 border border-slate-700 rounded-2xl px-5 py-4 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                    <span className="text-slate-400 text-sm">Analysing…</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSendChat}
              className="border-t border-slate-800 bg-slate-900 p-4">
              <div className="max-w-4xl mx-auto flex gap-3 items-end">
                <textarea
                  rows={1}
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendChat(e); } }}
                  placeholder="Ask a credit analysis question…"
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm
                    text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-blue-500
                    max-h-32 overflow-y-auto"
                  style={{ fieldSizing: 'content' }}
                />
                <button type="submit" disabled={!chatInput.trim() || chatLoading}
                  className="p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 rounded-xl transition-colors">
                  <Send className="w-4 h-4 text-white" />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── Tab: Generate CAM ── */}
        {tab === 'cam' && (
          <div className="flex-1 overflow-y-auto p-5">
            <div className="max-w-4xl mx-auto space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-blue-400" />
                  Credit Appraisal Memo Generator
                </h3>
                <p className="text-sm text-slate-400">
                  Fill in the loan details below. The engine will retrieve relevant financial data from uploaded documents
                  and auto-draft a full CAM for credit committee review.
                </p>
              </div>

              {!kbLoaded && (
                <div className="flex items-start gap-3 bg-amber-950/30 border border-amber-800 rounded-xl p-4 text-sm text-amber-300">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>No knowledge base found. Please upload and process financial documents first.</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleGenerateCAM}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                    Borrower / Company Name *
                  </label>
                  <input value={camForm.company_name} required
                    onChange={e => setCamForm(f => ({ ...f, company_name: e.target.value }))}
                    placeholder="e.g. Acme Industries Ltd."
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm
                      text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                    Proposed Facility Amount (₹) *
                  </label>
                  <input value={camForm.loan_amount} required
                    onChange={e => setCamForm(f => ({ ...f, loan_amount: e.target.value }))}
                    placeholder="e.g. 50 Crores"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm
                      text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                    Loan Tenor
                  </label>
                  <input value={camForm.loan_tenor}
                    onChange={e => setCamForm(f => ({ ...f, loan_tenor: e.target.value }))}
                    placeholder="e.g. 5 Years"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm
                      text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                    Purpose of the Facility *
                  </label>
                  <textarea rows={2} value={camForm.loan_purpose} required
                    onChange={e => setCamForm(f => ({ ...f, loan_purpose: e.target.value }))}
                    placeholder="e.g. Working Capital Requirement / Capex for plant expansion / Refinancing existing debt"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm
                      text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-blue-500" />
                </div>
                <div className="sm:col-span-2">
                  <button type="submit" disabled={camLoading}
                    className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold
                      rounded-xl flex items-center justify-center gap-2 transition-colors text-sm">
                    {camLoading
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating CAM…</>
                      : <><FileCheck className="w-4 h-4" /> Generate Credit Appraisal Memo</>}
                  </button>
                </div>
              </form>

              {/* CAM output */}
              {camResult && (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
                    <span className="text-sm font-semibold text-white flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-blue-400" />
                      Credit Appraisal Memo — {camForm.company_name}
                    </span>
                    <div className="flex items-center gap-2">
                      <button onClick={downloadCAM}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-white px-2 py-1
                          bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors">
                        <Download className="w-3 h-3" /> Download
                      </button>
                      <button onClick={() => setCamExpanded(v => !v)}
                        className="text-slate-400 hover:text-white">
                        {camExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                  {camExpanded && (
                    <div className="p-6 prose prose-invert prose-sm max-w-none overflow-x-auto">
                      <ReactMarkdown>{camResult}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Tab: Financial Insights ── */}
        {tab === 'insights' && (
          <div className="flex-1 overflow-y-auto p-5">
            <div className="max-w-4xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-blue-400" />
                    Financial Insights Extractor
                  </h3>
                  <p className="text-sm text-slate-400 mt-0.5">
                    Automatically extract key financial KPIs from uploaded documents.
                  </p>
                </div>
                <button onClick={handleExtractMetrics} disabled={metricsLoading || !kbLoaded}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40
                    text-white rounded-xl text-sm font-medium transition-colors">
                  {metricsLoading
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Extracting…</>
                    : <><BarChart2 className="w-4 h-4" /> Extract Metrics</>}
                </button>
              </div>

              {!kbLoaded && (
                <div className="flex items-start gap-3 bg-amber-950/30 border border-amber-800 rounded-xl p-4 text-sm text-amber-300">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>No knowledge base found. Upload and process documents first.</span>
                </div>
              )}

              {metrics && (
                <>
                  {/* Header info */}
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 grid grid-cols-3 gap-4">
                    {[
                      { label: 'Company', value: metrics.company_name },
                      { label: 'Financial Year', value: metrics.financial_year },
                      { label: 'Currency', value: metrics.currency },
                    ].map((item, i) => (
                      <div key={i}>
                        <p className="text-xs text-slate-500 mb-0.5">{item.label}</p>
                        <p className="text-sm font-semibold text-slate-200">{item.value ?? '—'}</p>
                      </div>
                    ))}
                  </div>

                  {/* Income metrics */}
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      Income Statement
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      <MetricCard label="Revenue / Net Sales" value={metrics.revenue} />
                      <MetricCard label="EBITDA" value={metrics.ebitda} />
                      <MetricCard label="EBITDA Margin" value={metrics.ebitda_margin_pct != null ? metrics.ebitda_margin_pct + '%' : null} />
                      <MetricCard label="Net Profit (PAT)" value={metrics.net_profit} />
                      <MetricCard label="PAT Margin" value={metrics.pat_margin_pct != null ? metrics.pat_margin_pct + '%' : null} />
                    </div>
                  </div>

                  {/* Balance sheet */}
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      Balance Sheet
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      <MetricCard label="Total Assets" value={metrics.total_assets} />
                      <MetricCard label="Net Worth" value={metrics.net_worth} />
                      <MetricCard label="Total Debt" value={metrics.total_debt} />
                    </div>
                  </div>

                  {/* Key ratios */}
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      Credit Ratios
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <MetricCard label="DSCR" value={metrics.dscr} benchmark="≥ 1.25x"
                        status={ratioStatus('dscr', metrics.dscr)} />
                      <MetricCard label="Current Ratio" value={metrics.current_ratio} benchmark="≥ 1.33x"
                        status={ratioStatus('current_ratio', metrics.current_ratio)} />
                      <MetricCard label="Debt / Equity" value={metrics.debt_equity_ratio} benchmark="≤ 3.0x"
                        status={ratioStatus('debt_equity_ratio', metrics.debt_equity_ratio)} />
                      <MetricCard label="Interest Coverage" value={metrics.interest_coverage_ratio} benchmark="≥ 2.0x"
                        status={ratioStatus('interest_coverage_ratio', metrics.interest_coverage_ratio)} />
                    </div>
                  </div>

                  <p className="text-xs text-slate-600">
                    * Metrics extracted from uploaded documents via AI. Verify against certified financials before credit decisions.
                  </p>
                </>
              )}

              {!metrics && !metricsLoading && kbLoaded && (
                <div className="text-center py-16 text-slate-500">
                  <BarChart2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Click "Extract Metrics" to auto-extract financial KPIs</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
