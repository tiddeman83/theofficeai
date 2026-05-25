import { useState, useEffect } from 'react';
import { writeTextFile, readTextFile, readDir } from '@tauri-apps/plugin-fs';
import { homeDir } from '@tauri-apps/api/path';
import { open } from '@tauri-apps/plugin-dialog';
import {
  Server,
  Network,
  Laptop,
  Send,
  RefreshCw,
  CheckCircle2,
  Activity,
  Database,
  Cpu,
  Terminal,
  Clock,
  Radio,
  FileCode2,
  Workflow,
  FolderOpen,
  Plus,
  Trash2,
  FolderKanban,
  MessageSquareWarning,
  ClipboardCheck,
  ShieldAlert
} from 'lucide-react';

const APP_VERSION = '2.0.0';

// Pure JS UUID generator
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

interface BranchNode {
  id: string;
  name: string;
  ip: string;
  status: 'ONLINE' | 'STANDBY' | 'OFFLINE';
  persona: string;
  taskCount: number;
}

// Task type -> persona. Mirrors PERSONAS in hq_router.py.
const PERSONA_BY_TYPE: Record<string, string> = {
  frontend: 'Pixel',
  backend: 'Linus',
  architecture: 'Ada',
  qa: 'Kent'
};

// Shape persisted by hq_status_listener.py into status_log/{task_id}.json.
interface TaskStatus {
  task_id: string;
  status: string;
  branch_id?: string;
  branch_name?: string | null;
  base_branch?: string | null;
  commit_hash?: string | null;
  file_changes?: boolean;
  stderr?: string;
  received_at?: string;
}

interface DispatchLogPayload {
  task_id: string;
  type?: string;
  prompt?: string;
  workspace_path: string;
  timestamp: string;
  sender: string;
  routing_target: string;
  queue_type: 'task' | 'epic' | 'project';
  task_count?: number;
}

// Shape written by hq_project_manager.py into projects/{id}/manifest.json.
interface ProjectManifest {
  project_id: string;
  name: string;
  ceo_brief: string;
  workspace_path: string;
  stage: string;
  status: string;
  open_action: string;
  stage_history: string[];
  current_task_id: string | null;
  created_at: string;
  updated_at: string;
}

// Shape written by hq_issue_listener.py into projects/{id}/issues/{iss}.json.
interface ProjectIssue {
  issue_id: string;
  project_id: string;
  from_agent: string;
  task_id?: string;
  severity: 'info' | 'question' | 'block';
  subject: string;
  body?: string;
  requires?: 'ceo' | 'cto';
  created_at: string;
}

// Lowercase alnum, dashes instead of non-alnum, no leading/trailing dashes.
const safeSlug = (input: string): string =>
  input.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

interface EpicTaskDraft {
  task_id: string;
  type: string;
  prompt: string;
  depends_on: string;
}

const createEpicTaskDraft = (index: number, dependsOn = ''): EpicTaskDraft => ({
  task_id: `epic-step-${index}-${generateUUID().slice(0, 8)}`,
  type: index === 1 ? 'architecture' : 'backend',
  prompt: '',
  depends_on: dependsOn
});

const createDefaultEpicTasks = (): EpicTaskDraft[] => {
  const first = createEpicTaskDraft(1);
  const second = createEpicTaskDraft(2, first.task_id);
  const third = createEpicTaskDraft(3, first.task_id);
  third.type = 'frontend';
  return [first, second, third];
};

export default function App() {
  const [dispatchMode, setDispatchMode] = useState<'single' | 'epic' | 'project'>('single');
  const [taskId, setTaskId] = useState(generateUUID);
  const [taskType, setTaskType] = useState('frontend');
  const [prompt, setPrompt] = useState('');
  const [epicTasks, setEpicTasks] = useState<EpicTaskDraft[]>(createDefaultEpicTasks);
  const [workspacePath, setWorkspacePath] = useState('');
  const [lastPayload, setLastPayload] = useState<DispatchLogPayload | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>('hq');
  
  // Real-time dynamic dashboard metrics
  const [cpuUsage, setCpuUsage] = useState(14);
  const [memoryUsage, setMemoryUsage] = useState(42);
  const [brokerLatency, setBrokerLatency] = useState(48);

  // Task results returned by the branch daemons, surfaced by hq_status_listener.py.
  const [statuses, setStatuses] = useState<TaskStatus[]>([]);

  // Projects state
  const [projects, setProjects] = useState<ProjectManifest[]>([]);
  const [projectName, setProjectName] = useState('');
  const [projectBrief, setProjectBrief] = useState('');
  // Per-project CEO answer drafts keyed by project_id
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  // Per-project board decision drafts keyed by project_id
  const [decisionDrafts, setDecisionDrafts] = useState<Record<string, string>>({});
  // Issues keyed by project_id
  const [issuesByProject, setIssuesByProject] = useState<Record<string, ProjectIssue[]>>({});

  useEffect(() => {
    // Animate mock metrics for dynamic, live-system aesthetic
    const interval = setInterval(() => {
      setCpuUsage(prev => Math.max(8, Math.min(45, prev + (Math.random() * 6 - 3))));
      setMemoryUsage(prev => Math.max(38, Math.min(48, prev + (Math.random() * 2 - 1))));
      setBrokerLatency(prev => Math.max(35, Math.min(65, prev + (Math.random() * 10 - 5))));
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // Poll the status_log directory that hq_status_listener.py writes into and
  // surface the latest task result per file. The dir may not exist until the
  // listener has run once, so failures are swallowed silently.
  useEffect(() => {
    let cancelled = false;

    const loadStatuses = async () => {
      try {
        const home = await homeDir();
        const statusDir = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/status_log`;
        const entries = await readDir(statusDir);
        const results: TaskStatus[] = [];
        for (const entry of entries) {
          if (!entry.isFile || !entry.name.endsWith('.json')) continue;
          try {
            const text = await readTextFile(`${statusDir}/${entry.name}`);
            results.push(JSON.parse(text) as TaskStatus);
          } catch {
            // Skip a file that is mid-write or malformed; next poll will retry.
          }
        }
        results.sort((a, b) => (b.received_at ?? '').localeCompare(a.received_at ?? ''));
        if (!cancelled) setStatuses(results);
      } catch {
        // status_log not present yet; leave current state untouched.
      }
    };

    loadStatuses();
    const poll = setInterval(loadStatuses, 4000);
    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, []);

  // Poll projects/{id}/manifest.json at same 4s cadence as task statuses.
  useEffect(() => {
    let cancelled = false;

    const loadProjects = async () => {
      try {
        const home = await homeDir();
        const projectsDir = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/projects`;
        const topEntries = await readDir(projectsDir);
        const manifests: ProjectManifest[] = [];
        const collectedIssues: Record<string, ProjectIssue[]> = {};
        for (const entry of topEntries) {
          if (entry.isFile) continue;
          try {
            const manifestPath = `${projectsDir}/${entry.name}/manifest.json`;
            const text = await readTextFile(manifestPath);
            manifests.push(JSON.parse(text) as ProjectManifest);
          } catch {
            // Manifest not yet written; skip until next poll.
          }
          // Load issues for this project (may be empty).
          try {
            const issuesDir = `${projectsDir}/${entry.name}/issues`;
            const issueEntries = await readDir(issuesDir);
            const list: ProjectIssue[] = [];
            for (const ie of issueEntries) {
              if (!ie.isFile || !ie.name.endsWith('.json') || ie.name.startsWith('_')) continue;
              try {
                const issueText = await readTextFile(`${issuesDir}/${ie.name}`);
                list.push(JSON.parse(issueText) as ProjectIssue);
              } catch {
                // Mid-write or malformed; retry next poll.
              }
            }
            list.sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
            if (list.length > 0) collectedIssues[entry.name] = list;
          } catch {
            // Issues dir may not exist yet.
          }
        }
        manifests.sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''));
        if (!cancelled) {
          setProjects(manifests);
          setIssuesByProject(collectedIssues);
        }
      } catch {
        // projects dir not yet present; leave state untouched.
      }
    };

    loadProjects();
    const poll = setInterval(loadProjects, 4000);
    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, []);

  const dispatchProject = async () => {
    if (!projectName.trim() || !projectBrief.trim() || !workspacePath) return;

    const slug = safeSlug(projectName.trim()) || generateUUID().slice(0, 8);
    const payload = {
      project_id: slug,
      name: projectName.trim(),
      ceo_brief: projectBrief.trim(),
      workspace_path: workspacePath
    };

    try {
      const home = await homeDir();
      const targetPath = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/project_queue/${slug}.intake.json`;
      await writeTextFile(targetPath, JSON.stringify(payload, null, 2));

      setLastPayload({
        task_id: slug,
        workspace_path: workspacePath,
        timestamp: new Date().toISOString(),
        sender: 'CEO_HQ',
        routing_target: 'HQ Project Manager',
        queue_type: 'project'
      });
      setShowToast(true);
      setProjectName('');
      setProjectBrief('');
      setTimeout(() => setShowToast(false), 4000);
    } catch (err) {
      alert(`FS Write Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleRegenId = () => {
    setTaskId(generateUUID());
  };

  const addEpicTask = () => {
    const lastTaskId = epicTasks[epicTasks.length - 1]?.task_id ?? '';
    setEpicTasks(prev => [
      ...prev,
      createEpicTaskDraft(prev.length + 1, lastTaskId)
    ]);
  };

  const removeEpicTask = (taskIdToRemove: string) => {
    setEpicTasks(prev => prev.length === 1
      ? prev
      : prev
        .filter(task => task.task_id !== taskIdToRemove)
        .map(task => ({
          ...task,
          depends_on: task.depends_on
            .split(',')
            .map(dep => dep.trim())
            .filter(dep => dep && dep !== taskIdToRemove)
            .join(', ')
        }))
    );
  };

  const updateEpicTask = (taskIdToUpdate: string, patch: Partial<EpicTaskDraft>) => {
    setEpicTasks(prev => prev.map(task => task.task_id === taskIdToUpdate ? { ...task, ...patch } : task));
  };

  const buildEpicPayload = () => {
    return epicTasks.map(task => ({
      task_id: task.task_id,
      type: task.type,
      prompt: task.prompt.trim(),
      workspace_path: workspacePath,
      depends_on: task.depends_on
        .split(',')
        .map(dep => dep.trim())
        .filter(Boolean)
    }));
  };

  const getInvalidEpicDependencies = () => {
    const validTaskIds = new Set(epicTasks.map(task => task.task_id));
    return epicTasks.flatMap(task =>
      task.depends_on
        .split(',')
        .map(dep => dep.trim())
        .filter(dep => dep && (!validTaskIds.has(dep) || dep === task.task_id))
        .map(dep => `${task.task_id} -> ${dep}`)
    );
  };

  const handleSelectWorkspace = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: 'Select Workspace Folder'
      });
      if (selected && typeof selected === 'string') {
        setWorkspacePath(selected);
      }
    } catch (err) {
      console.error("Failed to select workspace directory:", err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (dispatchMode === 'epic') {
      await dispatchEpic();
      return;
    }
    if (dispatchMode === 'project') {
      await dispatchProject();
      return;
    }
    if (!prompt.trim() || !workspacePath) return;

    const routerPayload = {
      task_id: taskId,
      type: taskType,
      prompt: prompt.trim(),
      workspace_path: workspacePath
    };

    const uiPayload = {
      ...routerPayload,
      timestamp: new Date().toISOString(),
      sender: "CEO_HQ",
      routing_target: PERSONA_BY_TYPE[taskType] ?? taskType,
      queue_type: 'task' as const
    };

    const routerPayloadStr = JSON.stringify(routerPayload, null, 2);
    console.log("HQ Dispatcher Payload JSON Output:", routerPayloadStr);

    try {
      // Resolve the home directory dynamically for security and portability
      const home = await homeDir();
      const targetPath = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/task_queue/task_${taskId}.json`;
      
      await writeTextFile(targetPath, routerPayloadStr);
      console.log(`Successfully wrote task to: ${targetPath}`);
      
      // Update UI log panel
      setLastPayload(uiPayload);
      setShowToast(true);
      
      // Clear form input and prepare next task (keep workspace selected for CEO convenience)
      setPrompt('');
      setTaskId(generateUUID());
      
      // Auto clear success notification toast
      setTimeout(() => {
        setShowToast(false);
      }, 4000);
      
    } catch (err) {
      console.error("Failed to write task payload using Tauri File System API:", err);
      alert(`FS Write Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const dispatchEpic = async () => {
    const validTasks = epicTasks.every(task => task.prompt.trim());
    if (!validTasks || !workspacePath) return;
    const invalidDependencies = getInvalidEpicDependencies();
    if (invalidDependencies.length > 0) {
      alert(`Invalid epic dependency: ${invalidDependencies[0]}`);
      return;
    }

    const epicId = generateUUID();
    const epicPayload = buildEpicPayload();
    const epicPayloadStr = JSON.stringify(epicPayload, null, 2);
    console.log("HQ Epic Payload JSON Output:", epicPayloadStr);

    try {
      const home = await homeDir();
      const targetPath = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/epic_queue/epic_${epicId}.json`;

      await writeTextFile(targetPath, epicPayloadStr);
      console.log(`Successfully wrote epic to: ${targetPath}`);

      setLastPayload({
        task_id: epicId,
        workspace_path: workspacePath,
        timestamp: new Date().toISOString(),
        sender: "CEO_HQ",
        routing_target: "HQ Epic Manager",
        queue_type: 'epic',
        task_count: epicPayload.length
      });
      setShowToast(true);
      setEpicTasks(createDefaultEpicTasks());

      setTimeout(() => {
        setShowToast(false);
      }, 4000);
    } catch (err) {
      console.error("Failed to write epic payload using Tauri File System API:", err);
      alert(`FS Write Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Branch offices landscape data
  const branches: BranchNode[] = [
    { id: 'branch_1', name: 'Branch Office 1', ip: '172.16.80.12', status: 'ONLINE', persona: 'Linus (CTO)', taskCount: 8 },
    { id: 'branch_2', name: 'Branch Office 2', ip: '172.16.80.15', status: 'STANDBY', persona: 'Ada (Architect)', taskCount: 3 },
    { id: 'branch_3', name: 'Branch Office 3', ip: '172.16.80.20', status: 'OFFLINE', persona: 'Pixel (Frontend)', taskCount: 0 }
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col selection:bg-indigo-500/30 selection:text-indigo-200">
      
      {/* Visual Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/30 shadow-lg shadow-indigo-500/10">
              <Network className="w-5 h-5 text-indigo-500" />
              <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 pulse-glow"></div>
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white m-0">DevBoss</h1>
              <p className="text-xs text-indigo-400 font-medium">HQ Command Center</p>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            {/* System Status Indicators */}
            <div className="hidden md:flex items-center gap-5 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                <span className="font-mono">BROKER: Connected</span>
              </div>
              <div className="w-px h-3 bg-slate-800"></div>
              <div className="flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                <span className="font-mono">Tauri Runtime</span>
              </div>
            </div>
            
            <div className="px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-400"></span>
              <span className="text-xs font-semibold text-indigo-300 tracking-wider">V2 CONTROL LOOP</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Command Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* LEFT COLUMN: Infrastructure Landscape (7 cols) */}
        <section className="lg:col-span-7 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight text-slate-100 flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-400" />
              Infrastructure Landscape
            </h2>
            <span className="text-xs text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
              Linode Cloud Sync
            </span>
          </div>

          {/* Infrastructure Topology Visual Grid */}
          <div className="glass rounded-xl p-6 relative overflow-hidden flex-1 min-h-[460px] flex flex-col justify-between">
            {/* Ambient Background Grid Effect */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none"></div>
            
            {/* SVG Connecting Paths to represent MQTT pipeline */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none hidden sm:block" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="po-to-hq" x1="50%" y1="0%" x2="50%" y2="100%">
                  <stop offset="0%" stopColor="#818cf8" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="po-to-branch" x1="0%" y1="50%" x2="100%" y2="50%">
                  <stop offset="0%" stopColor="#818cf8" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.6" />
                </linearGradient>
              </defs>
              {/* HQ to Post Office */}
              <line x1="50%" y1="75px" x2="50%" y2="190px" stroke="url(#po-to-hq)" strokeWidth="2" strokeDasharray="4 4" />
              
              {/* Post Office to Branch 1 */}
              <path d="M 50% 210 L 15% 320" stroke="#818cf8" strokeWidth="2" strokeOpacity="0.4" />
              {/* Post Office to Branch 2 */}
              <path d="M 50% 210 L 50% 320" stroke="#10b981" strokeWidth="2" strokeOpacity="0.4" strokeDasharray="3 3" />
              {/* Post Office to Branch 3 */}
              <path d="M 50% 210 L 85% 320" stroke="#ef4444" strokeWidth="2" strokeOpacity="0.2" />
            </svg>

            {/* Topology Layer 1: Core Command HQ */}
            <div className="flex justify-center z-10">
              <button 
                onClick={() => setSelectedNode('hq')}
                className={`flex flex-col items-center p-4 rounded-xl border transition-all duration-300 w-48 ${
                  selectedNode === 'hq' 
                    ? 'bg-indigo-500/10 border-indigo-500/80 shadow-lg shadow-indigo-500/10' 
                    : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="w-12 h-12 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-2">
                  <Server className="w-6 h-6 animate-pulse" />
                </div>
                <span className="text-sm font-bold text-white tracking-wide">HQ Command Server</span>
                <span className="text-[10px] font-mono text-indigo-300 mt-1">127.0.0.1 (Tauri)</span>
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-[9px] font-semibold text-slate-300">ACTIVE</span>
                </div>
              </button>
            </div>

            {/* Topology Layer 2: MQTT Broker Node (Linode Post Office) */}
            <div className="flex justify-center z-10 my-4">
              <button 
                onClick={() => setSelectedNode('po')}
                className={`flex flex-col items-center p-3 rounded-xl border transition-all duration-300 w-44 ${
                  selectedNode === 'po' 
                    ? 'bg-indigo-500/10 border-indigo-500/80 shadow-lg shadow-indigo-500/10' 
                    : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="w-10 h-10 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-2">
                  <Network className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-white tracking-wide">Linode Post Office</span>
                <span className="text-[10px] font-mono text-indigo-300 mt-0.5">Configured MQTT broker</span>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-[9px] font-semibold text-slate-300">ONLINE</span>
                </div>
              </button>
            </div>

            {/* Topology Layer 3: Remote Branch Worker Nodes */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 z-10">
              {branches.map(branch => {
                const cardColors = {
                  ONLINE: 'hover:border-emerald-500/30 border-slate-800/80',
                  STANDBY: 'hover:border-amber-500/30 border-slate-800/80',
                  OFFLINE: 'border-slate-900/80 opacity-50 bg-slate-900/20'
                };

                return (
                  <button 
                    key={branch.id}
                    onClick={() => setSelectedNode(branch.id)}
                    className={`flex flex-col items-center p-3.5 rounded-xl border bg-slate-900/40 transition-all duration-300 ${cardColors[branch.status]} ${
                      selectedNode === branch.id ? 'border-indigo-500 bg-indigo-500/5 shadow-md shadow-indigo-500/5' : ''
                    }`}
                  >
                    <div className="relative mb-2">
                      <div className="w-9 h-9 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
                        <Laptop className="w-5 h-5" />
                      </div>
                      <span className={`absolute -bottom-1 -right-1 w-2.5 h-2.5 rounded-full border-2 border-slate-950 ${
                        branch.status === 'ONLINE' ? 'bg-emerald-500' : branch.status === 'STANDBY' ? 'bg-amber-500' : 'bg-rose-500'
                      }`}></span>
                    </div>
                    <span className="text-[11px] font-bold text-slate-200 tracking-wide text-center">{branch.name}</span>
                    <span className="text-[9px] font-mono text-slate-400 mt-0.5">{branch.ip}</span>
                    <span className="text-[8px] font-semibold mt-1 px-1.5 py-0.5 rounded bg-slate-900/60 text-slate-300">
                      {branch.id}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Interactive Info / Metrics panel (based on selected node) */}
          <div className="glass rounded-xl p-5">
            {selectedNode === 'hq' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>CPU LOAD</span>
                    <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold font-mono text-white">{cpuUsage.toFixed(1)}%</div>
                  <div className="w-full bg-slate-900 h-1 rounded overflow-hidden mt-1.5">
                    <div className="bg-indigo-500 h-full transition-all duration-300" style={{ width: `${cpuUsage}%` }}></div>
                  </div>
                </div>
                <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>RAM ALLOCATION</span>
                    <Database className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold font-mono text-white">{memoryUsage.toFixed(1)}%</div>
                  <div className="w-full bg-slate-900 h-1 rounded overflow-hidden mt-1.5">
                    <div className="bg-indigo-500 h-full transition-all duration-300" style={{ width: `${memoryUsage}%` }}></div>
                  </div>
                </div>
                <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>TAURI RUNTIME</span>
                    <Radio className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold text-white font-mono">v{APP_VERSION}</div>
                  <div className="text-[10px] text-slate-500 mt-1 font-semibold">Tauri Desktop Shell Enabled</div>
                </div>
              </div>
            )}

            {selectedNode === 'po' && (
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                    <Radio className="w-5 h-5 animate-pulse" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-200">MQTT BROKER - LINODE INSTANCE</h3>
                    <p className="text-[11px] text-indigo-300 font-mono">agency/tasks/&lt;branch&gt; | agency/status/#</p>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <span className="block text-[9px] text-slate-400">LATENCY</span>
                    <span className="text-sm font-bold font-mono text-white">{brokerLatency.toFixed(0)} ms</span>
                  </div>
                  <div className="text-right">
                    <span className="block text-[9px] text-slate-400">ACTIVE CLIENTS</span>
                    <span className="text-sm font-bold font-mono text-emerald-400">2 Nodes</span>
                  </div>
                </div>
              </div>
            )}

            {selectedNode && selectedNode.startsWith('branch_') && (
              (() => {
                const node = branches.find(b => b.id === selectedNode);
                if (!node) return null;
                return (
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-indigo-400">
                        <Terminal className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-xs font-bold text-slate-200">{node.name} Details</h3>
                        <p className="text-[11px] text-slate-400">Assigned Persona: <strong className="text-indigo-400 font-semibold">{node.persona}</strong></p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <span className="block text-[9px] text-slate-400">IP ADDRESS</span>
                        <span className="text-xs font-bold font-mono text-white">{node.ip}</span>
                      </div>
                      <div className="text-right">
                        <span className="block text-[9px] text-slate-400">TASKS RUN</span>
                        <span className="text-xs font-bold font-mono text-indigo-400">{node.taskCount} Total</span>
                      </div>
                      <div className="text-right">
                        <span className="block text-[9px] text-slate-400">STATUS</span>
                        <span className={`text-[10px] font-bold tracking-wide ${
                          node.status === 'ONLINE' ? 'text-emerald-400' : node.status === 'STANDBY' ? 'text-amber-400' : 'text-rose-400'
                        }`}>{node.status}</span>
                      </div>
                    </div>
                  </div>
                );
              })()
            )}
          </div>

          {/* Task Results: live feedback loop from the branch daemons */}
          <div className="glass rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100 flex items-center gap-2 m-0">
                <Activity className="w-4 h-4 text-indigo-400" />
                Task Results
              </h3>
              <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                agency/status/#
              </span>
            </div>

            {statuses.length === 0 ? (
              <div className="border border-dashed border-slate-800 rounded-lg p-4 text-center">
                <span className="text-[11px] text-slate-500 italic">
                  No results yet. Run hq_status_listener.py and dispatch a task.
                </span>
              </div>
            ) : (
              <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                {statuses.map((s) => {
                  const ok = s.status === 'success' || s.status === 'pass';
                  const accepted = s.status === 'accepted';
                  const badge = ok
                    ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-500'
                    : accepted
                      ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-500'
                      : 'bg-rose-500/10 border-rose-500/40 text-rose-500';
                  const dot = ok ? 'bg-emerald-500' : accepted ? 'bg-indigo-500' : 'bg-rose-500';

                  return (
                    <div key={s.task_id} className="bg-slate-900/60 border border-slate-800 rounded-lg p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-mono text-slate-200 truncate">{s.task_id}</span>
                        <span className={`flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${badge}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${dot}`}></span>
                          {s.status}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-[9px] font-mono text-slate-500">
                        {s.branch_name && <span className="truncate">{s.branch_name}</span>}
                        {s.base_branch && <span>base:{s.base_branch}</span>}
                        {s.commit_hash && <span>#{s.commit_hash.substring(0, 8)}</span>}
                        {s.file_changes && <span>diff</span>}
                        {s.received_at && <span className="ml-auto">{new Date(s.received_at).toLocaleTimeString()}</span>}
                      </div>
                      {!ok && s.stderr && (
                        <p className="mt-1.5 text-[9px] font-mono text-rose-400/80 line-clamp-2 break-all">
                          {s.stderr.trim().split('\n').slice(-2).join(' ').substring(0, 200)}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          {/* Active Projects: lifecycle panel polled from projects/ directory */}
          <div className="glass rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100 flex items-center gap-2 m-0">
                <FolderKanban className="w-4 h-4 text-amber-400" />
                Active Projects
              </h3>
              <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                projects/*/manifest.json
              </span>
            </div>

            {projects.length === 0 ? (
              <div className="border border-dashed border-slate-800 rounded-lg p-4 text-center">
                <span className="text-[11px] text-slate-500 italic">
                  No projects yet. Dispatch a Project Intake to start.
                </span>
              </div>
            ) : (
              <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
                {projects.map((p) => {
                  const stageChip = 'bg-indigo-500/10 border-indigo-500/40 text-indigo-300';
                  const isPendingApproval = p.status === 'stage_pending_approval';
                  const isAwaitingAnswers = p.status === 'awaiting_ceo_answers';
                  const isBoardMeeting = p.status === 'board_meeting';

                  const statusColor =
                    p.status === 'stage_in_progress' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/40'
                    : isPendingApproval ? 'text-amber-300 bg-amber-500/10 border-amber-500/40'
                    : isAwaitingAnswers ? 'text-rose-300 bg-rose-500/10 border-rose-500/40'
                    : isBoardMeeting ? 'text-purple-300 bg-purple-500/10 border-purple-500/40'
                    : p.status === 'closed' ? 'text-slate-400 bg-slate-800/60 border-slate-700'
                    : 'text-slate-300 bg-slate-800/60 border-slate-700';

                  const actionColor = p.open_action === 'CEO'
                    ? 'text-amber-300 bg-amber-500/10 border-amber-500/30'
                    : 'text-indigo-300 bg-indigo-500/10 border-indigo-500/30';

                  const handleApprove = async () => {
                    try {
                      const home = await homeDir();
                      await writeTextFile(`${home}/Development/TheOffice/ai-agency-workspace/hq-backend/projects/${p.project_id}/ceo_approval.flag`, '');
                    } catch (err) {
                      alert(`Write error: ${err instanceof Error ? err.message : String(err)}`);
                    }
                  };

                  const handleSubmitAnswers = async () => {
                    const text = answerDrafts[p.project_id] ?? '';
                    if (!text.trim()) return;
                    try {
                      const home = await homeDir();
                      await writeTextFile(`${home}/Development/TheOffice/ai-agency-workspace/hq-backend/projects/${p.project_id}/ceo_answers.md`, text);
                      setAnswerDrafts(prev => ({ ...prev, [p.project_id]: '' }));
                    } catch (err) {
                      alert(`Write error: ${err instanceof Error ? err.message : String(err)}`);
                    }
                  };

                  const handleCloseBoard = async () => {
                    const text = decisionDrafts[p.project_id] ?? '';
                    if (!text.trim()) return;
                    try {
                      const home = await homeDir();
                      const base = `${home}/Development/TheOffice/ai-agency-workspace/hq-backend/projects/${p.project_id}`;
                      await writeTextFile(`${base}/decisions/${Date.now()}.md`, text);
                      await writeTextFile(`${base}/ceo_approval.flag`, '');
                      setDecisionDrafts(prev => ({ ...prev, [p.project_id]: '' }));
                    } catch (err) {
                      alert(`Write error: ${err instanceof Error ? err.message : String(err)}`);
                    }
                  };

                  return (
                    <div key={p.project_id} className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-bold text-slate-100 truncate">{p.name}</span>
                        <span className="text-[9px] font-mono text-slate-500 whitespace-nowrap">
                          {p.updated_at ? new Date(p.updated_at).toLocaleTimeString() : '—'}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${stageChip}`}>
                          {p.stage}
                        </span>
                        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${statusColor}`}>
                          {p.status.replace(/_/g, ' ')}
                        </span>
                        {p.open_action && (
                          <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border flex items-center gap-1 ${actionColor}`}>
                            {p.open_action === 'CEO' ? <ShieldAlert className="w-2.5 h-2.5" /> : <ClipboardCheck className="w-2.5 h-2.5" />}
                            {p.open_action}
                          </span>
                        )}
                      </div>

                      {isPendingApproval && (
                        <button
                          onClick={handleApprove}
                          className="w-full mt-1 h-8 rounded-lg border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 transition-colors"
                        >
                          <ClipboardCheck className="w-3.5 h-3.5" />
                          Approve Stage
                        </button>
                      )}

                      {isAwaitingAnswers && (
                        <div className="space-y-1.5 pt-1">
                          <label className="text-[9px] font-semibold text-rose-400 uppercase tracking-wider flex items-center gap-1">
                            <MessageSquareWarning className="w-3 h-3" />
                            CEO Answers Required
                          </label>
                          <textarea
                            value={answerDrafts[p.project_id] ?? ''}
                            onChange={(e) => setAnswerDrafts(prev => ({ ...prev, [p.project_id]: e.target.value }))}
                            rows={3}
                            placeholder="Answer the open questions..."
                            className="w-full bg-slate-950/80 border border-rose-500/30 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-rose-500/60 resize-none font-sans"
                          />
                          <button
                            onClick={handleSubmitAnswers}
                            disabled={!(answerDrafts[p.project_id] ?? '').trim()}
                            className="w-full h-8 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                          >
                            <Send className="w-3 h-3" />
                            Submit Answers
                          </button>
                        </div>
                      )}

                      {isBoardMeeting && (
                        <div className="space-y-1.5 pt-1">
                          <label className="text-[9px] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                            <ShieldAlert className="w-3 h-3" />
                            Board Meeting Open
                          </label>
                          <textarea
                            value={decisionDrafts[p.project_id] ?? ''}
                            onChange={(e) => setDecisionDrafts(prev => ({ ...prev, [p.project_id]: e.target.value }))}
                            rows={3}
                            placeholder="Enter board decisions..."
                            className="w-full bg-slate-950/80 border border-purple-500/30 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-purple-500/60 resize-none font-sans"
                          />
                          <button
                            onClick={handleCloseBoard}
                            disabled={!(decisionDrafts[p.project_id] ?? '').trim()}
                            className="w-full h-8 rounded-lg border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                          >
                            <ClipboardCheck className="w-3.5 h-3.5" />
                            Close Meeting
                          </button>
                        </div>
                      )}

                      {(() => {
                        const issues = issuesByProject[p.project_id] ?? [];
                        if (issues.length === 0) return null;
                        const blocking = issues.filter(i => i.severity === 'block');
                        const questions = issues.filter(i => i.severity === 'question');
                        const headerColor = blocking.length > 0
                          ? 'text-rose-300 border-rose-500/30'
                          : questions.length > 0
                            ? 'text-amber-300 border-amber-500/30'
                            : 'text-slate-300 border-slate-700';
                        return (
                          <div className={`mt-2 pt-2 border-t ${headerColor}`}>
                            <div className={`text-[9px] font-bold uppercase tracking-wider flex items-center gap-1 ${headerColor}`}>
                              <MessageSquareWarning className="w-3 h-3" />
                              Issues ({issues.length}{blocking.length > 0 ? `, ${blocking.length} block` : ''})
                            </div>
                            <ul className="mt-1 space-y-1 max-h-[120px] overflow-y-auto">
                              {issues.slice(0, 5).map(iss => {
                                const sevDot = iss.severity === 'block'
                                  ? 'bg-rose-500'
                                  : iss.severity === 'question'
                                    ? 'bg-amber-500'
                                    : 'bg-slate-500';
                                return (
                                  <li key={iss.issue_id} className="flex items-start gap-1.5 text-[10px] text-slate-300">
                                    <span className={`mt-1 w-1.5 h-1.5 rounded-full ${sevDot} flex-shrink-0`}></span>
                                    <span className="flex-1 break-words">
                                      <span className="font-mono text-slate-500">{iss.from_agent}:</span>{' '}
                                      <span className="text-slate-200">{iss.subject}</span>
                                      {iss.requires && (
                                        <span className="ml-1 text-[8px] uppercase font-bold text-slate-500">→{iss.requires}</span>
                                      )}
                                    </span>
                                  </li>
                                );
                              })}
                              {issues.length > 5 && (
                                <li className="text-[9px] text-slate-500 italic">+{issues.length - 5} more</li>
                              )}
                            </ul>
                          </div>
                        );
                      })()}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN: The Dispatch Control Form (5 cols) */}
        <section className="lg:col-span-5 flex flex-col gap-6">
          <div className="flex items-center gap-2">
            <Workflow className="w-5 h-5 text-indigo-400" />
            <h2 className="text-xl font-semibold tracking-tight text-slate-100 m-0">
              Task Dispatch Terminal
            </h2>
          </div>

          <div className="glass rounded-xl p-6 flex flex-col justify-between flex-1">
            
            {/* Workspace Selection Section */}
            <div className="mb-5 pb-5 border-b border-slate-800/80 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider block">
                  Target Project Workspace
                </label>
                {workspacePath && (
                  <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    Selected
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleSelectWorkspace}
                  className="flex items-center justify-center gap-2 px-4 py-2 border border-indigo-500/30 hover:border-indigo-500/80 bg-indigo-500/5 hover:bg-indigo-500/10 text-xs font-semibold text-indigo-300 hover:text-indigo-200 rounded-lg transition-all shadow-md shadow-indigo-500/5 w-full"
                >
                  <FolderOpen className="w-4 h-4 text-indigo-400" />
                  Select Workspace Folder
                </button>
              </div>
              {workspacePath ? (
                <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-2.5 flex items-start gap-2.5">
                  <div className="w-2 h-2 mt-1.5 rounded-full bg-indigo-400 flex-shrink-0 animate-pulse"></div>
                  <div className="min-w-0 flex-1">
                    <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider">Absolute Workspace Path</span>
                    <span className="text-[10px] font-mono text-indigo-200 block break-all font-medium select-all">{workspacePath}</span>
                  </div>
                </div>
              ) : (
                <div className="border border-dashed border-amber-500/20 bg-amber-500/5 rounded-lg p-2.5 text-center flex flex-col items-center gap-1 animate-pulse">
                  <span className="text-[10px] font-semibold text-amber-300">No Workspace Target Configured</span>
                  <span className="text-[9px] text-slate-400 max-w-[280px]">You must select a local directory on your machine before dispatching tasks.</span>
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-950/70 border border-slate-800 p-1">
                <button
                  type="button"
                  onClick={() => setDispatchMode('single')}
                  className={`h-9 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all ${
                    dispatchMode === 'single'
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/15'
                      : 'text-slate-400 hover:text-indigo-300'
                  }`}
                >
                  Single Task
                </button>
                <button
                  type="button"
                  onClick={() => setDispatchMode('epic')}
                  className={`h-9 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all ${
                    dispatchMode === 'epic'
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-500/15'
                      : 'text-slate-400 hover:text-emerald-300'
                  }`}
                >
                  Epic Builder
                </button>
                <button
                  type="button"
                  onClick={() => setDispatchMode('project')}
                  className={`h-9 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all ${
                    dispatchMode === 'project'
                      ? 'bg-amber-600 text-white shadow-md shadow-amber-500/15'
                      : 'text-slate-400 hover:text-amber-300'
                  }`}
                >
                  Projects
                </button>
              </div>

              {dispatchMode === 'project' ? (
                <div className="space-y-3">
                  <label className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider block">
                    Project Intake
                  </label>
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                      Project Name
                    </label>
                    <input
                      type="text"
                      required
                      value={projectName}
                      onChange={(e) => setProjectName(e.target.value)}
                      placeholder="e.g. Customer Portal V2"
                      className="w-full bg-slate-900/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/50"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                      CEO Brief
                    </label>
                    <textarea
                      required
                      value={projectBrief}
                      onChange={(e) => setProjectBrief(e.target.value)}
                      rows={6}
                      placeholder="Describe the project goals, constraints, and success criteria."
                      className="w-full bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/50 resize-none font-sans"
                    />
                  </div>
                </div>
              ) : dispatchMode === 'single' ? (
                <>
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                      Generated Task ID (UUID)
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <span className="absolute left-3 top-2.5 text-indigo-400">
                          <FileCode2 className="w-4 h-4" />
                        </span>
                        <input
                          type="text"
                          value={taskId}
                          readOnly
                          className="w-full bg-slate-900/80 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-indigo-300 focus:outline-none focus:border-indigo-500/50"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleRegenId}
                        className="p-2 border border-slate-800 rounded-lg bg-slate-900/60 hover:bg-slate-900 text-slate-400 hover:text-indigo-400 transition-colors"
                        title="Regenerate UUID"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                      Task Category
                    </label>
                    <div className="relative">
                      <select
                        value={taskType}
                        onChange={(e) => setTaskType(e.target.value)}
                        className="w-full bg-slate-900/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer"
                      >
                        <option value="frontend">Frontend Development (Cursor &rarr; Pixel)</option>
                        <option value="backend">Backend Development (Codex &rarr; Linus)</option>
                        <option value="architecture">System Architecture (Claude &rarr; Ada)</option>
                        <option value="qa">Quality Assurance (Codex &rarr; Kent)</option>
                      </select>
                      <div className="absolute right-3 top-3 pointer-events-none w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[4px] border-t-slate-400"></div>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                      Agent Instruction Prompt
                    </label>
                    <textarea
                      required
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      rows={6}
                      placeholder="e.g. Scaffold the login module. Write tests for standard forms and link validation."
                      className="w-full bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500/50 resize-none font-sans"
                    />
                  </div>
                </>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">
                      DAG Task Graph
                    </label>
                    <button
                      type="button"
                      onClick={addEpicTask}
                      className="h-8 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/15 text-emerald-300 text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Task
                    </button>
                  </div>

                  <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                    {epicTasks.map((task, index) => (
                      <div key={task.task_id} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <div className="relative flex-1">
                            <span className="absolute left-3 top-2.5 text-emerald-400">
                              <Workflow className="w-4 h-4" />
                            </span>
                            <input
                              type="text"
                              value={task.task_id}
                              readOnly
                              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-emerald-300 focus:outline-none"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => removeEpicTask(task.task_id)}
                            disabled={epicTasks.length === 1}
                            className="p-2 border border-slate-800 rounded-lg bg-slate-950/60 hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                            title="Remove task"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <select
                            value={task.type}
                            onChange={(e) => updateEpicTask(task.task_id, { type: e.target.value })}
                            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50 appearance-none cursor-pointer"
                          >
                            <option value="frontend">Frontend (Pixel)</option>
                            <option value="backend">Backend (Linus)</option>
                            <option value="architecture">Architecture (Ada)</option>
                            <option value="qa">QA (Kent)</option>
                          </select>
                          <input
                            type="text"
                            list={`depends-options-${task.task_id}`}
                            value={task.depends_on}
                            onChange={(e) => updateEpicTask(task.task_id, { depends_on: e.target.value })}
                            placeholder={index === 0 ? "depends_on" : epicTasks[index - 1]?.task_id}
                            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                          />
                          <datalist id={`depends-options-${task.task_id}`}>
                            {epicTasks
                              .slice(0, index)
                              .map(previousTask => (
                                <option key={previousTask.task_id} value={previousTask.task_id} />
                              ))}
                          </datalist>
                        </div>

                        <textarea
                          required
                          value={task.prompt}
                          onChange={(e) => updateEpicTask(task.task_id, { prompt: e.target.value })}
                          rows={3}
                          placeholder="Agent instruction"
                          className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50 resize-none font-sans"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={
                  !workspacePath ||
                  (dispatchMode === 'single'
                    ? !prompt.trim()
                    : dispatchMode === 'epic'
                      ? !epicTasks.every(task => task.prompt.trim())
                      : !projectName.trim() || !projectBrief.trim())
                }
                className={`w-full py-2.5 px-4 rounded-lg font-bold text-xs tracking-wider text-white shadow-lg flex items-center justify-center gap-2 transition-all disabled:opacity-40 disabled:pointer-events-none disabled:shadow-none ${
                  dispatchMode === 'single'
                    ? 'bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 shadow-indigo-500/10 hover:shadow-indigo-500/25'
                    : dispatchMode === 'epic'
                      ? 'bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 shadow-emerald-500/10 hover:shadow-emerald-500/25'
                      : 'bg-amber-600 hover:bg-amber-500 active:bg-amber-700 shadow-amber-500/10 hover:shadow-amber-500/25'
                }`}
              >
                <Send className="w-3.5 h-3.5" />
                {dispatchMode === 'single' ? 'DISPATCH TASK' : dispatchMode === 'epic' ? 'DISPATCH EPIC' : 'DISPATCH PROJECT INTAKE'}
              </button>
            </form>

            {/* Displaying Live Log Feed inside form card */}
            <div className="mt-6 border-t border-slate-800/80 pt-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Live Dispatch Log
                </span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
              </div>
              <div className="bg-slate-900 border border-slate-900 rounded-lg p-3 font-mono text-[10px] h-[130px] overflow-y-auto space-y-1 text-slate-400 scroll-smooth">
                {lastPayload ? (
                  <>
                    <div className="text-emerald-400">[INFO] Task initialized at {new Date(lastPayload.timestamp).toLocaleTimeString()}</div>
                    <div className="text-indigo-300">&gt; Target Persona: {lastPayload.routing_target}</div>
                    <div className="text-indigo-300">
                      &gt; Target Queue: {lastPayload.queue_type === 'epic' ? 'epic_queue/epic_' : lastPayload.queue_type === 'project' ? 'project_queue/' : 'task_queue/task_'}{lastPayload.task_id.substring(0, 8)}{lastPayload.queue_type === 'project' ? '.intake.json' : '.json'}
                    </div>
                    {lastPayload.task_count && (
                      <div className="text-emerald-300">&gt; DAG Nodes: {lastPayload.task_count}</div>
                    )}
                    <div className="text-slate-200 select-all overflow-hidden truncate max-w-full">
                      &gt; Payload: {JSON.stringify(lastPayload)}
                    </div>
                    <div className="text-emerald-500 font-semibold">
                      [SUCCESS] {lastPayload.queue_type === 'epic' ? 'Epic Dispatched to HQ Epic Manager.' : lastPayload.queue_type === 'project' ? 'Project Intake Dispatched to HQ Project Manager.' : 'Task Dispatched to HQ Router.'}
                    </div>
                  </>
                ) : (
                  <div className="text-slate-600 italic">No tasks dispatched yet. Terminal waiting...</div>
                )}
              </div>
            </div>
          </div>
        </section>

      </main>

      {/* Success Notification Toast */}
      {showToast && (
        <div className="fixed bottom-6 right-6 glass border-emerald-500/30 text-slate-100 px-4 py-3 rounded-lg shadow-2xl flex items-center gap-3 animate-bounce z-50">
          <div className="w-6 h-6 rounded-full bg-emerald-500/25 border border-emerald-500/50 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white">
              {lastPayload?.queue_type === 'epic'
                ? 'Epic Dispatched to HQ Epic Manager'
                : lastPayload?.queue_type === 'project'
                  ? 'Project Intake Dispatched to HQ Project Manager'
                  : 'Task Dispatched to HQ Router'}
            </h4>
            <p className="text-[10px] text-slate-300">
              Payload written directly to {lastPayload?.queue_type === 'epic' ? 'epic queue' : lastPayload?.queue_type === 'project' ? 'project queue' : 'task queue'}.
            </p>
          </div>
        </div>
      )}

      {/* Small Legal Footer */}
      <footer className="py-4 border-t border-slate-900 bg-slate-900/40 text-center">
        <span className="text-[10px] text-slate-600 font-mono uppercase tracking-widest">
          DevBoss Distributed Network © 2026
        </span>
      </footer>
    </div>
  );
}
