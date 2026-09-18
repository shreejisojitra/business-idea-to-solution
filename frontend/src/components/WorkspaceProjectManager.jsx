import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export const WorkspaceProjectManager = ({ onSelectProject }) => {
    const [workspaces, setWorkspaces] = useState([]);
    const [activeWorkspaceId, setActiveWorkspaceId] = useState('');
    const [projects, setProjects] = useState([]);
    const [activeProjectId, setActiveProjectId] = useState('');

    const [newWorkspaceName, setNewWorkspaceName] = useState('');
    const [newProjectName, setNewProjectName] = useState('');
    const [showWsModal, setShowWsModal] = useState(false);
    const [showProjModal, setShowProjModal] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadWorkspaces();
    }, []);

    useEffect(() => {
        if (activeWorkspaceId) {
            loadProjects(activeWorkspaceId);
        }
    }, [activeWorkspaceId]);

    const loadWorkspaces = async () => {
        try {
            const data = await api.listWorkspaces();
            setWorkspaces(data);
            if (data.length > 0 && !activeWorkspaceId) {
                setActiveWorkspaceId(data[0].id);
            }
        } catch (err) {
            console.error('Failed to load workspaces:', err);
        }
    };

    const loadProjects = async (wsId) => {
        try {
            const data = await api.listProjects(wsId);
            setProjects(data);
            if (data.length > 0) {
                setActiveProjectId(data[0].id);
                onSelectProject(data[0]);
            } else {
                setActiveProjectId('');
                onSelectProject(null);
            }
        } catch (err) {
            console.error('Failed to load projects:', err);
        }
    };

    const handleCreateWorkspace = async (e) => {
        e.preventDefault();
        if (!newWorkspaceName.trim()) return;
        setLoading(true);
        try {
            const ws = await api.createWorkspace(newWorkspaceName);
            setWorkspaces([...workspaces, ws]);
            setActiveWorkspaceId(ws.id);
            setNewWorkspaceName('');
            setShowWsModal(false);
        } catch (err) {
            alert(err.message || 'Failed to create workspace');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!newProjectName.trim() || !activeWorkspaceId) return;
        setLoading(true);
        try {
            const proj = await api.createProject(newProjectName, activeWorkspaceId, '');
            setProjects([...projects, proj]);
            setActiveProjectId(proj.id);
            onSelectProject(proj);
            setNewProjectName('');
            setShowProjModal(false);
        } catch (err) {
            alert(err.message || 'Failed to create project');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="glass-card" style={{ padding: '20px 24px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'center', justifyContent: 'space-between' }}>
                {/* Workspace Selector */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '600' }}>Workspace:</label>
                    <select
                        className="form-input"
                        style={{ width: 'auto', minWidth: '180px' }}
                        value={activeWorkspaceId}
                        onChange={(e) => setActiveWorkspaceId(e.target.value)}
                    >
                        {workspaces.map((w) => (
                            <option key={w.id} value={w.id}>
                                {w.name}
                            </option>
                        ))}
                    </select>
                    <button className="btn-secondary" style={{ padding: '8px 12px', fontSize: '0.8rem' }} onClick={() => setShowWsModal(!showWsModal)}>
                        + New
                    </button>
                </div>

                {/* Project Selector */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '600' }}>Project:</label>
                    <select
                        className="form-input"
                        style={{ width: 'auto', minWidth: '220px' }}
                        value={activeProjectId}
                        onChange={(e) => {
                            const selected = projects.find((p) => p.id === e.target.value);
                            setActiveProjectId(e.target.value);
                            onSelectProject(selected);
                        }}
                    >
                        {projects.length === 0 ? (
                            <option value="">No projects yet</option>
                        ) : (
                            projects.map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.name} ({p.status})
                                </option>
                            ))
                        )}
                    </select>
                    <button className="btn-secondary" style={{ padding: '8px 12px', fontSize: '0.8rem' }} onClick={() => setShowProjModal(!showProjModal)}>
                        + New Project
                    </button>
                </div>
            </div>

            {/* New Workspace Modal Form */}
            {showWsModal && (
                <form onSubmit={handleCreateWorkspace} style={{ marginTop: '16px', display: 'flex', gap: '12px', background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px' }}>
                    <input
                        type="text"
                        className="form-input"
                        placeholder="Workspace Name (e.g. Healthcare Team)"
                        value={newWorkspaceName}
                        onChange={(e) => setNewWorkspaceName(e.target.value)}
                        required
                    />
                    <button type="submit" className="btn-primary" disabled={loading}>
                        Create
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setShowWsModal(false)}>
                        Cancel
                    </button>
                </form>
            )}

            {/* New Project Modal Form */}
            {showProjModal && (
                <form onSubmit={handleCreateProject} style={{ marginTop: '16px', display: 'flex', gap: '12px', background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px' }}>
                    <input
                        type="text"
                        className="form-input"
                        placeholder="Project Name (e.g. Appointment Booking Engine)"
                        value={newProjectName}
                        onChange={(e) => setNewProjectName(e.target.value)}
                        required
                    />
                    <button type="submit" className="btn-primary" disabled={loading}>
                        Create Project
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setShowProjModal(false)}>
                        Cancel
                    </button>
                </form>
            )}
        </div>
    );
};
