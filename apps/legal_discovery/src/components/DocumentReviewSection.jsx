import React, { useState, useEffect, useMemo } from "react";
import VirtualList from "./common/VirtualList";
import { fetchJSON } from "../utils";

function DocumentReviewSection() {
  const [docs, setDocs] = useState([]);
  const [sort, setSort] = useState({ field: "probative_value", dir: "desc" });
  const [minProb, setMinProb] = useState(0);
  const [maxRisk, setMaxRisk] = useState(1);

  const load = () => fetchJSON("/api/documents").then(d => setDocs(d.data || []));
  useEffect(load, []);

  const setSortField = f =>
    setSort(s => ({ field: f, dir: s.field === f && s.dir === "desc" ? "asc" : "desc" }));

  const bar = (v, color) => (
    <div className="score-bar"><div className="score-fill" style={{ width: `${v * 100}%`, backgroundColor: color }}></div></div>
  );

  const filtered = useMemo(() => (docs
    .filter(d => d.probative_value >= minProb && d.admissibility_risk <= maxRisk)
    .sort((a, b) => {
      const f = sort.field;
      return sort.dir === "asc" ? a[f] - b[f] : b[f] - a[f];
    })), [docs, minProb, maxRisk, sort]);

  return (
    <section className="card">
      <h2>Document Review</h2>
      <div className="flex gap-2 mb-2 items-center">
        <label className="text-xs">Min Prob {minProb.toFixed(2)}</label>
        <input type="range" min="0" max="1" step="0.01" value={minProb} onChange={e=>setMinProb(parseFloat(e.target.value))} />
        <label className="text-xs">Max Risk {maxRisk.toFixed(2)}</label>
        <input type="range" min="0" max="1" step="0.01" value={maxRisk} onChange={e=>setMaxRisk(parseFloat(e.target.value))} />
        <button className="button-secondary ml-auto" onClick={load}><i className="fa fa-sync mr-1"/>Refresh</button>
      </div>
      <div className="w-full text-sm" role="table" aria-label="Documents">
        <div className="grid grid-cols-5 gap-2 py-2 border-b border-gray-600" role="rowgroup">
          <button className="text-left" role="columnheader" onClick={()=>setSortField('name')}>Name</button>
          <button className="text-left" role="columnheader" onClick={()=>setSortField('probative_value')}>Probative</button>
          <button className="text-left" role="columnheader" onClick={()=>setSortField('admissibility_risk')}>Admissibility</button>
          <button className="text-left" role="columnheader" onClick={()=>setSortField('narrative_alignment')}>Narrative</button>
          <button className="text-left" role="columnheader" onClick={()=>setSortField('score_confidence')}>Confidence</button>
        </div>
        <VirtualList
          items={filtered}
          itemHeight={40}
          height={320}
          renderItem={(d)=> (
            <div key={d.id} role="row" className="grid grid-cols-5 gap-2 py-2 border-b border-gray-700">
              <div role="cell" className="truncate" title={d.name}>{d.name}</div>
              <div role="cell">{bar(d.probative_value, '#38bdf8')}</div>
              <div role="cell">{bar(d.admissibility_risk, '#f87171')}</div>
              <div role="cell">{bar(d.narrative_alignment, '#a3e635')}</div>
              <div role="cell">{bar(d.score_confidence, '#facc15')}</div>
            </div>
          )}
        />
      </div>
    </section>
  );
}

export default DocumentReviewSection;
