import React, { useState, useRef, Suspense } from "react";
import { NavLink, Routes, Route } from "react-router-dom";
import SettingsModal from "./components/SettingsModal";
import ErrorBoundary from "./components/ErrorBoundary";
import Skeleton from "./components/Skeleton";
import ThemeToggle from "./components/ThemeToggle";
import Tour from "./components/Tour";

const AgentNetworkSection = React.lazy(()=>import('./components/AgentNetworkSection'));
const OverviewSection = React.lazy(()=>import('./components/OverviewSection'));
const PipelineSection = React.lazy(()=>import('./components/PipelineSection'));
const ChatSection = React.lazy(()=>import('./components/ChatSection'));
const StatsSection = React.lazy(()=>import('./components/StatsSection'));
const UploadSection = React.lazy(()=>import('./components/UploadSection'));
const DocumentReviewSection = React.lazy(()=>import('./components/DocumentReviewSection'));
const TimelineSection = React.lazy(()=>import('./components/TimelineSection'));
const GraphSection = React.lazy(()=>import('./components/GraphSection'));
const LegalTheorySection = React.lazy(()=>import('./components/LegalTheorySection'));
const DocToolsSection = React.lazy(()=>import('./components/DocToolsSection'));
const VersionHistorySection = React.lazy(()=>import('./components/VersionHistorySection'));
const DocumentDraftSection = React.lazy(()=>import('./components/DocumentDraftSection'));
const AutoDraftSection = React.lazy(()=>import('./components/AutoDraftSection'));
const ForensicSection = React.lazy(()=>import('./components/ForensicSection'));
const VectorSection = React.lazy(()=>import('./components/VectorSection'));
const TasksSection = React.lazy(()=>import('./components/TasksSection'));
const CaseManagementSection = React.lazy(()=>import('./components/CaseManagementSection'));
const ResearchSection = React.lazy(()=>import('./components/ResearchSection'));
const SubpoenaSection = React.lazy(()=>import('./components/SubpoenaSection'));
const PresentationSection = React.lazy(()=>import('./components/PresentationSection'));
const TrialPrepSchoolSection = React.lazy(()=>import('./components/TrialPrepSchoolSection'));
const ExhibitTab = React.lazy(()=>import('./components/ExhibitTab'));
const DepositionPrepSection = React.lazy(()=>import('./components/DepositionPrepSection'));
const OppositionTrackerSection = React.lazy(()=>import('./components/OppositionTrackerSection'));
const ChainLogSection = React.lazy(()=>import('./components/ChainLogSection'));

const TABS = [
  {id:'network', label:'Agent Network', icon:'fa-sitemap', Component: AgentNetworkSection},
  {id:'overview', label:'Overview', icon:'fa-home', Component: OverviewSection},
  {id:'chat', label:'Orchestrator', icon:'fa-comments', Component: ChatSection},
  {id:'pipeline', label:'Team Pipeline', icon:'fa-route', Component: PipelineSection},
  {id:'stats', label:'Stats', icon:'fa-chart-bar', Component: StatsSection},
  {id:'upload', label:'Ingestion', icon:'fa-upload', Component: UploadSection},
  {id:'review', label:'Doc Review', icon:'fa-list', Component: DocumentReviewSection},
  {id:'timeline', label:'Timeline', icon:'fa-clock', Component: TimelineSection},
  {id:'graph', label:'Graph', icon:'fa-project-diagram', Component: GraphSection},
  {id:'theory', label:'Case Theory', icon:'fa-balance-scale', Component: LegalTheorySection},
  {id:'docs', label:'Discovery Tools', icon:'fa-file-alt'},
  {id:'forensic', label:'Forensics', icon:'fa-search-dollar', Component: ForensicSection},
  {id:'vector', label:'Vector DB', icon:'fa-database', Component: VectorSection},
  {id:'tasks', label:'Scheduling', icon:'fa-tasks', Component: TasksSection},
  {id:'case', label:'Case Mgmt', icon:'fa-folder-open', Component: CaseManagementSection},
  {id:'research', label:'Legal Research', icon:'fa-book-open', Component: ResearchSection},
  {id:'subpoena', label:'Subpoena', icon:'fa-gavel', Component: SubpoenaSection},
  {id:'presentation', label:'Trial Prep', icon:'fa-slideshare', Component: PresentationSection},
  {id:'academy', label:'Trial Prep School', icon:'fa-university', Component: TrialPrepSchoolSection},
  {id:'exhibits', label:'Exhibits', icon:'fa-book', Component: ExhibitTab},
  {id:'deposition', label:'Deposition Prep', icon:'fa-user-tie', Component: DepositionPrepSection},
  {id:'opposition', label:'Opposition Tracker', icon:'fa-flag', Component: OppositionTrackerSection},
  {id:'chain', label:'Chain Log', icon:'fa-link', Component: ChainLogSection},
];

const render = (Comp) => (
  <ErrorBoundary>
    <Suspense fallback={<Skeleton className="h-48" />}>
      <Comp />
    </Suspense>
  </ErrorBoundary>
);

const DOC_TABS = [
  { id: 'tools', label: 'Document Tools', Component: DocToolsSection },
  { id: 'versions', label: 'Version History', Component: VersionHistorySection },
  { id: 'draft', label: 'Document Draft', Component: DocumentDraftSection },
  { id: 'auto', label: 'Auto Draft', Component: AutoDraftSection },
];

const DocsRoute = () => {
  const [selected, setSelected] = useState('tools');
  const Active = DOC_TABS.find(t => t.id === selected).Component;
  return (
    <div>
      <select value={selected} onChange={e=>setSelected(e.target.value)} className="mb-4 p-2 rounded">
        {DOC_TABS.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
      </select>
      <Active />
    </div>
  );
};

function Dashboard() {
  const [showSettings,setShowSettings] = useState(false);
  const tabListRef = useRef(null);

  const handleKeyDown = e => {
    if(e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const buttons = tabListRef.current.querySelectorAll('.tab-button');
    const index = Array.from(buttons).indexOf(document.activeElement);
    if(index === -1) return;
    const next = e.key === 'ArrowRight' ? (index + 1) % buttons.length : (index - 1 + buttons.length) % buttons.length;
    buttons[next].focus();
    e.preventDefault();
  };

  return (
    <div className="dashboard-grid">
      <Tour />
      <nav className="tab-buttons" role="tablist" onKeyDown={handleKeyDown} ref={tabListRef}>
        {TABS.map(t => (
          <NavLink id={`tab-${t.id}`} key={t.id} to={t.id} className={({isActive})=>`tab-button${isActive?' active':''}`} role="tab" aria-label={t.label}>
            <i className={`fa ${t.icon} mr-1`} aria-hidden="true"></i>{t.label}
          </NavLink>
        ))}
        <button className="tab-button" onClick={()=>setShowSettings(true)} aria-label="Open settings">
          <i className="fa fa-cog"></i>
        </button>
        <ThemeToggle />
      </nav>
      <main className="tab-panels">
        <Routes>
          {TABS.filter(t=>t.Component).map(t => (
            <Route key={t.id} path={t.id} element={render(t.Component)} />
          ))}
          <Route path="docs" element={render(DocsRoute)} />
          <Route index element={render(OverviewSection)} />
        </Routes>
      </main>
      <SettingsModal open={showSettings} onClose={()=>setShowSettings(false)}/>
    </div>
  );
}

export default Dashboard;
