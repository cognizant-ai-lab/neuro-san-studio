import React, { useState, useEffect } from "react";
import { fetchJSON } from "../utils";
import MetricCard from "./MetricCard";
function OverviewSection() {
  const [metrics,setMetrics] = useState({});
  const refresh = () => {
    fetchJSON('/api/metrics').then(d=>setMetrics(d.data||{}));
  };
  useEffect(refresh, []);
  const hitRate = (() => {
    const hits = metrics.cache_hits || 0;
    const misses = metrics.cache_misses || 0;
    const total = hits + misses;
    return total ? Math.round((hits * 100) / total) : 0;
  })();
  return (
    <section className="card">
      <h2>Overview</h2>
        <div className="metrics-grid">
          <MetricCard icon="fa-briefcase" label="Cases" value={metrics.case_count||0} />
          <MetricCard icon="fa-file-alt" label="Files" value={metrics.uploaded_files||0} />
          <MetricCard icon="fa-tasks" label="Tasks" value={metrics.task_count||0} />
          <MetricCard icon="fa-database" label="Vectors" value={metrics.vector_docs||0} />
          <MetricCard icon="fa-project-diagram" label="Graph" value={metrics.graph_nodes||0} />
          <MetricCard icon="fa-bolt" label="Cache Hit %" value={hitRate} />
        </div>
      <button className="button-secondary" onClick={refresh}><i className="fa fa-sync mr-1"></i>Refresh</button>
    </section>
  );
}
export default OverviewSection;
