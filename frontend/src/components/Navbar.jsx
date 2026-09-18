import React, { useState } from 'react';
import { removeAuthToken, api } from '../api/client';

export const Navbar = ({ user, activeWorkspace, activeProject, onLogout }) => {
    const [showExport, setShowExport] = useState(false);

    const handleLogout = () => {
        removeAuthToken();
        if (onLogout) onLogout();
    };

    const handleDownloadExport = async (format) => {
        if (!activeProject) return;
        const ext = { markdown: 'md', json: 'json', html: 'html', pdf: 'pdf' }[format] || format;
        const filename = `${activeProject.name.toLowerCase().replace(/\s+/g, '_')}_blueprint.${ext}`;
        try {
            await api.exportProject(activeProject.id, format, filename);
        } catch (err) {
            console.error('Export failed:', err.message);
        }
        setShowExport(false);
    };

    return (
        <header className="glass-card" style={{ borderRadius: '0 0 16px 16px', borderTop: 'none', padding: '16px 32px', marginBottom: '24px', background: '#ffffff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <h2 className="gradient-text" style={{ fontSize: '1.45rem', letterSpacing: '-0.5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>❇️</span> Business Transformation AI
                    </h2>
                    {activeWorkspace && (
                        <span style={{ background: 'var(--emerald-light)', color: 'var(--emerald-text)', padding: '4px 12px', borderRadius: '20px', fontSize: '0.8rem', border: '1px solid rgba(16, 185, 129, 0.3)', fontWeight: '600' }}>
                            Workspace: {activeWorkspace.name}
                        </span>
                    )}
                    {activeProject && (
                        <span style={{ background: 'var(--purple-light)', color: 'var(--purple-text)', padding: '4px 12px', borderRadius: '20px', fontSize: '0.8rem', border: '1px solid rgba(99, 102, 241, 0.3)', fontWeight: '600' }}>
                            Project: {activeProject.name}
                        </span>
                    )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    {activeProject && (
                        <div style={{ position: 'relative' }}>
                            <button
                                className="btn-emerald"
                                onClick={() => setShowExport(!showExport)}
                                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                            >
                                📥 Export Blueprint ▾
                            </button>

                            {showExport && (
                                <div style={{
                                    position: 'absolute',
                                    right: 0,
                                    top: '42px',
                                    background: '#ffffff',
                                    border: '1px solid var(--border-color)',
                                    borderRadius: '12px',
                                    padding: '8px',
                                    boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '4px',
                                    zIndex: 100,
                                    minWidth: '170px'
                                }}>
                                    <button
                                        onClick={() => handleDownloadExport('markdown')}
                                        style={{ textAlign: 'left', background: 'transparent', border: 'none', color: 'var(--text-main)', padding: '8px 12px', fontSize: '0.82rem', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
                                        onMouseOver={(e) => e.target.style.background = 'var(--emerald-light)'}
                                        onMouseOut={(e) => e.target.style.background = 'transparent'}
                                    >
                                        📝 Markdown (.md)
                                    </button>
                                    <button
                                        onClick={() => handleDownloadExport('json')}
                                        style={{ textAlign: 'left', background: 'transparent', border: 'none', color: 'var(--text-main)', padding: '8px 12px', fontSize: '0.82rem', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
                                        onMouseOver={(e) => e.target.style.background = 'var(--emerald-light)'}
                                        onMouseOut={(e) => e.target.style.background = 'transparent'}
                                    >
                                        📦 Raw JSON (.json)
                                    </button>
                                    <button
                                        onClick={() => handleDownloadExport('html')}
                                        style={{ textAlign: 'left', background: 'transparent', border: 'none', color: 'var(--text-main)', padding: '8px 12px', fontSize: '0.82rem', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
                                        onMouseOver={(e) => e.target.style.background = 'var(--emerald-light)'}
                                        onMouseOut={(e) => e.target.style.background = 'transparent'}
                                    >
                                        🌐 HTML Report (.html)
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {user && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontSize: '0.88rem', color: 'var(--text-muted)', fontWeight: '500' }}>
                                👤 {user.full_name || user.email}
                            </span>
                            <button onClick={handleLogout} className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.82rem' }}>
                                Sign Out
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
};
