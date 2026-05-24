import { useState, useEffect } from 'react';
import { writeTextFile } from '@tauri-apps/plugin-fs';
import { homeDir } from '@tauri-apps/api/path';
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
  Layers,
  Terminal,
  Clock,
  Radio,
  FileCode2,
  Workflow
} from 'lucide-react';

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

export default function App() {
  const [taskId, setTaskId] = useState('');
  const [taskType, setTaskType] = useState('frontend');
  const [prompt, setPrompt] = useState('');
  const [lastPayload, setLastPayload] = useState<any>(null);
  const [showToast, setShowToast] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>('hq');
  
  // Real-time dynamic dashboard metrics
  const [cpuUsage, setCpuUsage] = useState(14);
  const [memoryUsage, setMemoryUsage] = useState(42);
  const [brokerLatency, setBrokerLatency] = useState(48);

  useEffect(() => {
    setTaskId(generateUUID());
    
    // Animate mock metrics for dynamic, live-system aesthetic
    const interval = setInterval(() => {
      setCpuUsage(prev => Math.max(8, Math.min(45, prev + (Math.random() * 6 - 3))));
      setMemoryUsage(prev => Math.max(38, Math.min(48, prev + (Math.random() * 2 - 1))));
      setBrokerLatency(prev => Math.max(35, Math.min(65, prev + (Math.random() * 10 - 5))));
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const handleRegenId = () => {
    setTaskId(generateUUID());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const routerPayload = {
      task_id: taskId,
      type: taskType,
      prompt: prompt.trim()
    };

    const uiPayload = {
      ...routerPayload,
      timestamp: new Date().toISOString(),
      sender: "CEO_HQ",
      routing_target: taskType === 'frontend' ? 'Pixel' : taskType === 'backend' ? 'Linus' : 'Ada'
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
      
      // Clear form input and prepare next task
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

  // Branch offices landscape data
  const branches: BranchNode[] = [
    { id: 'branch_1', name: 'Branch Office 1', ip: '172.16.80.12', status: 'ONLINE', persona: 'Linus (CTO)', taskCount: 8 },
    { id: 'branch_2', name: 'Branch Office 2', ip: '172.16.80.15', status: 'STANDBY', persona: 'Ada (Architect)', taskCount: 3 },
    { id: 'branch_3', name: 'Branch Office 3', ip: '172.16.80.20', status: 'OFFLINE', persona: 'Pixel (Frontend)', taskCount: 0 }
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500/30 selection:text-indigo-200">
      
      {/* Visual Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/20">
              <Layers className="w-5 h-5 text-white" />
              <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 pulse-glow"></div>
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white m-0">The Office AI</h1>
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
              <span className="text-xs font-semibold text-indigo-300 tracking-wider">PHASE 4 ACTIVE</span>
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
                <span className="text-[10px] font-mono text-indigo-300 mt-0.5">172.105.92.145:1883</span>
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
                  OFFLINE: 'border-slate-900/80 opacity-50 bg-slate-950/20'
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
                    <span className="text-[8px] font-semibold mt-1 px-1.5 py-0.5 rounded bg-slate-950/60 text-slate-300">
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
                <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>CPU LOAD</span>
                    <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold font-mono text-white">{cpuUsage.toFixed(1)}%</div>
                  <div className="w-full bg-slate-900 h-1 rounded overflow-hidden mt-1.5">
                    <div className="bg-indigo-500 h-full transition-all duration-300" style={{ width: `${cpuUsage}%` }}></div>
                  </div>
                </div>
                <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>RAM ALLOCATION</span>
                    <Database className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold font-mono text-white">{memoryUsage.toFixed(1)}%</div>
                  <div className="w-full bg-slate-900 h-1 rounded overflow-hidden mt-1.5">
                    <div className="bg-indigo-500 h-full transition-all duration-300" style={{ width: `${memoryUsage}%` }}></div>
                  </div>
                </div>
                <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between items-center mb-1 text-[11px] text-slate-400">
                    <span>TAURI RUNTIME</span>
                    <Radio className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold text-white font-mono">v1.0.0</div>
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
                    <p className="text-[11px] text-indigo-300 font-mono">agency/tasks/# | agency/status/#</p>
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
            <form onSubmit={handleSubmit} className="space-y-5">
              
              {/* Task ID Input */}
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
                      className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-indigo-300 focus:outline-none focus:border-indigo-500/50" 
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

              {/* Task Type Dropdown */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Task Category
                </label>
                <div className="relative">
                  <select 
                    value={taskType}
                    onChange={(e) => setTaskType(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer"
                  >
                    <option value="frontend">Frontend Development (Cursor &rarr; Pixel)</option>
                    <option value="backend">Backend Development (Codex &rarr; Linus)</option>
                    <option value="architecture">System Architecture (Claude &rarr; Ada)</option>
                  </select>
                  <div className="absolute right-3 top-3 pointer-events-none w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[4px] border-t-slate-400"></div>
                </div>
              </div>

              {/* Task Prompt Area */}
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
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500/50 resize-none font-sans"
                />
              </div>

              {/* Dispatch Button */}
              <button 
                type="submit" 
                disabled={!prompt.trim()}
                className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:from-indigo-700 active:to-indigo-800 font-bold text-xs tracking-wider text-white shadow-lg shadow-indigo-500/10 flex items-center justify-center gap-2 transition-all hover:shadow-indigo-500/25 disabled:opacity-40 disabled:pointer-events-none disabled:shadow-none"
              >
                <Send className="w-3.5 h-3.5" />
                DISPATCH AGENT TASK
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
              <div className="bg-slate-950 border border-slate-900 rounded-lg p-3 font-mono text-[10px] h-[130px] overflow-y-auto space-y-1 text-slate-400 scroll-smooth">
                {lastPayload ? (
                  <>
                    <div className="text-emerald-400">[INFO] Task initialized at {new Date(lastPayload.timestamp).toLocaleTimeString()}</div>
                    <div className="text-indigo-300">&gt; Target Persona: {lastPayload.routing_target}</div>
                    <div className="text-indigo-300">&gt; Target Queue: task_queue/{lastPayload.task_id.substring(0, 8)}.json</div>
                    <div className="text-slate-200 select-all overflow-hidden truncate max-w-full">
                      &gt; Payload: {JSON.stringify(lastPayload)}
                    </div>
                    <div className="text-emerald-500 font-semibold">[SUCCESS] Task Dispatched to HQ Router.</div>
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
            <h4 className="text-xs font-bold text-white">Task Dispatched to HQ Router</h4>
            <p className="text-[10px] text-slate-300">Payload written directly to task queue.</p>
          </div>
        </div>
      )}

      {/* Small Legal Footer */}
      <footer className="py-4 border-t border-slate-900 bg-slate-950/40 text-center">
        <span className="text-[10px] text-slate-600 font-mono uppercase tracking-widest">
          The Office AI Distributed Network © 2026
        </span>
      </footer>
    </div>
  );
}
