import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import Skeleton from "./Skeleton";
function TimelineSection() {
  const [query,setQuery] = useState('');
  const [events,setEvents] = useState([]);
  const containerRef = useRef();
  const socketRef = useRef();
  const [exporting,setExporting] = useState(false);
  const [startDate,setStartDate] = useState('');
  const [endDate,setEndDate] = useState('');
  const [loading,setLoading] = useState(false);
  const hoverRef = useRef(null);
  const load = () => {
    setLoading(true);
    fetch('/api/timeline?query='+encodeURIComponent(query))
      .then(r=>r.json()).then(d=>setEvents(d.data||[])).finally(()=>setLoading(false));
  };
  const exportTimeline = () => {
    setExporting(true);
    fetch('/api/export/report', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'timeline',timeline_id:query})})
      .then(r=>r.text()).then(html=>{const w=window.open('about:blank'); w.document.write(html);})
      .finally(()=>setExporting(false));
  };
  useEffect(() => {
    socketRef.current = io('/present');
    return () => socketRef.current && socketRef.current.disconnect();
  }, []);
  useEffect(() => {
    if(!containerRef.current) return;
    let filtered = events;
    if(startDate) filtered = filtered.filter(e=>e.date>=startDate);
    if(endDate) filtered = filtered.filter(e=>e.date<=endDate);
    if(!filtered.length) { containerRef.current.innerHTML=''; return; }
    const dataset = new vis.DataSet(filtered.map(e => ({
      id: e.id,
      content: e.description,
      start: e.date,
      citation: e.citation,
      excerpt: e.excerpt || (e.links && e.links.excerpt) || '',
      hover_image: (e.links && e.links.hover_image) || e.hover_image,
      doc_path: (e.links && e.links.doc_path) || e.doc_path,
      page: (e.links && e.links.page) || e.page,
    })));

    const timeline = new vis.Timeline(containerRef.current, dataset, {});
    const pop = document.createElement('div');
    pop.style.position='fixed'; pop.style.pointerEvents='none'; pop.style.zIndex=999;
    pop.style.display='none';
    document.body.appendChild(pop);
    hoverRef.current = pop;
    const showHover = (props) => {
      const item = dataset.get(props.item); if(!item) return;
      pop.innerHTML = '';
      const wrap = document.createElement('div');
      wrap.style.background='rgba(0,0,0,0.8)'; wrap.style.backdropFilter='blur(8px)';
      wrap.style.border='1px solid var(--color-border)'; wrap.style.borderRadius='12px'; wrap.style.padding='8px';
      wrap.style.maxWidth='360px'; wrap.style.color='var(--color-text)';
      if(item.hover_image){ const img=new Image(); img.src=item.hover_image; img.style.maxWidth='100%'; img.style.borderRadius='8px'; wrap.appendChild(img); }
      if(item.excerpt){ const p=document.createElement('div'); p.textContent=item.excerpt; p.style.fontSize='12px'; p.style.marginTop='6px'; wrap.appendChild(p); }
      const btn=document.createElement('button'); btn.className='button-primary'; btn.textContent='Open'; btn.style.marginTop='6px';
      btn.onclick=(e)=>{ e.preventDefault(); e.stopPropagation(); if(item.doc_path){ window.open(`/present/viewer/${encodeURIComponent(item.doc_path)}`,'_blank'); } };
      wrap.appendChild(btn);
      pop.appendChild(wrap);
      pop.style.left=(props.event.srcEvent.clientX+12)+'px';
      pop.style.top=(props.event.srcEvent.clientY+12)+'px';
      pop.style.display='block';
    };
    const hideHover = ()=>{ if(pop) pop.style.display='none'; };
    timeline.on('itemover', showHover);
    timeline.on('itemout', hideHover);
    timeline.on('click', props => {
      const item = dataset.get(props.item);
      if(!item) return;
      const modal = document.getElementById('modal');
      const frame = modal.querySelector('iframe');
      if(item.citation) {
        frame.src = item.citation;
      } else if(item.excerpt) {
        frame.srcdoc = `<pre style="white-space:pre-wrap">${item.excerpt}</pre>`;
      } else {
        return;
      }
      modal.style.display='flex';
      if(item.doc_id && typeof item.page === 'number' && socketRef.current){
        socketRef.current.emit('command',{doc_id:item.doc_id,command:'goto_page',page:item.page});
      }
    });
    return () => { if(pop && pop.parentNode) pop.parentNode.removeChild(pop); };
  }, [events]);

  useEffect(() => {
    const handler = () => load();
    window.addEventListener('timelineRefresh', handler);
    return () => window.removeEventListener('timelineRefresh', handler);
  });
  return (
    <section className="card">
      <h2>Timeline</h2>
      <textarea rows="2" className="w-full mb-3 p-2 rounded" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Request events…"></textarea>
      <div className="flex gap-2 mb-2">
        <input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="p-1 rounded" />
        <input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)} className="p-1 rounded" />
      </div>
      <div className="flex gap-2 mb-2">
        <button className="button-primary" onClick={load}>Load Timeline</button>
        <button className="button-secondary" onClick={exportTimeline}><i className="fa fa-file-export mr-1"></i>Export</button>
        <button className="button-secondary" onClick={()=> window.dispatchEvent(new CustomEvent('toast',{detail:{type:'info',message:'Add timeline events via the new API (UI capture tool coming).'}}))}>Add Event</button>
      </div>
      {exporting && <p className="text-sm mb-1">Exporting...</p>}
      {loading ? <Skeleton className="h-48" /> : <div ref={containerRef} style={{height:'200px'}}></div>}
    </section>
  );
}
export default TimelineSection;
