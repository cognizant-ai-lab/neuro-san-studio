import React, { useState, useEffect, useRef } from "react";
import ErrorBoundary from "./ErrorBoundary";
import { io } from "socket.io-client";
import Spinner from "./common/Spinner";
import ErrorBanner from "./common/ErrorBanner";
// Inline lightweight components to avoid extra deps/files in this pass
const UploadGraph = ({ data = [], width = 560, height = 72 }) => {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const cvs = ref.current; if (!cvs) return;
    const ctx = cvs.getContext('2d');
    ctx.clearRect(0,0,width,height);
    ctx.fillStyle = 'rgba(255,255,255,0.04)';
    for (let x=0; x<width; x+=30) ctx.fillRect(x, 0, 1, height);
    for (let y=0; y<height; y+=15) ctx.fillRect(0, y, width, 1);
    if (!data.length) return;
    const t0 = data[0].t; const t1 = data[data.length-1].t; const dt = Math.max(1, t1 - t0);
    const pad = 4;
    ctx.beginPath();
    data.forEach((p, i) => {
      const x = pad + (width - pad*2) * ((p.t - t0) / dt);
      const y = pad + (height - pad*2) * (1 - p.v/100);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    const grad = ctx.createLinearGradient(0,0,width,0);
    grad.addColorStop(0, 'rgba(0,229,255,0.9)'); grad.addColorStop(1, 'rgba(0,200,255,0.5)');
    ctx.strokeStyle = grad; ctx.lineWidth = 2; ctx.shadowColor = 'rgba(0,229,255,0.6)'; ctx.shadowBlur = 8; ctx.stroke();
    const last = data[data.length-1]; const lastX = pad + (width - pad*2) * ((last.t - t0)/dt);
    ctx.lineTo(lastX, height - pad); ctx.lineTo(pad, height - pad); ctx.closePath();
    const fill = ctx.createLinearGradient(0,0,0,height);
    fill.addColorStop(0, 'rgba(0,229,255,0.18)'); fill.addColorStop(1, 'rgba(0,229,255,0.02)');
    ctx.fillStyle = fill; ctx.fill();
  }, [data, width, height]);
  return <canvas ref={ref} width={width} height={height} style={{ width, height, display:'block', borderRadius:8, background:'rgba(255,255,255,0.02)' }} aria-label="Upload progress graph" role="img"/>;
};

const VirtualList = ({ items = [], itemHeight = 28, height = 196, renderItem, overscan = 8 }) => {
  const [scrollTop, setScrollTop] = React.useState(0);
  const onScroll = (e) => setScrollTop(e.currentTarget.scrollTop);
  const total = items.length;
  const viewport = Math.max(1, Math.floor(height / itemHeight));
  const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const end = Math.min(total, start + viewport + overscan * 2);
  const topPad = start * itemHeight;
  const visible = React.useMemo(() => items.slice(start, end), [items, start, end]);
  return (
    <div onScroll={onScroll} style={{ overflowY: 'auto', height: `${height}px` }}>
      <div style={{ height: `${total * itemHeight}px`, position: 'relative' }}>
        <div style={{ position: 'absolute', top: `${topPad}px`, left: 0, right: 0 }}>
          {visible.map((item, i) => (
            <div key={item.id || i} style={{ height: `${itemHeight}px` }}>
              {renderItem(item, start + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

function UploadSection() {
  const inputRef = React.useRef();
  const pausedRef = React.useRef(false);
  const graphRef = useRef({ start: Date.now(), points: [] });
  const [tree, setTree] = useState([]);
  const [prog,setProg] = useState(0);
  const [vecProg,setVecProg] = useState(0);
  const [kgProg,setKgProg] = useState(0);
  const [neoProg,setNeoProg] = useState(0);
  const [current,setCurrent] = useState('');
  const [jobs, setJobs] = useState([]); // [{id, name, state}]
  const [trend, setTrend] = useState([]); // [{t, v}]
  const [source,setSource] = useState('user');
  const [filter,setFilter] = useState('all');
  const [redaction,setRedaction] = useState(false);
  const [paused,setPaused] = useState(false);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState(null);
  const togglePrivilege = (id, privileged) => {
    const reviewer = prompt('Reviewer (optional):') || '';
    const reason = prompt('Reason (optional):') || '';
    setLoading(true);
    setError(null);
    fetch(`/api/privilege/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ privileged, reviewer, reason })
    })
      .then(fetchFiles)
      .catch(e => {
        setError(e.message || 'Privilege update failed');
        setLoading(false);
      });
  };
  useEffect(() => {
    const s = io('/ws/upload', { transports: ["websocket"] });
    s.on('upload_progress', (ev) => {
      if (!ev || !ev.job_id) return;
      // Event-driven updates are supplemental; polling remains the source of truth
    });
    return () => s.disconnect();
  }, []);

  useEffect(() => {
    let raf;
    const tick = () => {
      const now = Date.now();
      const total = jobs.length || 1;
      const done = jobs.filter(j => j.state === 'done').length;
      const v = total ? Math.round((done / total) * 100) : 0;
      const pts = graphRef.current.points;
      pts.push({ t: now, v });
      const cutoff = now - 60000;
      graphRef.current.points = pts.filter(p => p.t >= cutoff);
      setTrend([...graphRef.current.points]);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [jobs]);

  const upload = async () => {
    const files = Array.from(inputRef.current.files);
    if (!files.length) return;
    let uploaded = 0;
    pausedRef.current = false;
    setPaused(false);
    const jobIds = [];
    for (let i = 0; i < files.length; i += 10) {
      while (pausedRef.current) {
        await new Promise(r=>setTimeout(r,200));
      }
      const batch = files.slice(i, i + 10);
      setCurrent(batch[0]?.name || '');
      const fd = new FormData();
      batch.forEach(f => fd.append('files', f, f.webkitRelativePath || f.name));
      fd.append('source', source);
      fd.append('redaction', redaction ? 'true' : 'false');
      const resp = await fetch('/api/upload', { method: 'POST', body: fd });
      let data = {};
      try { data = await resp.json(); } catch {}
      const accepted = (data?.data?.accepted) || [];
      const busy = !!(data?.meta?.busy);
      const newEntries = accepted.map((id)=>({ id, name: batch.find(f=>true)?.name || 'file', state: 'queued' }));
      setJobs(prev => [...prev, ...newEntries]);
      jobIds.push(...accepted);
      if (busy) {
        // Server signaled backpressure; wait briefly before next batch
        await new Promise(r=>setTimeout(r, 2000));
      }
    }
    // Poll status until all jobs complete
    const pending = new Set(jobIds);
    while (pending.size) {
      const qs = Array.from(pending).map(id => 'job_id='+encodeURIComponent(id)).join('&');
      try {
        const r = await fetch('/api/upload/status?'+qs);
        const j = await r.json();
        const payload = j?.data || {};
        let doneCount = 0;
        const updates = [];
        for (const [id, st] of Object.entries(payload)) {
          if (st && (st.state === 'done' || st.state === 'unknown')) pending.delete(id);
          if (st && st.state) updates.push({ id, state: st.state });
        }
        if (updates.length) {
          setJobs(prev => prev.map(j => {
            const u = updates.find(x => x.id === j.id);
            return u ? { ...j, state: u.state } : j;
          }));
        }
        doneCount = jobIds.length - pending.size;
        const pct = Math.round((doneCount / jobIds.length) * 100);
        setProg(pct); setVecProg(pct); setKgProg(pct); setNeoProg(pct);
      } catch {}
      await new Promise(r=>setTimeout(r, 1000));
    }
    setCurrent(''); setProg(0); setVecProg(0); setKgProg(0); setNeoProg(0);
    pausedRef.current = false; setPaused(false);
    fetchFiles(); window.dispatchEvent(new Event('graphRefresh'));
  };
  const fetchFiles = () => {
    setLoading(true);
    setError(null);
    fetch('/api/files')
      .then(r=>r.json())
      .then(d=>setTree(d.data||[]))
      .catch(e=>setError(e.message || 'Failed to load files'))
      .finally(()=>setLoading(false));
  };
  const exportAll = () => { window.open('/api/export', '_blank'); };
  const organize = () => {
    setLoading(true);
    setError(null);
    fetch('/api/organized-files')
      .then(r=>r.json())
      .then(d=>setTree(d.data||[]))
      .catch(e=>setError(e.message || 'Failed to organize files'))
      .finally(()=>setLoading(false));
  };
  const togglePause = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
  };
  useEffect(fetchFiles, []);
  const sourceClass = s => ({
    opp_counsel: 'text-red-400',
    court: 'text-yellow-400',
    user: 'text-blue-400'
  }[s] || 'text-blue-400');
  const renderNodes = nodes => nodes.map((n,i)=> {
    if (n.children) {
      const kids = renderNodes(n.children).filter(Boolean);
      if (!kids.length) return null;
      return (
        <li key={i} className="folder">
          <div className="folder-header" onClick={e=>e.currentTarget.parentNode.classList.toggle('open')}><i className="folder-icon fa fa-caret-right"></i>{n.name}</div>
          <div className="folder-contents"><ul>{kids}</ul></div>
        </li>
      );
    }
    if (filter !== 'all' && n.source !== filter) return null;
    return (
      <li
        key={i}
        className={`file ${n.privileged ? 'privileged' : ''} ${sourceClass(n.source)}`}
        onClick={() => window.open('/uploads/'+n.path,'_blank')}
        title={n.sha256 ? `SHA256: ${n.sha256}` : ''}
      >
        {n.name}
        {n.privileged && <i className="fa fa-user-secret ml-1" />}
        {n.sha256 && <span className="ml-2 text-xs text-gray-400">{n.sha256.slice(0,8)}</span>}
        {n.id && (
          <button
            className="button-secondary ml-2 text-xs"
            onClick={e => {e.stopPropagation(); togglePrivilege(n.id, !n.privileged);}}
          >
            {n.privileged ? 'Mark Public' : 'Mark Privileged'}
          </button>
        )}
      </li>
    );
  });
  return (
    <ErrorBoundary>
      <section className="card">
        <h2>Upload</h2>
      <input type="file" ref={inputRef} className="mb-3" webkitdirectory="" directory="" multiple />
      <div className="flex flex-wrap gap-2 mb-3">
        <select value={source} onChange={e=>setSource(e.target.value)} className="px-2 py-1 bg-gray-800 border border-gray-600 rounded">
          <option value="user">User</option>
          <option value="opp_counsel">Opposing Counsel</option>
          <option value="court">Court</option>
        </select>
        <select value={filter} onChange={e=>setFilter(e.target.value)} className="px-2 py-1 bg-gray-800 border border-gray-600 rounded">
          <option value="all">All Sources</option>
          <option value="user">User</option>
          <option value="opp_counsel">Opposing Counsel</option>
          <option value="court">Court</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={redaction} onChange={e=>setRedaction(e.target.checked)} />
          Enable Redaction
        </label>
        <button className="button-primary" onClick={upload}><i className="fa fa-upload mr-1"></i>Upload</button>
        <button className="button-secondary" onClick={exportAll}><i className="fa fa-file-export mr-1"></i>Export All</button>
        <button className="button-secondary" onClick={organize}><i className="fa fa-folder-tree mr-1"></i>Organize</button>
        {prog>0 && (
          <button className="button-secondary" onClick={togglePause}>
            <i className={`fa fa-${paused?'play':'pause'} mr-1`}></i>
            {paused ? 'Resume' : 'Pause'}
          </button>
        )}
      </div>
      {loading && <Spinner />}
      {error && <ErrorBanner message={error} />}
      {prog>0 && (
        <>
          <progress value={prog} max="100" className="w-full mb-2"></progress>
          {current && <p className="text-xs mb-2">Uploading: {current}</p>}
          <div className="mb-2">
            <p className="text-xs">Vector DB</p>
            <progress value={vecProg} max="100" className="w-full"></progress>
          </div>
          <div className="mb-2">
            <p className="text-xs">Knowledge DB</p>
            <progress value={kgProg} max="100" className="w-full"></progress>
          </div>
          <div className="mb-2">
            <p className="text-xs">Neo4j Graph</p>
            <progress value={neoProg} max="100" className="w-full"></progress>
          </div>
        </>
      )}
      {jobs.length>0 && (
        <div className="mb-3" role="status" aria-live="polite">
          <div className="mb-2"><UploadGraph data={trend} width={560} height={72} /></div>
          <VirtualList
            items={jobs}
            itemHeight={28}
            height={196}
            overscan={8}
            renderItem={(j)=> (
              <div className="flex items-center justify-between bg-gray-900/40 px-2 rounded border border-gray-700">
                <span className="truncate" title={j.name}>{j.name}</span>
                <span className={`px-2 py-0.5 rounded text-gray-900 ${j.state==='done'?'bg-green-400': j.state==='vectored'?'bg-blue-300': j.state==='redacted'?'bg-purple-300': 'bg-yellow-300'}`}>{j.state}</span>
              </div>
            )}
          />
        </div>
      )}
      <div className="folder-tree text-sm"><ul>{renderNodes(tree)}</ul></div>
      </section>
    </ErrorBoundary>
  );
}

export default UploadSection;
