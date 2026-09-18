import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

const TONES = ['friendly', 'professional', 'casual', 'formal'];
const THEMES = ['light', 'dark', 'auto'];
const POSITIONS = ['bottom-right', 'bottom-left'];
const LANGUAGES = [
    { code: 'en', label: 'English' },
    { code: 'es', label: 'Spanish' },
    { code: 'fr', label: 'French' },
    { code: 'de', label: 'German' },
    { code: 'hi', label: 'Hindi' },
];

const DEFAULT_FORM = {
    name: '',
    description: '',
    welcome_message: 'Hello! How can I help you today?',
    tone: 'friendly',
    default_language: 'en',
    theme: 'light',
    position: 'bottom-right',
    suggested_questions: '',
    avatar_url: '',
};

function parseQuestions(val) {
    return val.split('\n').map(s => s.trim()).filter(Boolean);
}

function serializeQuestions(arr) {
    return (arr || []).join('\n');
}

// ── Inline Preview ────────────────────────────────────────────────────────────
function ChatbotPreview({ bot }) {
    const [messages, setMessages] = useState([{ role: 'assistant', content: bot.welcome_message }]);
    const [input, setInput] = useState('');
    const [sessionId, setSessionId] = useState(null);
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef(null);
    const apiBase = window.location.origin;

    useEffect(() => {
        setMessages([{ role: 'assistant', content: bot.welcome_message }]);
        setSessionId(null);
    }, [bot.id, bot.welcome_message]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const send = async () => {
        const text = input.trim();
        if (!text || loading) return;
        setInput('');
        setLoading(true);
        setMessages(m => [...m, { role: 'user', content: text }]);
        try {
            let sid = sessionId;
            if (!sid) {
                const s = await fetch(`${apiBase}/api/public/chatbots/${bot.id}/session`, { method: 'POST' });
                const sj = await s.json();
                sid = sj.session_id;
                setSessionId(sid);
            }
            const r = await fetch(`${apiBase}/api/public/chatbots/${bot.id}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sid, message: text }),
            });
            const rj = await r.json();
            setMessages(m => [...m, { role: 'assistant', content: rj.message }]);
        } catch {
            setMessages(m => [...m, { role: 'assistant', content: 'Error getting response.' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden', maxWidth: '380px' }}>
            <div style={{ background: 'linear-gradient(135deg,#10b981,#6366f1)', color: '#fff', padding: '12px 16px', fontWeight: 600 }}>
                {bot.avatar_url && <img src={bot.avatar_url} alt="" style={{ width: 24, height: 24, borderRadius: '50%', marginRight: 8, verticalAlign: 'middle' }} />}
                {bot.name}
            </div>
            <div style={{ height: 260, overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column', gap: 8, background: '#f8fafc' }}>
                {messages.map((m, i) => (
                    <div key={i} style={{
                        alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                        background: m.role === 'user' ? '#6366f1' : '#fff',
                        color: m.role === 'user' ? '#fff' : '#0f172a',
                        padding: '8px 12px', borderRadius: 10, maxWidth: '82%',
                        fontSize: '0.88rem', boxShadow: '0 1px 3px rgba(0,0,0,.08)'
                    }}>
                        {m.content}
                    </div>
                ))}
                {loading && <div style={{ alignSelf: 'flex-start', color: '#94a3b8', fontSize: '0.85rem', fontStyle: 'italic' }}>Thinking…</div>}
                <div ref={bottomRef} />
            </div>
            {bot.suggested_questions?.length > 0 && !sessionId && (
                <div style={{ padding: '6px 12px', display: 'flex', flexWrap: 'wrap', gap: 6, borderTop: '1px solid var(--border-color)', background: '#f8fafc' }}>
                    {bot.suggested_questions.slice(0, 3).map((q, i) => (
                        <button key={i} onClick={() => { setInput(q); }} style={{
                            fontSize: '0.78rem', padding: '4px 10px', borderRadius: 20,
                            border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', color: '#475569'
                        }}>{q}</button>
                    ))}
                </div>
            )}
            <div style={{ display: 'flex', gap: 8, padding: '10px 12px', borderTop: '1px solid var(--border-color)', background: '#fff' }}>
                <input
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send())}
                    placeholder="Type a message…"
                    style={{ flex: 1, border: '1px solid #e2e8f0', borderRadius: 8, padding: '7px 10px', fontSize: '0.88rem', outline: 'none' }}
                />
                <button onClick={send} disabled={loading} className="btn-emerald" style={{ padding: '7px 14px', fontSize: '0.85rem' }}>Send</button>
            </div>
        </div>
    );
}

// ── Embed Code ────────────────────────────────────────────────────────────────
function EmbedCode({ bot }) {
    const [copied, setCopied] = useState(false);
    const apiBase = window.location.origin;
    const snippet = `<script\n  src="${apiBase}/widget/chatbot.js"\n  data-chatbot-id="${bot.id}"\n  data-api-base="${apiBase}"\n></script>`;

    const copy = () => {
        navigator.clipboard.writeText(snippet).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    return (
        <div>
            <pre className="code-block" style={{ fontSize: '0.78rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{snippet}</pre>
            <button onClick={copy} className="btn-secondary" style={{ marginTop: 8, fontSize: '0.82rem', padding: '6px 14px' }}>
                {copied ? '✅ Copied!' : '📋 Copy Embed Code'}
            </button>
        </div>
    );
}

// ── Knowledge Panel ───────────────────────────────────────────────────────────
function KnowledgePanel({ bot, onUpdated }) {
    const [uploading, setUploading] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [msg, setMsg] = useState('');
    const fileRef = useRef(null);

    const upload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        setMsg('');
        try {
            const res = await api.uploadChatbotKnowledge(bot.id, file);
            setMsg(`✅ ${res.message}`);
            onUpdated();
        } catch (err) {
            setMsg(`❌ ${err.message}`);
        } finally {
            setUploading(false);
            if (fileRef.current) fileRef.current.value = '';
        }
    };

    const clear = async () => {
        if (!window.confirm('Clear all public knowledge for this chatbot?')) return;
        setClearing(true);
        try {
            await api.clearChatbotKnowledge(bot.id);
            setMsg('✅ Knowledge cleared.');
            onUpdated();
        } catch (err) {
            setMsg(`❌ ${err.message}`);
        } finally {
            setClearing(false);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Current chunks: <strong>{bot.chunk_count}</strong>
            </p>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <label className="btn-secondary" style={{ cursor: 'pointer', fontSize: '0.85rem', padding: '8px 14px' }}>
                    {uploading ? 'Uploading…' : '📄 Upload Document'}
                    <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.txt" style={{ display: 'none' }} onChange={upload} disabled={uploading} />
                </label>
                {bot.chunk_count > 0 && (
                    <button onClick={clear} disabled={clearing} className="btn-secondary" style={{ fontSize: '0.85rem', padding: '8px 14px', color: '#dc2626', borderColor: '#fca5a5' }}>
                        {clearing ? 'Clearing…' : '🗑 Clear All Knowledge'}
                    </button>
                )}
            </div>
            {msg && <p style={{ fontSize: '0.83rem', color: msg.startsWith('✅') ? '#059669' : '#dc2626' }}>{msg}</p>}
        </div>
    );
}

// ── Chatbot Form ──────────────────────────────────────────────────────────────
function ChatbotForm({ initial, onSave, onCancel, saving }) {
    const [form, setForm] = useState(initial || DEFAULT_FORM);
    const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

    const handleSubmit = (e) => {
        e.preventDefault();
        const data = {
            ...form,
            suggested_questions: parseQuestions(form.suggested_questions),
        };
        onSave(data);
    };

    const inputStyle = { width: '100%', border: '1px solid var(--border-color)', borderRadius: 8, padding: '8px 12px', fontSize: '0.88rem', background: '#fff', color: 'var(--text-main)', fontFamily: 'inherit' };
    const labelStyle = { fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4, display: 'block' };
    const row = { display: 'flex', flexDirection: 'column', gap: 4 };

    return (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={row}>
                <label style={labelStyle}>Name *</label>
                <input style={inputStyle} value={form.name} onChange={e => set('name', e.target.value)} required placeholder="My Support Bot" />
            </div>
            <div style={row}>
                <label style={labelStyle}>Description</label>
                <input style={inputStyle} value={form.description} onChange={e => set('description', e.target.value)} placeholder="Helps visitors with product questions" />
            </div>
            <div style={row}>
                <label style={labelStyle}>Welcome Message</label>
                <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 60 }} value={form.welcome_message} onChange={e => set('welcome_message', e.target.value)} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={row}>
                    <label style={labelStyle}>Tone</label>
                    <select style={inputStyle} value={form.tone} onChange={e => set('tone', e.target.value)}>
                        {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                    </select>
                </div>
                <div style={row}>
                    <label style={labelStyle}>Language</label>
                    <select style={inputStyle} value={form.default_language} onChange={e => set('default_language', e.target.value)}>
                        {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
                    </select>
                </div>
                <div style={row}>
                    <label style={labelStyle}>Theme</label>
                    <select style={inputStyle} value={form.theme} onChange={e => set('theme', e.target.value)}>
                        {THEMES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                    </select>
                </div>
                <div style={row}>
                    <label style={labelStyle}>Position</label>
                    <select style={inputStyle} value={form.position} onChange={e => set('position', e.target.value)}>
                        {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                </div>
            </div>
            <div style={row}>
                <label style={labelStyle}>Avatar URL (optional)</label>
                <input style={inputStyle} value={form.avatar_url} onChange={e => set('avatar_url', e.target.value)} placeholder="https://example.com/avatar.png" />
            </div>
            <div style={row}>
                <label style={labelStyle}>Suggested Questions (one per line)</label>
                <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 70 }} value={form.suggested_questions} onChange={e => set('suggested_questions', e.target.value)} placeholder={"What are your hours?\nHow do I contact support?"} />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : '💾 Save'}</button>
                <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
            </div>
        </form>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function PublicChatbotManager() {
    const [bots, setBots] = useState([]);
    const [loading, setLoading] = useState(true);
    const [view, setView] = useState('list'); // list | create | detail
    const [selected, setSelected] = useState(null);
    const [detailTab, setDetailTab] = useState('settings'); // settings | knowledge | preview | embed
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const load = async () => {
        setLoading(true);
        try {
            const data = await api.listChatbots();
            setBots(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const openDetail = (bot) => {
        setSelected(bot);
        setDetailTab('settings');
        setView('detail');
    };

    const refreshSelected = async () => {
        if (!selected) return;
        try {
            const updated = await api.getChatbot(selected.id);
            setSelected(updated);
            setBots(bs => bs.map(b => b.id === updated.id ? updated : b));
        } catch { /* ignore */ }
    };

    const handleCreate = async (data) => {
        setSaving(true);
        setError('');
        try {
            const bot = await api.createChatbot(data);
            setBots(bs => [...bs, bot]);
            setSelected(bot);
            setDetailTab('settings');
            setView('detail');
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleUpdate = async (data) => {
        setSaving(true);
        setError('');
        try {
            const updated = await api.updateChatbot(selected.id, data);
            setSelected(updated);
            setBots(bs => bs.map(b => b.id === updated.id ? updated : b));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleToggle = async (bot) => {
        try {
            const updated = await api.updateChatbot(bot.id, { is_active: !bot.is_active });
            setBots(bs => bs.map(b => b.id === updated.id ? updated : b));
            if (selected?.id === bot.id) setSelected(updated);
        } catch (err) {
            setError(err.message);
        }
    };

    const handleDelete = async (bot) => {
        if (!window.confirm(`Delete chatbot "${bot.name}"? This cannot be undone.`)) return;
        try {
            await api.deleteChatbot(bot.id);
            setBots(bs => bs.filter(b => b.id !== bot.id));
            if (selected?.id === bot.id) { setSelected(null); setView('list'); }
        } catch (err) {
            setError(err.message);
        }
    };

    const cardStyle = { background: '#fff', border: '1px solid var(--border-color)', borderRadius: 12, padding: '16px 20px' };

    // ── List View ──────────────────────────────────────────────────────────────
    if (view === 'list') {
        return (
            <div className="glass-card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)' }}>🤖 Public Chatbots</h2>
                    <button className="btn-primary" onClick={() => setView('create')}>+ New Chatbot</button>
                </div>
                {error && <p style={{ color: '#dc2626', marginBottom: 12, fontSize: '0.85rem' }}>{error}</p>}
                {loading ? (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Loading…</p>
                ) : bots.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                        <p style={{ fontSize: '2rem', marginBottom: 8 }}>🤖</p>
                        <p>No chatbots yet. Create one to get started.</p>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {bots.map(bot => (
                            <div key={bot.id} style={{ ...cardStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                        <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{bot.name}</span>
                                        <span style={{
                                            fontSize: '0.72rem', padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                                            background: bot.is_active ? '#ecfdf5' : '#fef2f2',
                                            color: bot.is_active ? '#059669' : '#dc2626',
                                            border: `1px solid ${bot.is_active ? '#a7f3d0' : '#fca5a5'}`
                                        }}>
                                            {bot.is_active ? 'Active' : 'Disabled'}
                                        </span>
                                    </div>
                                    {bot.description && <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 2 }}>{bot.description}</p>}
                                    <p style={{ fontSize: '0.78rem', color: 'var(--text-light)', marginTop: 2 }}>
                                        {bot.chunk_count} knowledge chunks · {bot.tone} · {bot.theme}
                                    </p>
                                </div>
                                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                                    <button className="btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px' }} onClick={() => openDetail(bot)}>Manage</button>
                                    <button
                                        className="btn-secondary"
                                        style={{ fontSize: '0.82rem', padding: '6px 12px', color: bot.is_active ? '#dc2626' : '#059669', borderColor: bot.is_active ? '#fca5a5' : '#a7f3d0' }}
                                        onClick={() => handleToggle(bot)}
                                    >
                                        {bot.is_active ? 'Disable' : 'Enable'}
                                    </button>
                                    <button className="btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px', color: '#dc2626', borderColor: '#fca5a5' }} onClick={() => handleDelete(bot)}>Delete</button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // ── Create View ────────────────────────────────────────────────────────────
    if (view === 'create') {
        return (
            <div className="glass-card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                    <button className="btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px' }} onClick={() => setView('list')}>← Back</button>
                    <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Create New Chatbot</h2>
                </div>
                {error && <p style={{ color: '#dc2626', marginBottom: 12, fontSize: '0.85rem' }}>{error}</p>}
                <ChatbotForm onSave={handleCreate} onCancel={() => setView('list')} saving={saving} />
            </div>
        );
    }

    // ── Detail View ────────────────────────────────────────────────────────────
    if (view === 'detail' && selected) {
        const initialForm = {
            ...selected,
            suggested_questions: serializeQuestions(selected.suggested_questions),
            avatar_url: selected.avatar_url || '',
        };

        return (
            <div className="glass-card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <button className="btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px' }} onClick={() => { setView('list'); setSelected(null); }}>← Back</button>
                        <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{selected.name}</h2>
                        <span style={{
                            fontSize: '0.72rem', padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                            background: selected.is_active ? '#ecfdf5' : '#fef2f2',
                            color: selected.is_active ? '#059669' : '#dc2626',
                            border: `1px solid ${selected.is_active ? '#a7f3d0' : '#fca5a5'}`
                        }}>
                            {selected.is_active ? 'Active' : 'Disabled'}
                        </span>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button
                            className="btn-secondary"
                            style={{ fontSize: '0.82rem', padding: '6px 12px', color: selected.is_active ? '#dc2626' : '#059669', borderColor: selected.is_active ? '#fca5a5' : '#a7f3d0' }}
                            onClick={() => handleToggle(selected)}
                        >
                            {selected.is_active ? 'Disable' : 'Enable'}
                        </button>
                        <button className="btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px', color: '#dc2626', borderColor: '#fca5a5' }} onClick={() => handleDelete(selected)}>Delete</button>
                    </div>
                </div>

                {error && <p style={{ color: '#dc2626', marginBottom: 12, fontSize: '0.85rem' }}>{error}</p>}

                {/* Tabs */}
                <div className="tabs-header" style={{ marginBottom: 20 }}>
                    {[['settings', '⚙️ Settings'], ['knowledge', '📚 Knowledge'], ['preview', '👁 Preview'], ['embed', '</> Embed']].map(([key, label]) => (
                        <button key={key} className={`tab-btn${detailTab === key ? ' active' : ''}`} onClick={() => setDetailTab(key)}>{label}</button>
                    ))}
                </div>

                {detailTab === 'settings' && (
                    <ChatbotForm
                        key={selected.id}
                        initial={initialForm}
                        onSave={handleUpdate}
                        onCancel={() => setView('list')}
                        saving={saving}
                    />
                )}

                {detailTab === 'knowledge' && (
                    <KnowledgePanel bot={selected} onUpdated={refreshSelected} />
                )}

                {detailTab === 'preview' && (
                    <div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 12 }}>
                            Live preview using the same public API the widget uses.
                            {!selected.is_active && <strong style={{ color: '#dc2626' }}> (Chatbot is disabled — enable it to test.)</strong>}
                        </p>
                        {selected.is_active ? <ChatbotPreview bot={selected} /> : (
                            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border-color)', borderRadius: 12 }}>
                                Enable the chatbot to preview it.
                            </div>
                        )}
                    </div>
                )}

                {detailTab === 'embed' && (
                    <div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 12 }}>
                            Paste this snippet into any webpage to embed the chatbot widget.
                        </p>
                        <EmbedCode bot={selected} />
                    </div>
                )}
            </div>
        );
    }

    return null;
}
