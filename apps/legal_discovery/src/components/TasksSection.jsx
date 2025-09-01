import React, { useState } from "react";
import { alertResponse } from "../utils";
function TasksSection() {
  const [task,setTask] = useState('');
  const [list,setList] = useState('');
  const add = () => fetch('/api/tasks',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({task}),
    keepalive:true
  }).then(r=>r.json()).then(alertResponse);
  const listAll = () => fetch('/api/tasks').then(r=>r.json()).then(d=>setList(d.data||''));
  const clear = () => fetch('/api/tasks',{method:'DELETE'}).then(r=>r.json()).then(d=>{setList('');alert(d.message||'Cleared');});
  return (
    <section className="card">
      <h2>Task Tracker</h2>
      <input type="text" value={task} onChange={e=>setTask(e.target.value)} className="w-full mb-2 p-2 rounded" placeholder="New task" />
      <div className="flex flex-wrap gap-2 mb-2">
        <button className="button-secondary" onClick={add}><i className="fa fa-plus mr-1"></i>Add</button>
        <button className="button-secondary" onClick={listAll}><i className="fa fa-list mr-1"></i>List</button>
        <button className="button-secondary" onClick={clear}><i className="fa fa-trash mr-1"></i>Clear</button>
      </div>
      <pre className="text-sm">{list}</pre>
    </section>
  );
}

export default TasksSection;
