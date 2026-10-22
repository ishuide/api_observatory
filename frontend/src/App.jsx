import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Database, Cpu, Activity, AlertTriangle,
  Trash2, RefreshCw, Plus, Terminal, Layers, Pencil,
  UploadCloud, Share2
} from "lucide-react";
import DependencyGraph from "./DependencyGraph";

const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:5000/api`;

export default function App() {
  const [data, setData] = useState({ agents: [], resources: [], workflows: [], dependencies: [], teams: [], companies: [] });
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [activeTab, setActiveTab] = useState("registry"); // 'registry' | 'graph' | 'blast' | 'audit'
  const [auditLogs, setAuditLogs] = useState([]);
  const [impactData, setImpactData] = useState([]);
  const [selectedResource, setSelectedResource] = useState("");
  const [notice, setNotice] = useState(null);
  const [authUser, setAuthUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [adminUsers, setAdminUsers] = useState([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "Viewer" });
  const fileInputRef = useRef(null);
  const csrfTokenRef = useRef(null);

  useEffect(() => {
    csrfTokenRef.current = authUser?.csrf_token || null;
  }, [authUser]);

  // Form states
  const [newAgent, setNewAgent] = useState({ name: "", purpose: "", team_id: "" });
  const [editingAgentId, setEditingAgentId] = useState(null);
  const [newResource, setNewResource] = useState({ name: "", resource_type: "API", endpoint_url: "", company_id: "" });
  const [editingResourceId, setEditingResourceId] = useState(null);
  const [newDep, setNewDep] = useState({ agent_id: "", resource_id: "", dependency_type: "Inference", is_critical: true });


  const notify = (msg, type = "info") => {
    setNotice({ msg, type });
    setTimeout(() => setNotice(null), 5000);
  };

  const apiFetch = useCallback((path, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (csrfTokenRef.current && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase())) {
      headers.set("X-CSRF-Token", csrfTokenRef.current);
    }
    return fetch(`${API}${path}`, {
      ...options,
      headers,
      credentials: "include"
    });
  }, []);

  const hasPermission = (permission) => authUser?.permissions?.includes(permission) || false;

  const fetchOverview = useCallback(async (companyId = selectedCompanyId) => {
    try {
      const query = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
      const res = await apiFetch(`/overview${query}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setData(json);
      if (!companyId && json.companies.length > 0) {
        setSelectedCompanyId(String(json.companies[0].company_id));
      }
      if (json.teams.length > 0) {
        if (!newAgent.team_id) setNewAgent(prev => ({ ...prev, team_id: json.teams[0].team_id }));
      }
    } catch (error) {
      notify(`Failed to connect to backend API: ${error.message}`, "error");
    }
  }, [newAgent.team_id, apiFetch, selectedCompanyId]);

  const fetchAudit = async () => {
    const res = await apiFetch("/audit");
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Could not load audit history");
    setAuditLogs(json);
  };

  useEffect(() => {
    let cancelled = false;
    apiFetch("/auth/me")
      .then(async response => {
        if (response.ok) return response.json();
        return null;
      })
      .then(user => { if (!cancelled) setAuthUser(user); })
      .catch(() => { if (!cancelled) setAuthUser(null); })
      .finally(() => { if (!cancelled) setAuthChecked(true); });
    return () => { cancelled = true; };
  }, [apiFetch]);

  useEffect(() => {
    if (authUser) fetchOverview(selectedCompanyId);
  }, [authUser, fetchOverview, selectedCompanyId]);

  const handleLogin = async (event) => {
    event.preventDefault();
    try {
      const response = await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Login failed");
      setAuthUser(result);
      setLoginForm({ username: "", password: "" });
      notify(`Signed in as ${result.username}`, "success");
    } catch (error) {
      notify(error.message, "error");
    }
  };

  const handleLogout = async () => {
    await apiFetch("/auth/logout", { method: "POST" });
    setAuthUser(null);
    setData({ agents: [], resources: [], workflows: [], dependencies: [], teams: [], companies: [] });
    setActiveTab("registry");
  };

  const loadUsers = async () => {
    const response = await apiFetch("/admin/users");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not load users");
    setAdminUsers(result);
  };

  const handleCreateUser = async (event) => {
    event.preventDefault();
    const response = await apiFetch("/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newUser)
    });
    const result = await response.json();
    if (response.ok) {
      notify("User created", "success");
      setNewUser({ username: "", password: "", role: "Viewer" });
      loadUsers();
    } else {
      notify(result.error, "error");
    }
  };

  const handleUpdateUser = async (user, role, isActive) => {
    const response = await apiFetch(`/admin/users/${user.user_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, is_active: isActive })
    });
    const result = await response.json();
    if (response.ok) {
      notify("User access updated", "success");
      loadUsers();
    } else {
      notify(result.error, "error");
    }
  };

  const handleCascadeFail = async (id) => {
    const res = await apiFetch(`/resources/${id}/deactivate`, { method: "POST" });
    const json = await res.json();
    if (res.ok) {
      notify("Procedure Executed: Resource offline & dependents disabled", "warn");
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
  };

  const handleRecover = async (id) => {
    const res = await apiFetch(`/resources/${id}/recover`, { method: "POST" });
    const json = await res.json();
    if (res.ok) {
      notify("Resource restored & dependent agents re-enabled", "success");
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
  };

  const handleRegisterAgent = async (e) => {
    e.preventDefault();
    const res = await apiFetch(`/agents${editingAgentId ? `/${editingAgentId}` : ""}`, {
      method: editingAgentId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newAgent)
    });
    const json = await res.json();
    if (res.ok) {
      notify(editingAgentId ? "Agent updated" : "Agent registered successfully", "success");
      setEditingAgentId(null);
      setNewAgent({ name: "", purpose: "", team_id: data.teams[0]?.team_id || "" });
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
  };

  const handleDeleteAgent = async (id) => {
    const res = await apiFetch(`/agents/${id}`, { method: "DELETE" });
    if (res.ok) {
      notify("Agent removed", "info");
      fetchOverview();
    }
  };

  const handleEditAgent = (agent) => {
    setEditingAgentId(agent.agent_id);
    setNewAgent({
      name: agent.name,
      purpose: agent.purpose,
      team_id: data.teams.find(team => team.name === agent.team_name)?.team_id || ""
    });
  };

  const handleSaveResource = async (e) => {
    e.preventDefault();
    const res = await apiFetch(editingResourceId ? `/resources/${editingResourceId}` : "/resources", {
      method: editingResourceId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...newResource,
        endpoint_url: newResource.endpoint_url || null,
        company_id: selectedCompanyId,
        status: editingResourceId ? newResource.status || "HEALTHY" : "HEALTHY"
      })
    });
    const json = await res.json();
    if (res.ok) {
      notify(editingResourceId ? "Resource updated" : "Resource created", "success");
      setNewResource({ name: "", resource_type: "API", endpoint_url: "", company_id: data.companies[0]?.company_id || "" });
      setEditingResourceId(null);
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
  };

  const handleEditResource = (resource) => {
    setEditingResourceId(resource.resource_id);
    setNewResource({
      name: resource.name,
      resource_type: resource.resource_type,
      endpoint_url: resource.endpoint_url || "",
      company_id: resource.company_id,
      status: resource.status
    });
  };

  const handleDeleteResource = async (resourceId) => {
    const res = await apiFetch(`/resources/${resourceId}`, { method: "DELETE" });
    const json = await res.json();
    if (res.ok) {
      notify("Resource deleted", "info");
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
  };

  const handleAddDependency = async (e) => {
    e.preventDefault();
    const res = await apiFetch("/dependencies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newDep)
    });
    const json = await res.json();
    if (res.ok) {
      notify("Dependency registered", "success");
      fetchOverview();
    } else {
      notify(json.error, "error"); // Catches BEFORE INSERT trigger check
    }
  };

  const handleRevokeDep = async (agentId, resId) => {
    const res = await apiFetch(`/dependencies/${agentId}/${resId}`, { method: "DELETE" });
    if (res.ok) {
      notify("Dependency binding removed", "info");
      fetchOverview();
    }
  };

  const runBlastRadius = async (resourceId) => {
    setSelectedResource(resourceId);
    if (!resourceId) {
      setImpactData([]);
      return;
    }
    const res = await apiFetch(`/impact/${resourceId}`);
    const json = await res.json();
    setImpactData(json);
  };


  // JSON Ingestion
  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    const res = await apiFetch("/ingest", {
      method: "POST",
      body: formData
    });
    const json = await res.json();
    if (res.ok) {
      notify(json.message, "success");
      fetchOverview();
    } else {
      notify(json.error, "error");
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  if (!authChecked) {
    return <div className="min-h-screen bg-slate-950 text-slate-200 grid place-items-center text-sm">Checking sign-in...</div>;
  }

  if (!authUser) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 grid place-items-center p-6">
        <form onSubmit={handleLogin} className="w-full max-w-sm space-y-4 border border-slate-800 bg-slate-900 p-6 rounded-lg">
          <div>
            <h1 className="text-lg font-bold">AI Agent Registry</h1>
            <p className="text-xs text-slate-400 mt-1">Sign in with your registry account.</p>
          </div>
          <label className="block text-xs text-slate-400">
            Username
            <input autoComplete="username" value={loginForm.username} onChange={e => setLoginForm({ ...loginForm, username: e.target.value })} className="mt-1 w-full bg-slate-950 border border-slate-700 p-2 rounded text-slate-100" required />
          </label>
          <label className="block text-xs text-slate-400">
            Password
            <input type="password" autoComplete="current-password" value={loginForm.password} onChange={e => setLoginForm({ ...loginForm, password: e.target.value })} className="mt-1 w-full bg-slate-950 border border-slate-700 p-2 rounded text-slate-100" required />
          </label>
          {notice?.type === "error" && <p role="alert" className="text-xs text-red-300">{notice.msg}</p>}
          <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 rounded p-2 text-sm font-semibold">Sign in</button>
        </form>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white">AI Agent Ecosystem Registry</h1>
            <p className="text-[11px] text-slate-400">MySQL-backed Agent, Resource & Workflow Registry</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("registry")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${activeTab === 'registry' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
            Registry Overview
          </button>
          <button
            onClick={() => setActiveTab("graph")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${activeTab === 'graph' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
            <Share2 className="w-3.5 h-3.5" /> Interactive Graph
          </button>
          <button
            onClick={() => setActiveTab("blast")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${activeTab === 'blast' ? 'bg-rose-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
            <AlertTriangle className="w-3.5 h-3.5" /> Blast Radius
          </button>
          <button
            onClick={() => { setActiveTab("audit"); fetchAudit(); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${activeTab === 'audit' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
            <Terminal className="w-3.5 h-3.5" /> Audit Logs (Triggers)
          </button>

          {hasPermission("users.manage") && (
            <button
              onClick={() => { setActiveTab("users"); loadUsers().catch(error => notify(error.message, "error")); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${activeTab === 'users' ? 'bg-amber-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>
              User Access
            </button>
          )}

          <label className="flex items-center gap-2 text-[11px] text-slate-400">
            Company
            <select
              value={selectedCompanyId}
              onChange={event => {
                setSelectedCompanyId(event.target.value);
                setSelectedResource("");
                setImpactData([]);
                setEditingAgentId(null);
                setEditingResourceId(null);
              }}
              className="max-w-44 bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-slate-200"
              aria-label="Select company registry"
            >
              {data.companies.map(company => (
                <option key={company.company_id} value={company.company_id}>{company.name}</option>
              ))}
            </select>
          </label>

          {/* Quick Config Ingest Trigger */}
          {hasPermission("imports.manage") && <div className="pl-2 border-l border-slate-800">
            <input
              type="file"
              accept=".json"
              multiple
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 font-medium cursor-pointer flex items-center gap-1.5 transition">
              <UploadCloud className="w-3.5 h-3.5 text-indigo-400" /> Import JSON
            </label>
          </div>}
          <div className="ml-2 border-l border-slate-700 pl-3 flex items-center gap-2">
            <span className="text-[11px] text-slate-400">{authUser.username} · {authUser.roles?.join(", ")}</span>
            <button onClick={handleLogout} className="px-2 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 rounded">Sign out</button>
          </div>
        </div>
      </header>

      {/* Notifications */}
      {notice && (
        <div className={`mx-8 mt-4 p-3 rounded-lg text-xs border flex items-center gap-2 ${notice.type === "error" ? "bg-red-950/60 border-red-800 text-red-300" :
          notice.type === "warn" ? "bg-amber-950/60 border-amber-800 text-amber-300" :
            notice.type === "success" ? "bg-emerald-950/60 border-emerald-800 text-emerald-300" :
              "bg-slate-900 border-slate-700 text-slate-300"
          }`}>
          <Activity className="w-4 h-4 shrink-0" />
          <span>{notice.msg}</span>
        </div>
      )}

      {/* Main Container */}
      <main className="p-8 flex-1">
        {/* TAB 1: REGISTRY OVERVIEW */}
        {activeTab === "registry" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Agents */}
              <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
                <div className="px-5 py-3.5 border-b border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    <h2 className="text-xs font-semibold uppercase tracking-wider">Registered Autonomous Agents</h2>
                  </div>
                  <span className="text-[11px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">{data.agents.length} Nodes</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950/50 text-slate-500 font-semibold border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-4">Agent Name</th>
                        <th className="py-2.5 px-4">Team</th>
                        <th className="py-2.5 px-4">Purpose</th>
                        <th className="py-2.5 px-4">Dependencies</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {data.agents.map((a) => (
                        <tr key={a.agent_id} className="hover:bg-slate-800/30">
                          <td className="py-2.5 px-4 font-semibold text-white">{a.name}</td>
                          <td className="py-2.5 px-4"><span className="bg-slate-800 border border-slate-700 px-2 py-0.5 rounded text-[11px]">{a.team_name}</span></td>
                          <td className="py-2.5 px-4 max-w-xs truncate text-slate-400">{a.purpose}</td>
                          <td className="py-2.5 px-4"><span className="bg-indigo-950/60 text-indigo-300 border border-indigo-800/50 px-2 py-0.5 rounded text-[11px]">{a.resource_count} Links</span></td>
                          <td className="py-2.5 px-4">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${a.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                              {a.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            {hasPermission("agents.manage") && <button onClick={() => handleEditAgent(a)} className="text-slate-500 hover:text-indigo-400 transition mr-3" title="Edit agent">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>}
                            {hasPermission("agents.manage") && <button onClick={() => handleDeleteAgent(a.agent_id)} className="text-slate-500 hover:text-red-400 transition">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Underlying Resources */}
              <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
                <div className="px-5 py-3.5 border-b border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-xs font-semibold uppercase tracking-wider">Underlying Resources</h2>
                  </div>
                  <span className="text-[11px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">{data.resources.length} Nodes</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950/50 text-slate-500 font-semibold border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-4">Resource</th>
                        <th className="py-2.5 px-4">Company</th>
                        <th className="py-2.5 px-4">Type</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {data.resources.map((r) => (
                        <tr key={r.resource_id} className="hover:bg-slate-800/30">
                          <td className="py-2.5 px-4 font-semibold text-white">{r.name}</td>
                          <td className="py-2.5 px-4 text-slate-400">{r.company_name}</td>
                          <td className="py-2.5 px-4"><span className="text-indigo-400 font-mono text-[11px]">{r.resource_type}</span></td>
                          <td className="py-2.5 px-4">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${r.status === 'HEALTHY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                              {r.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            {hasPermission("resources.manage") && <button onClick={() => handleEditResource(r)} className="text-slate-500 hover:text-indigo-400 transition mr-3" title="Edit resource">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>}
                            {hasPermission("resources.manage") && <button onClick={() => handleDeleteResource(r.resource_id)} className="text-slate-500 hover:text-red-400 transition mr-3" title="Delete resource">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>}
                            {hasPermission("resources.health") && (r.status !== 'OFFLINE' ? (
                              <button
                                onClick={() => handleCascadeFail(r.resource_id)}
                                className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 text-[10px] font-bold transition">
                                Cascade Fail
                              </button>
                            ) : (
                              <button
                                onClick={() => handleRecover(r.resource_id)}
                                className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 text-[10px] font-bold transition">
                                Restore
                              </button>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {hasPermission("resources.manage") && <form onSubmit={handleSaveResource} className="grid grid-cols-1 md:grid-cols-2 gap-2 p-4 border-t border-slate-800">
                  <input
                    type="text"
                    placeholder="Resource name"
                    value={newResource.name}
                    onChange={e => setNewResource({ ...newResource, name: e.target.value })}
                    className="bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    required
                  />
                  {!editingResourceId && (
                    <select
                      value={newResource.company_id}
                      onChange={e => setNewResource({ ...newResource, company_id: e.target.value })}
                      className="bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                      required
                    >
                      <option value="">Choose company</option>
                      {data.companies.map(company => <option key={company.company_id} value={company.company_id}>{company.name}</option>)}
                    </select>
                  )}
                  <select
                    value={newResource.resource_type}
                    onChange={e => setNewResource({ ...newResource, resource_type: e.target.value })}
                    className="bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  >
                    <option value="LLM">LLM</option>
                    <option value="API">API</option>
                    <option value="VECTOR_DB">Vector database</option>
                    <option value="MEMORY">Memory</option>
                    <option value="TOOL">Tool</option>
                  </select>
                  <input
                    type="url"
                    placeholder="Endpoint URL (optional)"
                    value={newResource.endpoint_url}
                    onChange={e => setNewResource({ ...newResource, endpoint_url: e.target.value })}
                    className="bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  />
                  {editingResourceId && (
                    <select
                      value={newResource.status}
                      onChange={e => setNewResource({ ...newResource, status: e.target.value })}
                      className="bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    >
                      <option value="HEALTHY">Healthy</option>
                      <option value="DEGRADED">Degraded</option>
                      <option value="OFFLINE">Offline</option>
                    </select>
                  )}
                  <div className="flex gap-2 md:col-span-2">
                    <button type="submit" className="px-3 py-2 bg-emerald-700 hover:bg-emerald-600 rounded text-xs font-semibold text-white">
                      {editingResourceId ? "Save Resource" : "Add Resource"}
                    </button>
                    {editingResourceId && (
                      <button type="button" onClick={() => { setEditingResourceId(null); setNewResource({ name: "", resource_type: "API", endpoint_url: "", company_id: data.companies[0]?.company_id || "" }); }} className="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded text-xs text-slate-200">
                        Cancel
                      </button>
                    )}
                  </div>
                </form>}
              </div>
            </div>

            {/* Dependency Matrix & Quick Registrations */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-8 bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
                <div className="px-5 py-3.5 border-b border-slate-800 flex justify-between items-center">
                  <h2 className="text-xs font-semibold uppercase tracking-wider">Architecture Dependency Matrix</h2>
                  <span className="text-[11px] text-slate-500">M:N Junction Table (agent_resources)</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950/50 text-slate-500 font-semibold border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-4">Agent</th>
                        <th className="py-2.5 px-4">Resource Target</th>
                        <th className="py-2.5 px-4">Type</th>
                        <th className="py-2.5 px-4">Criticality</th>
                        <th className="py-2.5 px-4 text-right">Revoke</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {data.dependencies.map((d, i) => (
                        <tr key={i} className="hover:bg-slate-800/30">
                          <td className="py-2.5 px-4 font-semibold text-white">{d.agent_name}</td>
                          <td className="py-2.5 px-4">
                            {d.resource_name} {d.resource_status === 'OFFLINE' && <span className="text-[10px] text-red-400 ml-1 font-bold">(Offline)</span>}
                          </td>
                          <td className="py-2.5 px-4 font-mono text-slate-400">{d.dependency_type}</td>
                          <td className="py-2.5 px-4">
                            {d.is_critical ? (
                              <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px]">Hard Fail</span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">Soft Fail</span>
                            )}
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            <button onClick={() => handleRevokeDep(d.agent_id, d.resource_id)} className="text-slate-500 hover:text-red-400 transition">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="lg:col-span-4 space-y-6">
                {/* Bind Dependency */}
                <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                    <Plus className="w-3.5 h-3.5 text-indigo-400" /> Bind Dependency
                  </h3>
                  {hasPermission("dependencies.manage") && <form onSubmit={handleAddDependency} className="space-y-3 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1">Select Agent</label>
                      <select
                        value={newDep.agent_id}
                        onChange={(e) => setNewDep({ ...newDep, agent_id: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200" required>
                        <option value="">-- Choose Agent --</option>
                        {data.agents.map(a => <option key={a.agent_id} value={a.agent_id}>{a.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Select Resource</label>
                      <select
                        value={newDep.resource_id}
                        onChange={(e) => setNewDep({ ...newDep, resource_id: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200" required>
                        <option value="">-- Choose Resource --</option>
                        {data.resources.map(r => (
                          <option key={r.resource_id} value={r.resource_id}>
                            {r.name} ({r.status})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="crit"
                        checked={newDep.is_critical}
                        onChange={e => setNewDep({ ...newDep, is_critical: e.target.checked })}
                        className="rounded border-slate-800 bg-slate-950"
                      />
                      <label htmlFor="crit" className="text-slate-400">Critical Dependency (Triggers Failure)</label>
                    </div>
                    <button type="submit" className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 rounded font-semibold text-white transition">
                      Bind Edge
                    </button>
                  </form>}
                </div>

                {/* Register Node */}
                <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                    <Plus className="w-3.5 h-3.5 text-emerald-400" /> {editingAgentId ? "Edit Agent" : "Onboard Agent"}
                  </h3>
                  {hasPermission("agents.manage") && <form onSubmit={handleRegisterAgent} className="space-y-3 text-xs">
                    <input
                      type="text"
                      placeholder="Agent Name"
                      value={newAgent.name}
                      onChange={e => setNewAgent({ ...newAgent, name: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200" required
                    />
                    <input
                      type="text"
                      placeholder="Purpose"
                      value={newAgent.purpose}
                      onChange={e => setNewAgent({ ...newAgent, purpose: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200" required
                    />
                    <select
                      value={newAgent.team_id}
                      onChange={e => setNewAgent({ ...newAgent, team_id: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200" required>
                      {data.teams.map(t => <option key={t.team_id} value={t.team_id}>{t.name}</option>)}
                    </select>
                    <button type="submit" className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded font-semibold text-white transition">
                      {editingAgentId ? "Save Agent" : "Register Node"}
                    </button>
                    {editingAgentId && (
                      <button type="button" onClick={() => { setEditingAgentId(null); setNewAgent({ name: "", purpose: "", team_id: data.teams[0]?.team_id || "" }); }} className="w-full py-2 bg-slate-800 hover:bg-slate-700 rounded font-semibold text-slate-200 transition">
                        Cancel Edit
                      </button>
                    )}
                  </form>}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: INTERACTIVE GRAPH CANVAS */}
        {activeTab === "graph" && (
          <div className="max-w-6xl mx-auto space-y-4">
            <div className="flex justify-between items-center bg-slate-900/60 border border-slate-800 rounded-xl px-6 py-4">
              <div>
                <h2 className="text-sm font-bold text-white">Topological Dependency Network</h2>
                <p className="text-xs text-slate-400">Dynamic graph of live agent and resource relationships</p>
              </div>
              <div className="flex gap-4 text-xs">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-indigo-500"></span> Active Agent</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Healthy Infra</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Offline Node</span>
              </div>
            </div>
            <DependencyGraph
              agents={data.agents}
              resources={data.resources}
              dependencies={data.dependencies}
            />
          </div>
        )}

        {/* TAB 3: BLAST RADIUS */}
        {activeTab === "blast" && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 shadow-lg">
              <h2 className="text-sm font-bold text-white mb-1">Recursive Blast-Radius Engine</h2>
              <p className="text-xs text-slate-400 mb-4">Calculates downstream impact using a recursive SQL common table expression.</p>
              <select
                value={selectedResource}
                onChange={(e) => runBlastRadius(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200">
                <option value="">-- Choose Failing Resource Node --</option>
                {data.resources.map(r => (
                  <option key={r.resource_id} value={r.resource_id}>{r.name} ({r.resource_type})</option>
                ))}
              </select>
            </div>

            {impactData.length > 0 ? (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
                <div className="px-5 py-3 border-b border-slate-800 bg-rose-950/20 text-rose-400 font-semibold text-xs">
                  Detected Failure Cascade ({impactData.length} Nodes Compromised)
                </div>
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/50 text-slate-500 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Depth</th>
                      <th className="py-2.5 px-4">Compromised Agent</th>
                      <th className="py-2.5 px-4">Impacted Pipeline</th>
                      <th className="py-2.5 px-4">Pipeline Criticality</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {impactData.map((row, i) => (
                      <tr key={i} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-4">
                          <span className="bg-rose-500/10 border border-rose-500/20 text-rose-400 font-mono px-2 py-0.5 rounded text-[10px]">
                            {row.depth} Hop{row.depth > 1 ? 's' : ''}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 font-bold text-white">{row.agent_name}</td>
                        <td className="py-2.5 px-4 text-slate-400">{row.workflow_name || "Standalone Worker"}</td>
                        <td className="py-2.5 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 border border-amber-500/20 text-amber-300">
                            {row.criticality_level || "MEDIUM"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : selectedResource ? (
              <div className="p-8 text-center bg-slate-900/30 border border-slate-800/50 rounded-xl text-slate-500 text-xs">
                No active dependencies cascade from this node.
              </div>
            ) : null}
          </div>
        )}


        {/* TAB 5: AUDIT LOGS */}
        {activeTab === "audit" && (
          <div className="max-w-5xl mx-auto bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <div className="px-5 py-3.5 border-b border-slate-800 flex justify-between items-center">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-white">Database Trigger Execution Ledger</h2>
                <p className="text-[11px] text-slate-400">Captures changes through MySQL triggers and stored procedures</p>
              </div>
              <button onClick={fetchAudit} className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition">
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/50 text-slate-500 font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Log ID</th>
                    <th className="py-2.5 px-4">Table</th>
                    <th className="py-2.5 px-4">Operation</th>
                    <th className="py-2.5 px-4">Record ID</th>
                    <th className="py-2.5 px-4">Actor</th>
                    <th className="py-2.5 px-4">Details</th>
                    <th className="py-2.5 px-4 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {auditLogs.map((log) => (
                    <tr key={log.log_id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-4 text-slate-500">#{log.log_id}</td>
                      <td className="py-2.5 px-4 text-indigo-400 font-bold">{log.table_name}</td>
                      <td className="py-2.5 px-4">
                        <span className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded text-[10px]">
                          {log.operation}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-400">{log.record_id}</td>
                      <td className="py-2.5 px-4 text-slate-300">{log.changed_by}</td>
                      <td className="py-2.5 px-4 text-slate-400 font-sans">{log.change_details}</td>
                      <td className="py-2.5 px-4 text-slate-500 text-right">{new Date(log.created_at).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "users" && hasPermission("users.manage") && (
          <div className="max-w-5xl mx-auto space-y-5">
            <section className="bg-slate-900/60 border border-slate-800 rounded-lg p-5">
              <h2 className="text-sm font-bold text-white mb-4">Create Application User</h2>
              <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <input
                  placeholder="Username"
                  autoComplete="off"
                  value={newUser.username}
                  onChange={event => setNewUser({ ...newUser, username: event.target.value })}
                  className="bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-100"
                  required
                />
                <input
                  type="password"
                  placeholder="Password (12+ chars)"
                  autoComplete="new-password"
                  value={newUser.password}
                  onChange={event => setNewUser({ ...newUser, password: event.target.value })}
                  className="bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-100"
                  minLength={12}
                  required
                />
                <select
                  value={newUser.role}
                  onChange={event => setNewUser({ ...newUser, role: event.target.value })}
                  className="bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-100"
                >
                  <option>Viewer</option>
                  <option>Operator</option>
                  <option>Admin</option>
                </select>
                <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 rounded px-3 py-2 text-xs font-semibold">Create user</button>
              </form>
            </section>

            <section className="bg-slate-900/60 border border-slate-800 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                <h2 className="text-sm font-bold text-white">Application Accounts</h2>
                <button onClick={() => loadUsers().catch(error => notify(error.message, "error"))} className="p-2 hover:bg-slate-800 rounded" title="Refresh accounts">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left text-slate-300">
                  <thead className="bg-slate-950/60 text-slate-400">
                    <tr>
                      <th className="p-3">Username</th>
                      <th className="p-3">Role</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Last login</th>
                      <th className="p-3">Update access</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {adminUsers.map(user => {
                      const currentRole = user.roles?.split(",")[0] || "Viewer";
                      return (
                        <tr key={user.user_id}>
                          <td className="p-3 font-medium text-white">{user.username}</td>
                          <td className="p-3">{user.roles || "Unassigned"}</td>
                          <td className="p-3">{user.is_active ? "Active" : "Disabled"}</td>
                          <td className="p-3">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</td>
                          <td className="p-3">
                            <div className="flex gap-2">
                              <select
                                aria-label={`Role for ${user.username}`}
                                value={currentRole}
                                onChange={event => handleUpdateUser(user, event.target.value, user.is_active)}
                                className="bg-slate-950 border border-slate-700 rounded p-1.5"
                              >
                                <option>Viewer</option>
                                <option>Operator</option>
                                <option>Admin</option>
                              </select>
                              <button
                                disabled={user.user_id === authUser.user_id}
                                onClick={() => handleUpdateUser(user, currentRole, !user.is_active)}
                                className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded disabled:opacity-40"
                              >
                                {user.is_active ? "Disable" : "Enable"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}