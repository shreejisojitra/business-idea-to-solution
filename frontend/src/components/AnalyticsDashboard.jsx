import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const PERIODS = [
    { value: 'today', label: 'Today' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
];

const StatCard = ({ label, value, sub, color = '#6366f1' }) => (
    <div style={{
        background: '#fff',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '20px 24px',
        boxShadow: '0 2px 8px rgba(15,23,42,0.05)',
        minWidth: '140px',
    }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {label}
        </div>
        <div style={{ fontSize: '2rem', fontWeight: 800, color, lineHeight: 1 }}>{value ?? '—'}</div>
        {sub && <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>{sub}</div>}
    </div>
);

const MiniBar = ({ data }) => {
    if (!data || data.length === 0) {
        return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No activity in this period.</p>;
    }
    const max = Math.max(...data.map(d => d.requests), 1);
    return (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '60px' }}>
            {data.map((d, i) => (
                <div key={i} title={`${d.date}: ${d.requests} requests`} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
                    <div style={{
                        width: '100%',
                        height: `${Math.max(4, (d.requests / max) * 52)}px`,
                        background: d.failed > 0
                            ? 'linear-gradient(180deg, #f87171, #ef4444)'
                            : 'linear-gradient(180deg, #10b981, #059669)',
                        borderRadius: '3px 3px 0 0',
                        transition: 'height 0.3s ease',
                    }} />
                </div>
            ))}
        </div>
    );
};

export const AnalyticsDashboard = ({ activeProject, activeChatbot }) => {
    const [period, setPeriod] = useState('30d');
    const [projectData, setProjectData] = useState(null);
    const [chatbotData, setChatbotData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        if (!activeProject?.id && !activeChatbot?.id) return;
        setLoading(true);
        setError('');
        try {
            const [pd, cd] = await Promise.all([
                activeProject?.id ? api.getProjectAnalytics(activeProject.id, period) : Promise.resolve(null),
                activeChatbot?.id ? api.getChatbotAnalytics(activeChatbot.id, period) : Promise.resolve(null),
            ]);
            setProjectData(pd);
            setChatbotData(cd);
        } catch (e) {
            setError(e.message || 'Failed to load analytics.');
        } finally {
            setLoading(false);
        }
    }, [activeProject?.id, activeChatbot?.id, period]);

    useEffect(() => { load(); }, [load]);

    if (!activeProject?.id && !activeChatbot?.id) {
        return (
            <div className="glass-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                Select a project or chatbot to view analytics.
            </div>
        );
    }

    return (
        <div className="glass-card" style={{ padding: '28px' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                    <h3 className="gradient-text" style={{ fontSize: '1.3rem' }}>📊 Analytics</h3>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                        {activeProject?.name && `Project: ${activeProject.name}`}
                        {activeChatbot?.name && ` · Chatbot: ${activeChatbot.name}`}
                    </span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                    {PERIODS.map(p => (
                        <button
                            key={p.value}
                            onClick={() => setPeriod(p.value)}
                            className={period === p.value ? 'btn-emerald' : 'btn-secondary'}
                            style={{ padding: '6px 14px', fontSize: '0.82rem' }}
                        >
                            {p.label}
                        </button>
                    ))}
                    <button onClick={load} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.82rem' }}>
                        🔄
                    </button>
                </div>
            </div>

            {loading && <p style={{ color: 'var(--text-muted)' }}>Loading analytics...</p>}
            {error && <p style={{ color: '#ef4444', fontSize: '0.85rem' }}>{error}</p>}

            {/* Project Analytics */}
            {projectData && (
                <section style={{ marginBottom: '32px' }}>
                    <h4 style={{ color: '#6366f1', marginBottom: '16px', fontSize: '1rem', fontWeight: 700 }}>
                        Project Activity
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
                        <StatCard label="AI Requests" value={projectData.ai_requests} color="#6366f1" />
                        <StatCard label="Successful" value={projectData.ai_success} color="#10b981" />
                        <StatCard label="Failed" value={projectData.ai_failed} color="#ef4444" />
                        <StatCard label="Chat Messages" value={projectData.messages_in_period} sub="in period" color="#f59e0b" />
                        <StatCard label="Conversations" value={projectData.total_conversations} color="#8b5cf6" />
                        <StatCard
                            label="Avg Latency"
                            value={projectData.avg_latency_ms != null ? `${projectData.avg_latency_ms}ms` : '—'}
                            color="#0ea5e9"
                        />
                        <StatCard label="Knowledge Sources" value={projectData.knowledge_sources} color="#64748b" />
                    </div>

                    {projectData.daily_breakdown?.length > 0 && (
                        <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '16px' }}>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '10px', textTransform: 'uppercase' }}>
                                Daily AI Requests
                            </div>
                            <MiniBar data={projectData.daily_breakdown} />
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    {projectData.daily_breakdown[0]?.date}
                                </span>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    {projectData.daily_breakdown[projectData.daily_breakdown.length - 1]?.date}
                                </span>
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Chatbot Analytics */}
            {chatbotData && (
                <section>
                    <h4 style={{ color: '#10b981', marginBottom: '16px', fontSize: '1rem', fontWeight: 700 }}>
                        Chatbot Activity — {chatbotData.chatbot_name}
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
                        <StatCard label="AI Requests" value={chatbotData.ai_requests} color="#6366f1" />
                        <StatCard label="Successful" value={chatbotData.ai_success} color="#10b981" />
                        <StatCard label="Failed" value={chatbotData.ai_failed} color="#ef4444" />
                        <StatCard label="Total Sessions" value={chatbotData.total_sessions} color="#8b5cf6" />
                        <StatCard label="Sessions (period)" value={chatbotData.sessions_in_period} color="#f59e0b" />
                        <StatCard label="Total Messages" value={chatbotData.total_messages} color="#0ea5e9" />
                        <StatCard
                            label="Avg Latency"
                            value={chatbotData.avg_latency_ms != null ? `${chatbotData.avg_latency_ms}ms` : '—'}
                            color="#64748b"
                        />
                    </div>

                    {chatbotData.daily_breakdown?.length > 0 && (
                        <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '16px' }}>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '10px', textTransform: 'uppercase' }}>
                                Daily AI Requests
                            </div>
                            <MiniBar data={chatbotData.daily_breakdown} />
                        </div>
                    )}
                </section>
            )}
        </div>
    );
};
