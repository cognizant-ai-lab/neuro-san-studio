import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom';
import { AppProvider } from './AppContext';
import Dashboard from './Dashboard';
import tokens from '../figma_tokens.json';
import { applyDesignTokens } from './theme';
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
      <BrowserRouter>
        <Routes>
          <Route path="/present/:mode/*" element={<DocumentViewerWrapper />} />
          <Route path="/*" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  </React.StrictMode>
);
