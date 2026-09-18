import React, { useState, useEffect, useCallback } from 'react';
import { Auth } from './components/Auth';
import { AIConsultantChat } from './components/AIConsultantChat';
import { TransformationDashboard } from './components/TransformationDashboard';
import { api, getAuthToken, removeAuthToken } from './api/client';
import { PublicChatbotManager } from './components/PublicChatbotManager';

export function App() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeProject, setActiveProject] = useState(null);
    const [blueprintData, setBlueprintData] = useState(null);
    const [mainView, setMainView] = useState('chat');
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [workspaces, setWorkspaces] = useState([]);
    const [projects, setProjects] = useState([]);
    const [activeWorkspaceId, setActiveWorkspaceId] = useState('');
    const [showExport, setShowExport] = useState(false);
    const [newProjName, setNewProjName] = useState('');
    const [showNewProj, setShowNewProj] = useState(false);

    useEffect(() => {
        checkAuth();
    }, []);

    useEffect(() => {
        if (user) loadWorkspaces();
    }, [user]);

    useEffect(() => {
        if (activeWorkspaceId) loadProjects(activeWorkspaceId);
    }, [activeWorkspaceId]);

    // Clear ALL private state when project changes to prevent cross-project data leakage
    useEffect(() => {
        setBlueprintData(null);
        if (activeProject?.id) {
            loadBlueprint(activeProject.id);
        }
    }, [activeProject?.id]);

    const checkAuth = async () => {
        const token = getAuthToken();
        if (!token) {
            setLoading(false);
            return;
        }
        try {
            const u = await api.getMe();
            setUser(u);
        } catch {
            // Token invalid or expired — clear it and show login
            removeAuthToken();
        } finally {
            setLoading(false);
        }
    };

    const loadBlueprint = async (projectId) => {
        try {
            const res = await api.getBlueprint(projectId);
            setBlueprintData(res.blueprint);
        } catch {
            setBlueprintData(null);
        }
    };

    const loadWorkspaces = async () => {
        try {
            const data = await api.listWorkspaces();
            setWorkspaces(data);
            if (data.length > 0) setActiveWorkspaceId(data[0].id);
        } catch (e) { console.error(e); }
    };

    const loadProjects = async (wsId) => {
        try {
            const data = await api.listProjects(wsId);
            setProjects(data);
            if (data.length > 0 && !activeProject) {
                setActiveProject(data[0]);
            }
        } catch (e) { console.error(e); }
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!newProjName.trim() || !activeWorkspaceId) return;
        try {
            const proj = await api.createProject(newProjName.trim(), activeWorkspaceId, '');
            setProjects((p) => [...p, proj]);
            setActiveProject(proj);
            setNewProjName('');
            setShowNewProj(false);
        } catch (err) { alert(err.message); }
    };

    const handleExportBlueprint = async (format) => {
        if (!activeProject) return;
        const ext = { markdown: 'md', json: 'json', html: 'html' }[format] || format;
        const filename = `${activeProject.name.toLowerCase().replace(/\s+/g, '_')}_blueprint.${ext}`;
        try { await api.exportProject(activeProject.id, format, filename); } catch (e) { console.error(e); }
        setShowExport(false);
    };

    // Full private-state wipe on logout
    const handleLogout = useCallback(() => {
        removeAuthToken();
        setUser(null);
        setActiveProject(null);
        setBlueprintData(null);
        setMainView('chat');
        setWorkspaces([]);
        setProjects([]);
    }, []);

    if (loading) {
        return (
            <div className="loading-screen">
                <span>⬡</span> Loading Business Transformation AI...
            </div>
        );
    }

    if (!user) {
        return <Auth onAuthSuccess={(u) => setUser(u)} />;
    }

    return (
        <div className="app-shell">
            {/* Sidebar toggle for mobile */}
            <button className="sidebar-toggle" onClick={() => setSidebarOpen((o) => !o)} aria-label="Toggle sidebar">
                {sidebarOpen ? '\u2715' : '\u2630'}
            </button>

            {/* LEFT SIDEBAR */}
            <nav className={`sidebar${sidebarOpen ? '' : ' collapsed'}`}>
                <div className="sidebar-logo">
                    <div className="sidebar-logo-icon">⬡</div>
                    <span className="sidebar-logo-text">Business Transformation AI</span>
                </div>

                <div className="sidebar-body">
                    {/* New consultation */}
                    <button className="sidebar-new-btn" onClick={() => { setMainView('chat'); setActiveProject(null); }}>
                        <span>+</span> New Consultation
                    </button>

                    {/* View navigation */}
                    <button className={`sidebar-item${mainView === 'chat' ? ' active' : ''}`} onClick={() => setMainView('chat')}>
                        <span className="sidebar-item-icon">💬</span> AI Consultant
                    </button>
                    <button className={`sidebar-item${mainView === 'dashboard' ? ' active' : ''}`} onClick={() => setMainView('dashboard')}>
                        <span className="sidebar-item-icon">📊</span> Blueprint Dashboard
                    </button>
                    <button className={`sidebar-item${mainView === 'chatbots' ? ' active' : ''}`} onClick={() => setMainView('chatbots')}>
                        <span className="sidebar-item-icon">🤖</span> Public Chatbots
                    </button>

                    <div className="sidebar-divider" />

                    {/* Projects */}
                    <span className="sidebar-section-label">Projects</span>
                    {projects.map((p) => (
                        <button
                            key={p.id}
                            className={`sidebar-item${activeProject?.id === p.id ? ' active' : ''}`}
                            onClick={() => { setActiveProject(p); setMainView('chat'); }}
                        >
                            <span className="sidebar-item-icon">📁</span>
                            {p.name}
                        </button>
                    ))}
                    {showNewProj ? (
                        <form onSubmit={handleCreateProject} style={{ padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <input
                                className="panel-input"
                                placeholder="Project name..."
                                value={newProjName}
                                onChange={(e) => setNewProjName(e.target.value)}
                                autoFocus
                            />
                            <div style={{ display: 'flex', gap: '4px' }}>
                                <button type="submit" className="btn btn-primary" style={{ flex: 1, justifyContent: 'center', fontSize: '0.75rem', padding: '5px 8px' }}>Create</button>
                                <button type="button" className="btn" style={{ fontSize: '0.75rem', padding: '5px 8px' }} onClick={() => setShowNewProj(false)}>Cancel</button>
                            </div>
                        </form>
                    ) : (
                        <button className="sidebar-item" onClick={() => setShowNewProj(true)}>
                            <span className="sidebar-item-icon">+</span> New Project
                        </button>
                    )}

                    {/* Stage tracker when project active */}
                    {activeProject && (
                        <>
                            <div className="sidebar-divider" />
                            <div className="tracker-section">
                                <div className="tracker-header">
                                    <span className="tracker-title">Transformation</span>
                                    <span className="tracker-pct">
                                        {Math.round((['business_analysis','ai_opportunities','solution_blueprint','architecture','data_api_design','ux_design','roadmap'].filter((s) => blueprintData?.[s]).length / 7) * 100)}%
                                    </span>
                                </div>
                                <div className="tracker-bar-track">
                                    <div className="tracker-bar-fill" style={{ width: `${Math.round((['business_analysis','ai_opportunities','solution_blueprint','architecture','data_api_design','ux_design','roadmap'].filter((s) => blueprintData?.[s]).length / 7) * 100)}%` }} />
                                </div>
                                <div className="tracker-metrics">
                                    <div className="tracker-metric">
                                        <span className="tracker-metric-label">Feasibility</span>
                                        <span className="tracker-metric-value">
                                            {blueprintData ? `${Math.round(65 + ['business_analysis','ai_opportunities','solution_blueprint','architecture','data_api_design','ux_design','roadmap'].filter((s) => blueprintData[s]).length * 4)}/100` : '—'}
                                        </span>
                                    </div>
                                    <div className="tracker-metric">
                                        <span className="tracker-metric-label">Est. Build</span>
                                        <span className="tracker-metric-value">
                                            {blueprintData?.roadmap?.effort_estimates?.total_duration || (blueprintData ? '4–6 wks' : '—')}
                                        </span>
                                    </div>
                                </div>
                                <div className="stage-list">
                                    {[
                                        { key: 'business_analysis', label: 'Business Analysis' },
                                        { key: 'ai_opportunities', label: 'AI Opportunities' },
                                        { key: 'solution_blueprint', label: 'Solution Blueprint' },
                                        { key: 'architecture', label: 'System Architecture' },
                                        { key: 'data_api_design', label: 'Database & API' },
                                        { key: 'ux_design', label: 'UX Recommendations' },
                                        { key: 'roadmap', label: 'Implementation' },
                                    ].map((st) => {
                                        const done = !!(blueprintData?.[st.key]);
                                        const status = blueprintData?.stage_statuses?.[st.key];
                                        return (
                                            <div key={st.key} className={`stage-item${done ? ' stage-item--done' : ''}${status === 'STALE' ? ' stage-item--stale' : ''}${status === 'RUNNING' ? ' stage-item--running' : ''}`}>
                                                <span className="stage-icon">{status === 'RUNNING' ? '⏳' : status === 'STALE' ? '⚠' : done ? '✓' : '○'}</span>
                                                <span>{st.label}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="sidebar-footer">
                    {activeProject && (
                        <div style={{ position: 'relative' }}>
                            <button className="sidebar-footer-item" style={{ width: '100%' }} onClick={() => setShowExport((s) => !s)}>
                                <span>📥</span> Export Blueprint
                            </button>
                            {showExport && (
                                <div style={{ position: 'absolute', bottom: '100%', left: 0, right: 0, background: '#1f1f1f', border: '1px solid #3f3f3f', borderRadius: '8px', padding: '6px', marginBottom: '4px', zIndex: 50 }}>
                                    {['markdown', 'json', 'html'].map((f) => (
                                        <button key={f} onClick={() => handleExportBlueprint(f)} style={{ display: 'block', width: '100%', padding: '7px 10px', background: 'transparent', border: 'none', color: '#ececec', fontSize: '0.8125rem', textAlign: 'left', borderRadius: '5px', cursor: 'pointer' }}
                                            onMouseOver={(e) => e.currentTarget.style.background = '#2a2a2a'}
                                            onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                                        >
                                            {f === 'markdown' ? '📝 .md' : f === 'json' ? '📦 .json' : '🌐 .html'}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                    <button className="sidebar-footer-item" onClick={handleLogout}>
                        <span>👤</span> {user?.full_name || user?.email}
                    </button>
                    <button className="sidebar-footer-item" onClick={handleLogout}>
                        <span>→</span> Sign Out
                    </button>
                </div>
            </nav>

            {/* MAIN AREA */}
            <div className="main-area">
                {mainView === 'chat' && (
                    <AIConsultantChat
                        activeProject={activeProject}
                        onSelectProject={(proj) => {
                            setActiveProject(proj);
                            if (proj && !projects.find((p) => p.id === proj.id)) {
                                setProjects((prev) => [...prev, proj]);
                            }
                        }}
                        blueprintData={blueprintData}
                        onBlueprintUpdated={(updated) => setBlueprintData(updated)}
                        onViewDashboard={() => setMainView('dashboard')}
                    />
                )}
                {mainView === 'dashboard' && (
                    <div className="view-wrap">
                        <TransformationDashboard
                            activeProject={activeProject}
                            blueprintData={blueprintData}
                            onBlueprintUpdated={(updated) => setBlueprintData(updated)}
                        />
                    </div>
                )}
                {mainView === 'chatbots' && (
                    <div className="view-wrap">
                        <PublicChatbotManager />
                    </div>
                )}
            </div>
        </div>
    );
}

export default App;
