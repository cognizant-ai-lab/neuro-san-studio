import React, { useState, useEffect, useRef } from "react";
import { fetchJSON } from "../utils";
import { io } from "socket.io-client";
function PipelineSection() {
  const [metrics,setMetrics] = useState({files:0,vectors:0,graph:0,tasks:0,logs:0});
  const [live,setLive] = useState(true);
  const [passes,setPasses] = useState([]);
  const [detailPass,setDetailPass] = useState(null);
  const sockRef = useRef(null);
  const refresh = () => {
    fetchJSON('/api/metrics').then(d=>{
      const m=d.data||{};
      setMetrics({
        files:m.uploaded_files||0,
        vectors:m.vector_docs||0,
        graph:m.graph_nodes||0,
        tasks:m.task_count||0,
        logs:m.forensic_logs||0
      });
    });
  };
  useEffect(refresh, []);
  useEffect(() => {
    if (!live) {
      if (sockRef.current) { try { sockRef.current.disconnect(); } catch {} }
      sockRef.current = null;
      return;
    }
    const s = io('/chat', { transports:['websocket'] });
    s.on('pipeline_pass', (p) => {
      setPasses(prev => [{
        iteration: p.iteration,
        graphDeltaTotal: (()=>{ const d=p.graph_deltas||{}; return Object.values(d).reduce((a,b)=>a+(parseInt(b,10)||0),0); })(),
        timeline: p.timeline_sequences || p.timeline_paths || {},
        theories: p.theories || [],
        raw: p,
      }, ...prev].slice(0,10));
    });
    sockRef.current = s;
    return () => { try { s.disconnect(); } catch {} };
  }, [live]);
  return (
    <section className="card">
      <h2>
        Team Pipeline
        <i
          className="fa fa-question-circle ml-2 text-sm"
          title="Counts of items processed in each stage of the discovery pipeline."
          aria-label="Pipeline info"
        ></i>
      </h2>
      <p className="text-sm text-gray-600 mb-2">
        Track how documents move from ingestion through analysis and tasking.
      </p>
      <div className="pipeline">
        <div className="stage">
          <i className="fa fa-file-upload"></i>
          <span>Ingestion</span>
          <span className="count">{metrics.files}</span>
        </div>
        <div className="stage">
          <i className="fa fa-search-dollar"></i>
          <span>Forensics</span>
          <span className="count">{metrics.logs}</span>
        </div>
        <div className="stage">
          <i className="fa fa-database"></i>
          <span>Vector DB</span>
          <span className="count">{metrics.vectors}</span>
        </div>
        <div className="stage">
          <i className="fa fa-project-diagram"></i>
          <span>Graph</span>
          <span className="count">{metrics.graph}</span>
        </div>
        <div className="stage">
          <i className="fa fa-tasks"></i>
          <span>Tasks</span>
          <span className="count">{metrics.tasks}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <button className="button-secondary" onClick={refresh}><i className="fa fa-sync mr-1"></i>Refresh</button>
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={live} onChange={e=>setLive(e.target.checked)} /> Live</label>
      </div>
      {!!passes.length && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold mb-1">Recent Analysis Passes</h3>
          <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))', gap:'8px'}}>
            {passes.map((p,idx) => (
              <div key={idx} className="p-2 rounded" style={{background:'rgba(0,0,0,0.3)', border:'1px solid rgba(255,255,255,0.08)'}}>
                <div className="text-xs opacity-80">Iteration {p.iteration}</div>
                <div className="text-sm">Graph Δ: <span className="font-semibold">{p.graphDeltaTotal}</span></div>
                <div className="text-xs">Timeline max chain: {(p.timeline && p.timeline.max_timeline_chain) || 0}</div>
                {!!(p.theories && p.theories.length) && (
                  <ul className="text-xs list-disc list-inside mt-1">
                    {p.theories.slice(0,3).map((t,i)=>(<li key={i}>{t.name || t.title || 'theory'}</li>))}
                  </ul>
                )}
                <div className="mt-2">
                  <button className="button-secondary text-xs" onClick={()=>setDetailPass(p.raw)}>Details</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {detailPass && (
        <div className="modal" role="dialog" aria-modal="true" onClick={(e)=>{ if(e.target.classList.contains('modal')) setDetailPass(null); }}>
          <div className="modal-content" style={{maxWidth:'720px'}}>
            <button className="close-btn" onClick={()=>setDetailPass(null)} aria-label="Close details">&times;</button>
            <h3 className="text-lg font-semibold mb-2">Pass Details (Iteration {detailPass.iteration || detailPass?.raw?.iteration || ''})</h3>
            {detailPass.graph_deltas && (
              <div className="mb-3">
                <h4 className="text-sm font-semibold mb-1">Graph Deltas</h4>
                <ul className="text-xs list-disc list-inside">
                  {Object.entries(detailPass.graph_deltas).map(([k,v]) => (
                    <li key={k}>{k}: {v}</li>
                  ))}
                </ul>
              </div>
            )}
            {(detailPass.timeline_sequences || detailPass.timeline_paths) && (
              <div className="mb-3">
                <h4 className="text-sm font-semibold mb-1">Timeline</h4>
                <pre className="text-xs overflow-x-auto" style={{background:'rgba(0,0,0,0.3)', padding:'8px'}}>{JSON.stringify(detailPass.timeline_sequences || detailPass.timeline_paths, null, 2)}</pre>
              </div>
            )}
            {detailPass.theories && detailPass.theories.length > 0 && (
              <div className="mb-3">
                <h4 className="text-sm font-semibold mb-1">Theories</h4>
                <ul className="text-xs list-disc list-inside">
                  {detailPass.theories.map((t,i)=> (
                    <li key={i}><span className="font-semibold">{t.name || t.title || 'theory'}</span>{t.description? ': '+t.description: ''}</li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h4 className="text-sm font-semibold mb-1">Raw</h4>
              <pre className="text-xs overflow-x-auto" style={{background:'rgba(0,0,0,0.3)', padding:'8px'}}>{JSON.stringify(detailPass, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
export default PipelineSection;
