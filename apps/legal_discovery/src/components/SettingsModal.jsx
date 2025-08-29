import React, { useState, useEffect, useRef } from "react";
import { useAppContext } from "../AppContext";

function SettingsModal({open,onClose}) {
  const { setSettings, setFeatureFlags, theme, setTheme, themes } = useAppContext();
  const [form,setForm] = useState({});
  const ref = useRef();
  const firstFieldRef = useRef();
  const previousFocus = useRef();

  useEffect(() => {
    if(open) {
      previousFocus.current = document.activeElement;
      Promise.all([
        fetch('/api/settings').then(r=>r.json()),
        fetch('/api/feature-flags').then(r=>r.json())
      ]).then(([settings, flags]) => setForm({ theme, ...settings, ...flags }));
      setTimeout(()=>firstFieldRef.current && firstFieldRef.current.focus(),0);
    } else if(previousFocus.current) {
      previousFocus.current.focus();
    }
  }, [open]);

  const update = e => {
    const { name, type, checked, value } = e.target;
    setForm({ ...form, [name]: type === "checkbox" ? checked : value });
  };

  const submit = e => {
    e.preventDefault();
    const { voice_stt, voice_tts, voice_commands, theories, binder, chat, ...rest } = form;
    const flags = { voice_stt, voice_tts, voice_commands, theories, binder, chat };
    Promise.all([
      fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(rest)}),
      fetch('/api/feature-flags',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(flags)})
    ]).then(()=>{
      setSettings(rest);
      setFeatureFlags(flags);
      if(rest.theme) setTheme(rest.theme);
      onClose();
    });
  };

  const trapFocus = e => {
    if(e.key !== 'Tab') return;
    const focusable = ref.current.querySelectorAll('a,button,input,textarea');
    if(!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length-1];
    if(e.shiftKey && document.activeElement === first){
      e.preventDefault();
      last.focus();
    } else if(!e.shiftKey && document.activeElement === last){
      e.preventDefault();
      first.focus();
    }
  };

  if(!open) return null;
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title" onKeyDown={trapFocus} onClick={e=>{if(e.target===ref.current) onClose();}} ref={ref}>
      <div className="modal-content">
        <button className="close-btn" onClick={onClose} aria-label="Close settings">&times;</button>
        <h2 id="settings-title">API Settings</h2>
        <form id="settings-form" onSubmit={submit} className="space-y-2 overflow-y-auto" style={{maxHeight:'60vh'}}>
          <label>CourtListener API Key<input ref={firstFieldRef} type="text" name="courtlistener_api_key" value={form.courtlistener_api_key||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>CourtListener Endpoint<input type="text" name="courtlistener_com_api_endpoint" value={form.courtlistener_com_api_endpoint||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>California Codes URL<input type="text" name="california_codes_url" value={form.california_codes_url||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Gemini API Key<input type="text" name="gemini_api_key" value={form.gemini_api_key||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Google API Endpoint<input type="text" name="google_api_endpoint" value={form.google_api_endpoint||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>VerifyPDF API Key<input type="text" name="verifypdf_api_key" value={form.verifypdf_api_key||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>VerifyPDF Endpoint<input type="text" name="verify_pdf_endpoint" value={form.verify_pdf_endpoint||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Riza Key<input type="text" name="riza_key" value={form.riza_key||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Neo4j URI<input type="text" name="neo4j_uri" value={form.neo4j_uri||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Neo4j Username<input type="text" name="neo4j_username" value={form.neo4j_username||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Neo4j Password<input type="password" name="neo4j_password" value={form.neo4j_password||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Neo4j Database<input type="text" name="neo4j_database" value={form.neo4j_database||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Aura Instance ID<input type="text" name="aura_instance_id" value={form.aura_instance_id||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>Aura Instance Name<input type="text" name="aura_instance_name" value={form.aura_instance_name||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>GCP Project ID<input type="text" name="gcp_project_id" value={form.gcp_project_id||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>GCP Vertex Data Store<input type="text" name="gcp_vertex_ai_data_store_id" value={form.gcp_vertex_ai_data_store_id||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>GCP Search App<input type="text" name="gcp_vertex_ai_search_app" value={form.gcp_vertex_ai_search_app||''} onChange={update} className="w-full p-2 rounded"/></label>
          <label>GCP Service Account Key<textarea name="gcp_service_account_key" value={form.gcp_service_account_key||''} onChange={update} className="w-full p-2 rounded" rows="2"/></label>
          <label>Theme
            <select name="theme" value={form.theme||'dark'} onChange={update} className="w-full p-2 rounded">
              {themes.map(t => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="theories" checked={form.theories||false} onChange={update}/><span>Enable Legal Theories</span></label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="binder" checked={form.binder||false} onChange={update}/><span>Enable Binder</span></label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="chat" checked={form.chat||false} onChange={update}/><span>Enable Chat</span></label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="voice_stt" checked={form.voice_stt||false} onChange={update}/><span>Enable Voice Transcription</span></label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="voice_tts" checked={form.voice_tts||false} onChange={update}/><span>Enable Voice Synthesis</span></label>
          <label className="flex items-center space-x-2"><input type="checkbox" name="voice_commands" checked={form.voice_commands||false} onChange={update}/><span>Enable Voice Commands</span></label>
          <div className="grid grid-cols-2 gap-2">
            <label>Voice Engine
              <select name="voice_engine" value={form.voice_engine||''} onChange={update} className="w-full p-2 rounded">
                <option value="">Default</option>
                <option value="gtts">gTTS</option>
                <option value="system">System</option>
                <option value="coqui">Coqui</option>
              </select>
            </label>
            <label>Voice Model
              <input type="text" name="voice_model" value={form.voice_model||''} onChange={update} className="w-full p-2 rounded" placeholder="e.g., en-US" />
            </label>
            <button type="button" className="button-secondary" onClick={()=>{
              fetch('/api/chat/voices').then(r=>r.json()).then(v=>{
                const first = (v.voices && v.voices[0] && (v.voices[0].id||v.voices[0].name)) || '';
                if (first) setForm(prev=>({ ...prev, voice_model: first }));
                alert(`Found ${v.voices? v.voices.length:0} voices${first?` (selected: ${first})`:''}`);
              });
            }}>List Voices</button>
          </div>
          <button className="button-primary" type="submit">Save</button>
        </form>
      </div>
    </div>
  );
}

export default SettingsModal;
