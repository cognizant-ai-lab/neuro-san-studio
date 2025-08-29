import React, { useState, useEffect, useRef, useCallback } from "react";
import { fetchJSON } from "../utils";
import Skeleton from "./Skeleton";
import { theme } from "../theme";
/* global cytoscape */
function GraphSection() {
  const [nodes,setNodes] = useState([]);
  const [edges,setEdges] = useState([]);
  const [subnet,setSubnet] = useState('');
  const [search,setSearch] = useState('');
  const [cypher,setCypher] = useState('');
  const [cypherResult,setCypherResult] = useState(null);
  const cyRef = useRef(null);
  const [exporting,setExporting] = useState(false);
  const [analysis,setAnalysis] = useState([]);
  const [timelineStats,setTimelineStats] = useState(null);
  const [enrichDeltas,setEnrichDeltas] = useState(null);
  const [loading,setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    const url = '/api/graph' + (subnet?`?subnet=${encodeURIComponent(subnet)}`:'');
    fetchJSON(url).then(d=>{setNodes(d.data.nodes||[]);setEdges(d.data.edges||[]);}).finally(()=>setLoading(false));
  }, [subnet]);
  useEffect(load, []);
  useEffect(() => {
    const handler = () => load();
    window.addEventListener('graphRefresh', handler);
    return () => window.removeEventListener('graphRefresh', handler);
  }, [load]);

  useEffect(() => {
    const handler = (e) => {
      const cause = e.detail && e.detail.cause;
      if (!cause) return;
      fetchJSON(`/api/theories/graph?cause=${encodeURIComponent(cause)}`).then(d => {
        setNodes(d.nodes || []);
        setEdges(d.edges || []);
      });
    };
    window.addEventListener('loadTheoryGraph', handler);
    return () => window.removeEventListener('loadTheoryGraph', handler);
  }, []);
  useEffect(() => {
    if(!nodes.length && !edges.length) return;
    const cy = cytoscape({
      container: document.getElementById('graph'),
      elements: [],
      style:[
        { selector:'node', style:{ label:'data(label)', 'background-color':'#64748b', color:'#fff' } },
        { selector:'.highlight', style:{ 'background-color':'#f97316', color:'#fff' } }
      ]
    });
    cy.add(nodes.map(n => ({ data:{ id:n.id, label:(n.labels||[''])[0] }})));
    cy.add(edges.map(e => ({ data:{ id:e.source+'_'+e.target, source:e.source, target:e.target }})));
    cy.layout({ name:'breadthfirst', directed:true }).run();
    cyRef.current = cy;
  }, [nodes,edges]);
  const highlight = () => {
    if(!cyRef.current) return;
    const node = cyRef.current.getElementById(search);
    if(node) {
      cyRef.current.elements().removeClass('highlight');
      node.addClass('highlight');
      cyRef.current.center(node);
    }
  };
  const exportGraph = () => {
    setExporting(true);
    fetch('/api/graph/export')
      .then(r=>r.text()).then(html=>{const w=window.open('about:blank'); w.document.write(html);})
      .finally(()=>setExporting(false));
  };
  const analyze = () => {
    const url = '/api/graph/analyze' + (subnet?`?subnet=${encodeURIComponent(subnet)}`:'');
    fetchJSON(url).then(d=>{ setAnalysis(d.data||[]); setTimelineStats((d.meta && d.meta.timeline) || null); });
  };
  const syncTimeline = () => {
    fetch('/api/graph/sync_timeline',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})})
      .then(r=>r.json()).then(()=>load());
  };
  const enrich = () => {
    fetch('/api/graph/enrich',{method:'POST'}).then(r=>r.json()).then(d=> setEnrichDeltas(d.data||d.error||null));
  };
  const runCypher = (preset) => {
    const query = preset || cypher;
    if(!query) return;
    fetch('/api/graph/cypher',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query})})
      .then(r=>r.json()).then(d=>setCypherResult(d.data||d.error||null));
  };
  if (loading) {
    return (
      <section className="card">
        <h2>Knowledge Graph</h2>
        <Skeleton className="h-48" />
      </section>
    );
  }
  return (
    <section className="card">
      <h2>Knowledge Graph</h2>
      <div className="flex flex-wrap" style={{ gap: theme.spacing.sm, marginBottom: theme.spacing.sm }}>
        <input
          type="text"
          value={subnet}
          onChange={e=>setSubnet(e.target.value)}
          placeholder="subnet"
          style={{ padding: theme.spacing.xs, borderRadius: theme.spacing.xs }}
        />
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={load}><i className="fa fa-sync mr-1"></i>Load</button>
        <input
          type="text"
          value={search}
          onChange={e=>setSearch(e.target.value)}
          placeholder="find node"
          style={{ padding: theme.spacing.xs, borderRadius: theme.spacing.xs }}
        />
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={highlight}><i className="fa fa-search mr-1"></i>Find</button>
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={exportGraph}><i className="fa fa-file-export mr-1"></i>Export</button>
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={analyze}><i className="fa fa-network-wired mr-1"></i>Analyze</button>
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={syncTimeline}><i className="fa fa-project-diagram mr-1"></i>Sync Timeline</button>
        <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={enrich}><i className="fa fa-bolt mr-1"></i>Enrich Graph</button>
      </div>
      <div className="flex flex-wrap" style={{ gap: theme.spacing.sm, marginBottom: theme.spacing.sm }}>
        <textarea
          value={cypher}
          onChange={e=>setCypher(e.target.value)}
          placeholder="MATCH (n) RETURN n LIMIT 25"
          className="flex-1"
          rows={2}
          style={{ padding: theme.spacing.xs, borderRadius: theme.spacing.xs }}
        ></textarea>
        <div className="flex flex-col" style={{ gap: theme.spacing.sm }}>
          <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={()=>runCypher()}>Run</button>
          <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={()=>runCypher("MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50")}>Populate</button>
          <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={()=>runCypher("MATCH (d:Document) WHERE d.category='fraud' RETURN d LIMIT 25")}>Fraud</button>
          <button className="button-secondary" style={{ padding: theme.spacing.xs }} onClick={()=>runCypher("MATCH (d:Document) WHERE d.category='financial' RETURN d LIMIT 25")}>Financial Docs</button>
        </div>
      </div>
      {exporting && <p style={{ fontSize: theme.typography.sizeSm, marginBottom: theme.spacing.xs }}>Exporting...</p>}
      <div id="graph" style={{height:'300px', border:`1px solid ${theme.colors.border}`}}></div>
      {cypherResult && (
        <pre
          className="overflow-x-auto"
          style={{ background: 'rgba(0,0,0,0.3)', marginTop: theme.spacing.sm, padding: theme.spacing.sm, fontSize: theme.typography.sizeSm }}
        >{JSON.stringify(cypherResult,null,2)}</pre>
      )}
      {timelineStats && (
        <div style={{ marginTop: theme.spacing.sm, fontSize: theme.typography.sizeSm }}>
          <h3 style={{ fontWeight: theme.typography.weightBold, marginBottom: theme.spacing.xs }}>Timeline Metrics</h3>
          <ul className="list-disc list-inside">
            <li>Max chain length: {timelineStats.max_timeline_chain||0}</li>
            <li>3-hop sequences: {timelineStats.three_hop_sequences||0}</li>
          </ul>
        </div>
      )}
      {enrichDeltas && (
        <div style={{ marginTop: theme.spacing.sm, fontSize: theme.typography.sizeSm }}>
          <h3 style={{ fontWeight: theme.typography.weightBold, marginBottom: theme.spacing.xs }}>Enrichment Deltas</h3>
          <pre className="overflow-x-auto" style={{ background: 'rgba(0,0,0,0.3)', padding: theme.spacing.xs }}>{JSON.stringify(enrichDeltas,null,2)}</pre>
        </div>
      )}
      {!!analysis.length && (
        <div style={{ marginTop: theme.spacing.sm, fontSize: theme.typography.sizeSm }}>
          <h3 style={{ fontWeight: theme.typography.weightBold, marginBottom: theme.spacing.xs }}>Central Entities</h3>
          <ul className="list-disc list-inside">
            {analysis.map(a=> (
              <li key={a.id}>{a.id}: {a.score}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
export default GraphSection;
