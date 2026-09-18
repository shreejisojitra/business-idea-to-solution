import React, { useState } from 'react';
import { api } from '../api/client';
import { AIConsultantChat } from './AIConsultantChat';

export const TransformationDashboard = ({ activeProject, blueprintData, onBlueprintUpdated }) => {
    const [activeTab, setActiveTab] = useState('business_analysis');
    const [editing, setEditing] = useState(false);
    const [editJson, setEditJson] = useState('');
    const [saving, setSaving] = useState(false);
    const [regenerating, setRegenerating] = useState(false);
    const [exporting, setExporting] = useState('');

    const handleExport = async (format) => {
        if (!activeProject?.id || exporting) return;
        setExporting(format);
        const ext = { markdown: 'md', json: 'json', html: 'html', pdf: 'pdf' }[format];
        const filename = `${(activeProject.name || 'blueprint').toLowerCase().replace(/\s+/g, '_')}_blueprint.${ext}`;
        try {
            await api.exportProject(activeProject.id, format, filename);
        } catch (err) {
            alert('Export failed: ' + err.message);
        } finally {
            setExporting('');
        }
    };

    if (!blueprintData) return null;

    const tabs = [
        { id: 'business_analysis', label: '1. Business Analysis' },
        { id: 'ai_opportunities', label: '2. AI Opportunities' },
        { id: 'solution_blueprint', label: '3. Solution Blueprint' },
        { id: 'architecture', label: '4. Architecture' },
        { id: 'data_api_design', label: '5. Data & APIs' },
        { id: 'ux_design', label: '6. UX Recommendations' },
        { id: 'roadmap', label: '7. Implementation Roadmap' },
        { id: 'chat', label: '🤖 AI Consultant' },
    ];

    const currentStageContent = blueprintData[activeTab] || {};

    const handleStartEdit = () => {
        setEditJson(JSON.stringify(currentStageContent, null, 2));
        setEditing(true);
    };

    const handleSaveEdit = async () => {
        try {
            const parsed = JSON.parse(editJson);
            setSaving(true);
            await api.updateBlueprintStage(activeProject.id, activeTab, parsed);
            const updated = { ...blueprintData, [activeTab]: parsed };
            onBlueprintUpdated(updated);
            setEditing(false);
        } catch (err) {
            alert('Invalid JSON formatting: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleRegenerateStage = async () => {
        if (!window.confirm(`Regenerate stage "${activeTab}" using AI?`)) return;
        setRegenerating(true);
        try {
            const res = await api.regenerateStage(activeProject.id, activeTab);
            const updated = { ...blueprintData, [activeTab]: res.data };
            onBlueprintUpdated(updated);
        } catch (err) {
            alert('Regeneration failed: ' + err.message);
        } finally {
            setRegenerating(false);
        }
    };

    return (
        <div className="glass-card" style={{ padding: '28px' }}>
            {/* Header & Export Controls */}
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', gap: '16px' }}>
                <div>
                    <h3 className="gradient-text" style={{ fontSize: '1.4rem' }}>
                        Transformation Dashboard
                    </h3>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        Real AI-Generated Blueprint — Review, Edit, or Export
                    </span>
                </div>

                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button
                        onClick={() => handleExport('markdown')}
                        disabled={!!exporting}
                        className="btn-secondary"
                        style={{ fontSize: '0.85rem', padding: '8px 14px' }}
                    >
                        {exporting === 'markdown' ? '⏳...' : '📥 Export .md'}
                    </button>
                    <button
                        onClick={() => handleExport('json')}
                        disabled={!!exporting}
                        className="btn-secondary"
                        style={{ fontSize: '0.85rem', padding: '8px 14px' }}
                    >
                        {exporting === 'json' ? '⏳...' : '📥 Export JSON'}
                    </button>
                    <button
                        onClick={() => handleExport('html')}
                        disabled={!!exporting}
                        className="btn-secondary"
                        style={{ fontSize: '0.85rem', padding: '8px 14px' }}
                    >
                        {exporting === 'html' ? '⏳...' : '🌐 Export HTML'}
                    </button>
                    <button
                        onClick={() => handleExport('pdf')}
                        disabled={!!exporting}
                        className="btn-primary"
                        style={{ fontSize: '0.85rem', padding: '8px 14px' }}
                    >
                        {exporting === 'pdf' ? '⏳ Generating PDF...' : '📄 Export PDF'}
                    </button>
                </div>
            </div>

            {/* Tabs Header */}
            <div className="tabs-header" style={{ marginBottom: '24px' }}>
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                        onClick={() => { setActiveTab(tab.id); setEditing(false); }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Action Controls for Stage */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginBottom: '16px' }}>
                {editing ? (
                    <>
                        <button className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={handleSaveEdit} disabled={saving}>
                            {saving ? 'Saving...' : '💾 Save Changes'}
                        </button>
                        <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => setEditing(false)}>
                            Cancel
                        </button>
                    </>
                ) : (
                    <>
                        <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={handleStartEdit}>
                            ✏️ Edit Stage Data
                        </button>
                        <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={handleRegenerateStage} disabled={regenerating}>
                            {regenerating ? 'Regenerating...' : '🔄 Regenerate Stage'}
                        </button>
                    </>
                )}
            </div>

            {/* Content Area */}
            {editing ? (
                <div>
                    <textarea
                        className="form-input"
                        rows={16}
                        style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}
                        value={editJson}
                        onChange={(e) => setEditJson(e.target.value)}
                    />
                </div>
            ) : (
                <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '24px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                    {renderTabContent(activeTab, currentStageContent)}
                </div>
            )}
        </div>
    );
};

function renderTabContent(tabId, data) {
    if (!data || Object.keys(data).length === 0) {
        return <p style={{ color: 'var(--text-muted)' }}>No data available for this stage.</p>;
    }

    switch (tabId) {
        case 'business_analysis':
            return (
                <div>
                    <h4 style={{ color: '#a5b4fc', marginBottom: '8px' }}>Core Business Problem:</h4>
                    <p style={{ marginBottom: '16px' }}>{data.problem}</p>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                        <div>
                            <h5 style={{ color: '#f472b6', marginBottom: '6px' }}>Pain Points</h5>
                            <ul>{data.pain_points?.map((p, i) => <li key={i}>{p}</li>)}</ul>
                        </div>
                        <div>
                            <h5 style={{ color: '#38bdf8', marginBottom: '6px' }}>Goals</h5>
                            <ul>{data.goals?.map((g, i) => <li key={i}>{g}</li>)}</ul>
                        </div>
                        <div>
                            <h5 style={{ color: '#4ade80', marginBottom: '6px' }}>Stakeholders</h5>
                            <ul>{data.stakeholders?.map((s, i) => <li key={i}>{s}</li>)}</ul>
                        </div>
                        <div>
                            <h5 style={{ color: '#fbbf24', marginBottom: '6px' }}>Requirements</h5>
                            <ul>{data.requirements?.map((r, i) => <li key={i}>{r}</li>)}</ul>
                        </div>
                    </div>
                </div>
            );

        case 'ai_opportunities':
            return (
                <div>
                    <h4 style={{ color: '#a5b4fc', marginBottom: '16px' }}>Identified AI Opportunities:</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                        {data.opportunities?.map((opp, i) => (
                            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                                <h5 style={{ color: '#38bdf8', fontSize: '1.05rem', marginBottom: '6px' }}>{opp.opportunity_name}</h5>
                                <span style={{ fontSize: '0.75rem', background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', padding: '2px 8px', borderRadius: '4px', display: 'inline-block', marginBottom: '8px' }}>
                                    {opp.ai_capability}
                                </span>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>{opp.description}</p>
                                <p style={{ fontSize: '0.85rem', color: '#4ade80' }}><strong>Benefit:</strong> {opp.expected_benefit}</p>
                            </div>
                        ))}
                    </div>
                </div>
            );

        case 'solution_blueprint':
            return (
                <div>
                    <h4 style={{ color: '#a5b4fc', marginBottom: '8px' }}>Recommended Solution Architecture:</h4>
                    <p style={{ marginBottom: '20px' }}>{data.recommended_solution}</p>

                    <h5 style={{ color: '#f472b6', marginBottom: '12px' }}>System Modules</h5>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '24px' }}>
                        {data.system_modules?.map((m, i) => (
                            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: '14px', borderRadius: '8px' }}>
                                <strong style={{ color: '#38bdf8' }}>{m.module_name}</strong>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{m.description}</p>
                            </div>
                        ))}
                    </div>
                </div>
            );

        case 'data_api_design':
            return (
                <div>
                    <h4 style={{ color: '#a5b4fc', marginBottom: '12px' }}>Database DDL Script:</h4>
                    <pre className="code-block" style={{ marginBottom: '24px' }}>
                        {data.database_schema_sql}
                    </pre>

                    <h5 style={{ color: '#38bdf8', marginBottom: '12px' }}>REST API Endpoints:</h5>
                    <ul>
                        {data.rest_apis?.map((api, i) => (
                            <li key={i} style={{ marginBottom: '8px' }}>
                                <strong style={{ color: api.method === 'GET' ? '#6ee7b7' : '#f472b6' }}>[{api.method}]</strong> {api.path} — {api.summary}
                            </li>
                        ))}
                    </ul>
                </div>
            );

        case 'chat':
            return <AIConsultantChat activeProject={activeProject} blueprintData={blueprintData} />;

        default:
            return (
                <pre className="code-block">
                    {JSON.stringify(data, null, 2)}
                </pre>
            );
    }
}
