import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom';
import { AppProvider } from './AppContext';
import Dashboard from './Dashboard';
import tokens from '../figma_tokens.json';
import { applyDesignTokens } from './theme';
import { ToasterProvider } from './components/common/Toaster';
try {
  const TOKENS_CSS = `:root{--color-bg:#000;--color-bg-alt:#0b0f1a;--color-surface:rgba(15,23,42,0.6);--color-surface-hover:rgba(31,38,45,0.75);--color-accent:#00e5ff;--color-text:#e5e7eb;--color-text-muted:#9ca3af;--color-border:rgba(255,255,255,0.08);--color-accent-glow:#00e5ff;--glass-blur:12px;--font-base:Rajdhani,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,Arial,sans-serif;--font-size-sm:.875rem;--font-size-md:1rem;--font-size-lg:1.125rem;--font-weight-normal:400;--font-weight-bold:700;--space-xs:.25rem;--space-sm:.5rem;--space-md:1rem;--space-lg:1.5rem}html,body,#root{height:100%}body{margin:0;background:radial-gradient(1200px 800px at 20% -10%,rgba(0,229,255,.08),transparent),radial-gradient(1000px 600px at 120% 10%,rgba(0,229,255,.06),transparent),var(--color-bg);color:var(--color-text);font-family:var(--font-base)}.dashboard-grid{display:grid;grid-template-rows:auto 1fr;gap:var(--space-md);padding:var(--space-md)}.tab-buttons{display:flex;gap:var(--space-sm);align-items:center}.tab-button{background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.02));color:var(--color-text);border:1px solid var(--color-border);padding:.4rem .8rem;border-radius:10px;backdrop-filter:blur(var(--glass-blur));box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 10px 20px rgba(0,0,0,.25);transition:transform 120ms ease,background 200ms ease,box-shadow 200ms ease;text-decoration:none;display:inline-flex;align-items:center}.tab-button:hover{transform:translateY(-1px);background:var(--color-surface-hover)}.tab-button.active{border-color:var(--color-accent);box-shadow:0 0 0 1px var(--color-accent),0 0 16px rgba(0,229,255,.2)}.tab-panels{min-height:60vh}.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:var(--space-md)}.card{background:var(--color-surface);border:1px solid var(--color-border);border-radius:16px;padding:var(--space-md);box-shadow:0 10px 30px rgba(0,0,0,.25),0 0 0 1px rgba(255,255,255,.03) inset;backdrop-filter:blur(var(--glass-blur))}.network-card{border:1px solid var(--color-border);border-radius:12px;background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,.01));padding:var(--space-sm)}.button-primary,.button-secondary{cursor:pointer;padding:.5rem .9rem;border-radius:10px;border:1px solid var(--color-border);transition:transform 120ms ease,box-shadow 200ms ease,background 200ms ease}.button-primary{background:linear-gradient(180deg,var(--color-accent),color-mix(in oklab,var(--color-accent),black 12%));color:#081013;box-shadow:0 8px 24px rgba(0,229,255,.25),0 0 0 1px rgba(0,229,255,.4) inset}.button-primary:hover{transform:translateY(-1px);box-shadow:0 10px 28px rgba(0,229,255,.33),0 0 0 1px rgba(0,229,255,.55) inset}.button-secondary{background:var(--color-surface-hover);color:var(--color-text)}.button-secondary:hover{transform:translateY(-1px)}input,select,textarea{background:var(--color-bg-alt);color:var(--color-text);border:1px solid var(--color-border);border-radius:10px}progress{width:100%;height:8px;-webkit-appearance:none;appearance:none}progress::-webkit-progress-bar{background:rgba(255,255,255,.05);border-radius:999px}progress::-webkit-progress-value{background:var(--color-accent);border-radius:999px}`;
  const s = document.createElement('style'); s.textContent = TOKENS_CSS; document.head.appendChild(s);
} catch {}
import './tokens.css';
import DocumentViewer from './components/DocumentViewer';

const API_BASE = __API_BASE__ || '';
const originalFetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return originalFetch(API_BASE + input, init);
  }
  return originalFetch(input, init);
};

function DocumentViewerWrapper() {
  const { mode, '*': docId } = useParams();
  return <DocumentViewer mode={mode} docId={decodeURIComponent(docId)} />;
}

const root = document.getElementById('root');
// Apply design tokens to CSS variables at startup
try { applyDesignTokens(tokens); } catch {}
ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <AppProvider>
      <ToasterProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/present/:mode/*" element={<DocumentViewerWrapper />} />
            <Route path="/*" element={<Dashboard />} />
          </Routes>
        </BrowserRouter>
      </ToasterProvider>
    </AppProvider>
  </React.StrictMode>
);
