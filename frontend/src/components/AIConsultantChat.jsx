import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../api/client';
import {
    useSpeechRecognition,
    SPEECH_LANGUAGES,
    SPEECH_STATES,
    isSpeechSupported,
} from '../hooks/useSpeechRecognition';

export const AIConsultantChat = ({ activeProject, onSelectProject, blueprintData, onBlueprintUpdated, onViewDashboard }) => {
    const [conversations, setConversations] = useState([]);
    const [activeConvId, setActiveConvId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [copiedIndex, setCopiedIndex] = useState(null);
    const [error, setError] = useState('');
    const messagesEndRef = useRef(null);

    const [projectMemory, setProjectMemory] = useState([]);
    const [projectDecisions, setProjectDecisions] = useState([]);
    const [knowledgeSources, setKnowledgeSources] = useState([]);
    const [websiteUrlInput, setWebsiteUrlInput] = useState('');
    const [addingWebsite, setAddingWebsite] = useState(false);
    const [feedbackState, setFeedbackState] = useState({});
    const [feedbackComment, setFeedbackComment] = useState({});
    const [showHandoff, setShowHandoff] = useState(false);
    const [handoffForm, setHandoffForm] = useState({ subject: '', description: '', priority: 'normal' });
    const [handoffList, setHandoffList] = useState([]);
    const [handoffSubmitting, setHandoffSubmitting] = useState(false);
    const [handoffError, setHandoffError] = useState('');

    // Drawer / menu state
    const [showTransformation, setShowTransformation] = useState(false);
    const [showKnowledge, setShowKnowledge] = useState(false);
    const [showHelpDrawer, setShowHelpDrawer] = useState(false);
    const [showToolsMenu, setShowToolsMenu] = useState(false);
    const [showExportMenu, setShowExportMenu] = useState(false);
    const toolsMenuRef = useRef(null);
    const exportMenuRef = useRef(null);

    // Speech
    const [speechLang, setSpeechLang] = useState('en-IN');
    const handleSpeechResult = useCallback((transcript) => {
        setInput((prev) => {
            const trimmed = prev.trimEnd();
            return trimmed ? trimmed + ' ' + transcript : transcript;
        });
    }, []);
    const { speechState, errorMessage: speechError, interimText, isSupported: speechSupported,
        toggleRecognition, stopRecognition } = useSpeechRecognition({ lang: speechLang, onResult: handleSpeechResult });
    const isListening = speechState === SPEECH_STATES.LISTENING;

    // Close menus on outside click
    useEffect(() => {
        const handler = (e) => {
            if (toolsMenuRef.current && !toolsMenuRef.current.contains(e.target)) setShowToolsMenu(false);
            if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) setShowExportMenu(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const loadProjectMemoryAndDecisions = async (projectId) => {
        if (!projectId) return;
        try {
            const memRes = await api.getProjectMemory(projectId);
            setProjectMemory(memRes?.memories || []);
            const decRes = await api.getProjectDecisions(projectId);
            setProjectDecisions(decRes?.decisions || []);
        } catch (err) { console.error('Failed to load memory or decisions:', err); }
    };

    const loadKnowledgeSources = async (projectId) => {
        if (!projectId) return;
        try {
            const sources = await api.listKnowledgeSources(projectId);
            setKnowledgeSources(sources || []);
        } catch (err) { console.error('Failed to load knowledge sources:', err); }
    };

    const handleUploadKnowledgeDocument = async (e) => {
        const file = e.target.files?.[0];
        if (!file || !activeProject?.id) return;
        setUploading(true); setError('');
        try {
            await api.uploadKnowledgeDocument(activeProject.id, file);
            await loadKnowledgeSources(activeProject.id);
        } catch (err) { setError('Upload failed: ' + (err.message || 'Unknown error')); }
        finally { setUploading(false); e.target.value = ''; }
    };

    const handleAddWebsiteKnowledge = async (e) => {
        e.preventDefault();
        if (!websiteUrlInput.trim() || !activeProject?.id || addingWebsite) return;
        setAddingWebsite(true);
        try {
            await api.ingestWebsiteKnowledge(activeProject.id, websiteUrlInput.trim());
            setWebsiteUrlInput('');
            await loadKnowledgeSources(activeProject.id);
        } catch (err) { setError('Failed to ingest website knowledge: ' + err.message); }
        finally { setAddingWebsite(false); }
    };

    const handleRefreshWebsiteKnowledge = async (sourceId) => {
        if (!activeProject?.id) return;
        try {
            await api.refreshWebsiteKnowledge(activeProject.id, sourceId);
            await loadKnowledgeSources(activeProject.id);
        } catch (err) { setError('Failed to refresh: ' + err.message); }
    };

    const handleDeleteKnowledgeSource = async (sourceId) => {
        if (!activeProject?.id) return;
        try {
            await api.deleteKnowledgeSource(activeProject.id, sourceId);
            await loadKnowledgeSources(activeProject.id);
        } catch (err) { setError('Failed to delete: ' + err.message); }
    };

    useEffect(() => { stopRecognition(); }, [activeProject?.id]);

    useEffect(() => {
        setActiveConvId(null); setMessages([]);
        setFeedbackState({}); setFeedbackComment({});
        setShowHandoff(false); setHandoffList([]);
        if (activeProject?.id) {
            loadConversations(activeProject.id);
            loadProjectMemoryAndDecisions(activeProject.id);
            loadKnowledgeSources(activeProject.id);
            loadHandoffs(activeProject.id);
        } else {
            setConversations([]); setProjectMemory([]);
            setProjectDecisions([]); setKnowledgeSources([]);
        }
    }, [activeProject?.id]);

    useEffect(() => {
        if (activeConvId) {
            loadMessages(activeConvId);
        } else if (activeProject?.id) {
            setMessages([{
                role: 'assistant',
                content: `Hello! I'm your **AI Business Transformation Consultant** for the **${activeProject.name}** project.\n\nI have your business context ready. Ask me anything about your solution — AI capabilities, architecture, database design, workflow steps — or say **"Generate everything"** to build the full 7-stage blueprint.`
            }]);
        }
    }, [activeConvId, activeProject?.id, activeProject?.name]);

    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

    const loadConversations = async (projId) => {
        try {
            const list = await api.listConversations(projId);
            setConversations(list);
            if (list.length > 0) setActiveConvId(list[0].id);
        } catch (err) { console.error('Failed to load conversations:', err); }
    };

    const loadMessages = async (convId) => {
        try {
            const msgs = await api.getConversationMessages(convId);
            setMessages(msgs);
        } catch (err) { console.error('Failed to load messages:', err); }
    };

    const ensureActiveProject = async (textIdea) => {
        try {
            const workspaces = await api.listWorkspaces();
            let wsId = workspaces.length > 0 ? workspaces[0].id : null;
            if (!wsId) { const newWs = await api.createWorkspace('Default Workspace'); wsId = newWs.id; }
            if (activeProject) {
                if (!activeProject.business_idea && textIdea) {
                    const updated = await api.updateProject(activeProject.id, { business_idea: textIdea });
                    onSelectProject(updated); return updated;
                }
                return activeProject;
            }
            const title = textIdea.slice(0, 30) + '...';
            const proj = await api.createProject(title, wsId, textIdea);
            onSelectProject(proj); return proj;
        } catch (err) { setError('Failed to auto-initialize project: ' + err.message); return null; }
    };

    const handleSendMessage = async (textToSend) => {
        const query = textToSend || input;
        if (!query.trim() || loading) return;
        setError(''); setLoading(true);
        const targetProj = await ensureActiveProject(query);
        if (!targetProj) { setLoading(false); return; }
        if (!targetProj.business_idea) {
            try { const updated = await api.updateProject(targetProj.id, { business_idea: query }); onSelectProject(updated); }
            catch (err) { console.error('Failed to sync business idea:', err); }
        }
        const userMsg = { role: 'user', content: query };
        setMessages((prev) => [...prev, userMsg]);
        if (!textToSend) setInput('');
        try {
            const res = await api.sendChatMessage(targetProj.id, query, activeConvId);
            if (res.project && onSelectProject) onSelectProject(res.project);
            if (res.conversation_id && !activeConvId) { setActiveConvId(res.conversation_id); loadConversations(targetProj.id); }
            setMessages((prev) => [...prev, { role: 'assistant', content: res.message }]);
            if (res.stage_triggered) {
                const bpRes = await api.getBlueprint(targetProj.id);
                if (bpRes.blueprint && onBlueprintUpdated) onBlueprintUpdated(bpRes.blueprint);
            }
        } catch (err) {
            setError(err.message || 'Failed to get AI Consultant response.');
            setMessages((prev) => [...prev, { role: 'assistant', content: `⚠️ Error: ${err.message || 'Unable to complete request.'}` }]);
        } finally { setLoading(false); }
    };

    const handleDocumentUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true); setError('');
        try {
            const targetProj = await ensureActiveProject(`Document Context: ${file.name}`);
            if (!targetProj) return;
            const updatedProj = await api.uploadDocument(targetProj.id, file);
            onSelectProject(updatedProj);
            setMessages((prev) => [...prev, { role: 'assistant', content: `📁 Uploaded document "${file.name}". Automatically extracted text and attached context to your project.` }]);
        } catch (err) { setError('Document upload failed: ' + err.message); }
        finally { setUploading(false); }
    };

    const handleExportTranscript = () => {
        if (!messages || messages.length === 0) return;
        const transcriptText = messages.map((m) => `### ${m.role.toUpperCase()}\n${m.content}\n`).join('\n---\n\n');
        const blob = new Blob([transcriptText], { type: 'text/markdown;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${activeProject?.name || 'Consultation'}_Transcript.md`);
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
    };

    const handleExportBlueprint = async (format) => {
        if (!activeProject) return;
        const ext = { markdown: 'md', json: 'json', html: 'html' }[format] || format;
        const filename = `${activeProject.name.toLowerCase().replace(/\s+/g, '_')}_blueprint.${ext}`;
        try { await api.exportProject(activeProject.id, format, filename); } catch (e) { console.error(e); }
        setShowExportMenu(false);
    };

    const mdComponents = {
        h1: ({children}) => <h2 className="md-h1">{children}</h2>,
        h2: ({children}) => <h3 className="md-h2">{children}</h3>,
        h3: ({children}) => <h4 className="md-h3">{children}</h4>,
        h4: ({children}) => <h5 className="md-h4">{children}</h5>,
        p: ({children}) => <p className="md-p">{children}</p>,
        ul: ({children}) => <ul className="md-ul">{children}</ul>,
        ol: ({children}) => <ol className="md-ol">{children}</ol>,
        li: ({children}) => <li className="md-li">{children}</li>,
        strong: ({children}) => <strong className="md-strong">{children}</strong>,
        em: ({children}) => <em>{children}</em>,
        code: ({node, inline, className, children, ...props}) => {
            const isInline = !className && inline !== false && !String(children).includes('\n');
            return isInline
                ? <code className="md-code-inline" {...props}>{children}</code>
                : <pre className="md-code-block"><code>{children}</code></pre>;
        },
        pre: ({children}) => <>{children}</>,
        table: ({children}) => <div className="md-table-wrap"><table className="md-table">{children}</table></div>,
        th: ({children}) => <th className="md-th">{children}</th>,
        td: ({children}) => <td className="md-td">{children}</td>,
        blockquote: ({children}) => <blockquote className="md-blockquote">{children}</blockquote>,
        hr: () => <hr className="md-hr" />,
    };

    const renderMarkdown = (content) => (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{content || ''}</ReactMarkdown>
    );

    const handleCopyText = (content, index) => {
        navigator.clipboard.writeText(content);
        setCopiedIndex(index);
        setTimeout(() => setCopiedIndex(null), 2000);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
    };

    const handleFeedback = async (idx, rating, msgId) => {
        if (!activeProject?.id) return;
        if (feedbackState[idx] === rating) return;
        if (rating === 'negative' && feedbackState[idx] !== 'commenting') {
            setFeedbackState((prev) => ({ ...prev, [idx]: 'commenting' })); return;
        }
        try {
            const comment = feedbackComment[idx] || null;
            await api.submitFeedback(activeProject.id, rating, comment, msgId || null, activeConvId || null);
            setFeedbackState((prev) => ({ ...prev, [idx]: rating }));
        } catch (err) { console.error('Feedback failed:', err); }
    };

    const loadHandoffs = async (projectId) => {
        if (!projectId) return;
        try { const list = await api.listHandoffs(projectId); setHandoffList(list || []); }
        catch (err) { console.error('Failed to load handoffs:', err); }
    };

    const handleSubmitHandoff = async (e) => {
        e.preventDefault();
        if (!activeProject?.id || !handoffForm.subject.trim() || !handoffForm.description.trim()) return;
        setHandoffSubmitting(true); setHandoffError('');
        try {
            await api.createHandoff(activeProject.id, handoffForm.subject.trim(), handoffForm.description.trim(), handoffForm.priority, activeConvId || null);
            setHandoffForm({ subject: '', description: '', priority: 'normal' });
            await loadHandoffs(activeProject.id);
        } catch (err) { setHandoffError(err.message || 'Failed to submit request.'); }
        finally { setHandoffSubmitting(false); }
    };

    const completedStageCount = blueprintData
        ? ['business_analysis','ai_opportunities','solution_blueprint','architecture','data_api_design','ux_design','roadmap'].filter((s) => blueprintData[s]).length
        : 0;
    const completionPercent = Math.round((completedStageCount / 7) * 100);

    const STAGES = [
        { key: 'business_analysis', label: 'Business Analysis' },
        { key: 'ai_opportunities', label: 'AI Opportunities' },
        { key: 'solution_blueprint', label: 'Solution Blueprint' },
        { key: 'architecture', label: 'System Architecture' },
        { key: 'data_api_design', label: 'Database & API' },
        { key: 'ux_design', label: 'UX Recommendations' },
        { key: 'roadmap', label: 'Implementation' },
    ];

    const heroCards = [
        { icon: "🧾", title: "Vendor Invoice Automation", idea: "Small businesses waste 15+ hours weekly manually typing paper vendor receipts and invoices into accounting software, leading to data entry errors and late supplier payments." },
        { icon: "🎓", title: "College Faculty Booking", idea: "A college wants to build a system where students can book academic advising appointments with faculty members, check availability, and receive notifications." },
        { icon: "🩺", title: "Connected Blood Reports", idea: "Healthcare platform connecting diagnostic labs with patients and doctors to analyze blood test reports, track biomarkers, and alert on abnormal health ranges." },
    ];

    const suggestedPrompts = [
        "Analyze my problem", "What AI can we use?", "Why this architecture?",
        "What database should we use?", "Show me the workflow",
        "Create architecture", "Create database design", "Generate everything"
    ];

    // ── HERO / EMPTY STATE ──────────────────────────────────────────────────
    if (!activeProject && messages.length === 0) {
        return (
            <div className="hero-wrap">
                <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                    <h1 className="hero-title">Business Transformation AI</h1>
                    <p className="hero-sub">Turn your business idea into an implementation-ready solution blueprint.</p>
                </div>
                <div className="hero-cards">
                    {heroCards.map((card, i) => (
                        <div key={i} className="hero-card" onClick={() => handleSendMessage(card.idea)}>
                            <div className="hero-card-title">{card.icon} {card.title}</div>
                            <div className="hero-card-body">{card.idea}</div>
                            <div className="hero-card-cta">Start consultation →</div>
                        </div>
                    ))}
                </div>
                <div className="composer-inner" style={{ width: '100%', maxWidth: '720px' }}>
                    <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}>
                        <div className="composer-box">
                            <label style={{ cursor: 'pointer', flexShrink: 0 }} title={uploading ? 'Uploading...' : 'Upload document'}>
                                <span className="composer-icon-btn" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32 }}>📎</span>
                                <input type="file" accept=".pdf,.docx,.doc,.pptx,.ppt,.txt" onChange={handleDocumentUpload} style={{ display: 'none' }} disabled={uploading} />
                            </label>
                            <textarea className="composer-textarea" rows={1} placeholder="Describe your business idea or problem..." value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} />
                            {speechSupported && (
                                <button type="button" onClick={toggleRecognition} className={`composer-icon-btn${isListening ? ' listening' : ''}`} title={isListening ? 'Stop' : 'Voice input'}>🎤</button>
                            )}
                            <button type="submit" className="composer-btn" disabled={loading || !input.trim()}>↑</button>
                        </div>
                    </form>
                </div>
            </div>
        );
    }

    // ── MAIN CHAT VIEW ──────────────────────────────────────────────────────
    return (
        <div className="chat-shell">

            {/* ── TOP BAR ── */}
            <div className="chat-topbar">
                <div className="chat-topbar-left">
                    <span className="chat-topbar-title">AI Business Transformation Consultant</span>
                    {activeProject && (
                        <span className="chat-topbar-sub">
                            Project: <strong style={{ color: 'var(--text)' }}>{activeProject.name}</strong>
                        </span>
                    )}
                </div>
                <div className="chat-topbar-right">
                    {/* Transformation tracker toggle */}
                    {activeProject && (
                        <button
                            className={`topbar-btn${showTransformation ? ' active' : ''}`}
                            onClick={() => { setShowTransformation((s) => !s); setShowKnowledge(false); setShowHelpDrawer(false); }}
                        >
                            ◎ Transformation {completionPercent > 0 ? `${completionPercent}%` : ''}
                        </button>
                    )}

                    {/* Knowledge sources toggle */}
                    {activeProject && (
                        <button
                            className={`topbar-btn${showKnowledge ? ' active' : ''}`}
                            onClick={() => { setShowKnowledge((s) => !s); setShowTransformation(false); setShowHelpDrawer(false); }}
                        >
                            📚 Knowledge {knowledgeSources.length > 0 ? `(${knowledgeSources.length})` : ''}
                        </button>
                    )}

                    {/* Tools menu */}
                    {activeProject && (
                        <div style={{ position: 'relative' }} ref={toolsMenuRef}>
                            <button className={`topbar-btn${showToolsMenu ? ' active' : ''}`} onClick={() => setShowToolsMenu((s) => !s)}>
                                ⚡ Tools ▾
                            </button>
                            {showToolsMenu && (
                                <div className="tools-menu">
                                    <button className="tools-menu-item" onClick={() => { handleSendMessage('Analyze my problem'); setShowToolsMenu(false); }}>🧾 Analyze Business Problem</button>
                                    <button className="tools-menu-item" onClick={() => { handleSendMessage('What AI can we use?'); setShowToolsMenu(false); }}>🤖 Find AI Opportunities</button>
                                    <button className="tools-menu-item" onClick={() => { handleSendMessage('Create architecture'); setShowToolsMenu(false); }}>🏗️ Generate Architecture</button>
                                    <button className="tools-menu-item" onClick={() => { handleSendMessage('Create database design'); setShowToolsMenu(false); }}>🗄️ Generate DB & APIs</button>
                                    <div className="tools-menu-divider" />
                                    <button className="tools-menu-item" onClick={() => { handleSendMessage('Generate everything'); setShowToolsMenu(false); }}>🚀 Generate Full Blueprint</button>
                                    <div className="tools-menu-divider" />
                                    <button className="tools-menu-item" onClick={() => { setShowHelpDrawer(true); setShowToolsMenu(false); setShowTransformation(false); setShowKnowledge(false); }}>📩 Request Human Help</button>
                                    {onViewDashboard && (
                                        <button className="tools-menu-item" onClick={() => { onViewDashboard(); setShowToolsMenu(false); }}>📊 Blueprint Dashboard</button>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Export menu */}
                    <div style={{ position: 'relative' }} ref={exportMenuRef}>
                        <button className={`topbar-btn${showExportMenu ? ' active' : ''}`} onClick={() => setShowExportMenu((s) => !s)}>
                            📥 Export ▾
                        </button>
                        {showExportMenu && (
                            <div className="tools-menu">
                                <button className="tools-menu-item" onClick={handleExportTranscript} disabled={messages.length === 0}>💬 Chat Transcript (.md)</button>
                                {activeProject && (
                                    <>
                                        <div className="tools-menu-divider" />
                                        <button className="tools-menu-item" onClick={() => handleExportBlueprint('markdown')}>📝 Blueprint (.md)</button>
                                        <button className="tools-menu-item" onClick={() => handleExportBlueprint('json')}>📦 Blueprint (.json)</button>
                                        <button className="tools-menu-item" onClick={() => handleExportBlueprint('html')}>🌐 Blueprint (.html)</button>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── MESSAGES AREA ── */}
            <div className="messages-area">
                <div className="messages-inner">
                    {/* Suggested prompt chips */}
                    {messages.length <= 1 && activeProject && (
                        <div className="chips-row">
                            {suggestedPrompts.map((sug, i) => (
                                <button key={i} className="chip" onClick={() => handleSendMessage(sug)} disabled={loading}>
                                    {sug}
                                </button>
                            ))}
                        </div>
                    )}

                    {messages.map((m, idx) => (
                        <div key={idx} className={m.role === 'user' ? 'msg-user-row' : 'msg-ai-row'}>
                            {m.role === 'assistant' && <div className="ai-avatar" aria-hidden="true">✦</div>}
                            <div className={m.role === 'user' ? 'msg-user-bubble' : 'msg-ai-content'}>
                                {m.role === 'assistant' && <div className="msg-ai-label">Business Transformation AI</div>}
                                {m.role === 'user'
                                    ? <span>{m.content}</span>
                                    : <div className="md-body">{renderMarkdown(m.content)}</div>
                                }
                                {m.role === 'assistant' && (
                                    <div className="msg-actions">
                                        <button onClick={() => handleFeedback(idx, 'positive', m.id)} title="Useful" className={`action-btn${feedbackState[idx] === 'positive' ? ' action-btn--active-pos' : ''}`}>👍</button>
                                        <button onClick={() => handleFeedback(idx, 'negative', m.id)} title="Not useful" className={`action-btn${feedbackState[idx] === 'negative' ? ' action-btn--active-neg' : ''}`}>👎</button>
                                        <button onClick={() => handleCopyText(m.content, idx)} className="action-btn" title="Copy">{copiedIndex === idx ? '✓' : '⎘'}</button>
                                        {feedbackState[idx] === 'commenting' && (
                                            <div className="feedback-comment-row">
                                                <input type="text" placeholder="Optional comment..." value={feedbackComment[idx] || ''} onChange={(e) => setFeedbackComment((prev) => ({ ...prev, [idx]: e.target.value }))} className="feedback-input" maxLength={200} />
                                                <button onClick={async () => {
                                                    try {
                                                        await api.submitFeedback(activeProject.id, 'negative', feedbackComment[idx] || null, m.id || null, activeConvId || null);
                                                        setFeedbackState((prev) => ({ ...prev, [idx]: 'negative' }));
                                                    } catch (err) { console.error(err); }
                                                }} className="action-btn action-btn--active-neg">Send</button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="msg-ai-row">
                            <div className="ai-avatar" aria-hidden="true">✦</div>
                            <div className="msg-ai-content">
                                <div className="msg-ai-label">Business Transformation AI</div>
                                <div className="msg-ai-thinking">
                                    <span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* ── COMPOSER ── */}
            <div className="composer-wrap">
                <div className="composer-inner">
                    {isListening && (
                        <div className="speech-bar">
                            <span style={{ animation: 'micPulse 1s infinite', display: 'inline-block' }}>🔴</span>
                            Listening...
                            {interimText && <span className="speech-bar-interim">"{interimText}"</span>}
                        </div>
                    )}
                    {speechError && (
                        <div style={{ padding: '6px 12px', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: '8px', fontSize: '0.8125rem', color: '#fbbf24', marginBottom: '8px' }}>
                            {speechError}
                        </div>
                    )}
                    {error && (
                        <div style={{ padding: '6px 12px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '8px', fontSize: '0.8125rem', color: '#fca5a5', marginBottom: '8px' }}>
                            Something went wrong. Please try again.
                        </div>
                    )}
                    <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}>
                        <div className="composer-box">
                            {/* Attach document */}
                            <label style={{ cursor: 'pointer', flexShrink: 0 }} title={uploading ? 'Uploading...' : 'Upload document'}>
                                <span className={`composer-icon-btn${uploading ? ' listening' : ''}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32 }}>
                                    {uploading ? '⏳' : '📎'}
                                </span>
                                <input type="file" accept=".pdf,.docx,.doc,.pptx,.ppt,.txt" onChange={handleDocumentUpload} style={{ display: 'none' }} disabled={uploading} />
                            </label>

                            <textarea
                                className="composer-textarea"
                                rows={1}
                                placeholder="Ask your consultant... (Enter to send, Shift+Enter for new line)"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={loading}
                                aria-label="Chat message input"
                            />

                            {/* Language selector + mic */}
                            {speechSupported && (
                                <>
                                    <select
                                        value={speechLang}
                                        onChange={(e) => setSpeechLang(e.target.value)}
                                        disabled={isListening}
                                        aria-label="Speech recognition language"
                                        className="composer-lang-select"
                                    >
                                        {SPEECH_LANGUAGES.map((l) => (
                                            <option key={l.code} value={l.code}>{l.label}</option>
                                        ))}
                                    </select>
                                    <button type="button" onClick={toggleRecognition} className={`composer-icon-btn${isListening ? ' listening' : ''}`} aria-label={isListening ? 'Stop voice input' : 'Start voice input'} title={isListening ? 'Stop voice input' : 'Start voice input'}>
                                        {isListening ? '🔴' : '🎤'}
                                    </button>
                                </>
                            )}

                            <button type="submit" className="composer-btn" disabled={loading || !input.trim()}>↑</button>
                        </div>
                    </form>
                    <p className="composer-hint">Enter to send · Shift+Enter for new line</p>
                </div>
            </div>

            {/* ── TRANSFORMATION DRAWER ── */}
            {showTransformation && activeProject && (
                <>
                    <div className="drawer-overlay" onClick={() => setShowTransformation(false)} />
                    <div className="drawer">
                        <div className="drawer-header">
                            <span className="drawer-title">TRANSFORMATION PROGRESS</span>
                            <button className="drawer-close" onClick={() => setShowTransformation(false)}>✕</button>
                        </div>
                        <div className="drawer-body">
                            {/* Progress */}
                            <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                    <span className="drawer-section-label">Overall Progress</span>
                                    <span style={{ fontSize: '1.25rem', fontWeight: '700', color: '#a3e4d7' }}>{completionPercent}%</span>
                                </div>
                                <div className="progress-bar-track"><div className="progress-bar-fill" style={{ width: `${completionPercent}%` }} /></div>
                            </div>

                            {/* Metrics */}
                            <div className="tracker-metrics">
                                <div className="tracker-metric">
                                    <span className="tracker-metric-label">AI Feasibility</span>
                                    <strong className="tracker-metric-value">
                                        {blueprintData ? (completedStageCount === 7 ? '94/100' : `${Math.round(65 + completedStageCount * 4)}/100`) : '—'}
                                    </strong>
                                </div>
                                <div className="tracker-metric">
                                    <span className="tracker-metric-label">Est. Build</span>
                                    <strong className="tracker-metric-value">
                                        {blueprintData?.roadmap?.effort_estimates?.total_duration || (blueprintData ? '4–6 wks' : '—')}
                                    </strong>
                                </div>
                            </div>

                            {/* Stage list */}
                            <div>
                                <span className="drawer-section-label">Stages</span>
                                <div className="stage-list">
                                    {STAGES.map((st) => {
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

                            {/* Business idea context */}
                            {activeProject?.business_idea && (
                                <div>
                                    <span className="drawer-section-label">Business Idea</span>
                                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: '1.55', margin: 0 }}>{activeProject.business_idea}</p>
                                </div>
                            )}

                            {/* Memory & Decisions */}
                            {(projectMemory.length > 0 || projectDecisions.length > 0) && (
                                <div>
                                    <span className="drawer-section-label">🧠 Memory & Decisions</span>
                                    {projectDecisions.length > 0 && (
                                        <div style={{ marginBottom: '10px' }}>
                                            <span style={{ fontSize: '0.6875rem', color: 'var(--text-light)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '6px' }}>Active Decisions</span>
                                            {projectDecisions.map((d) => (
                                                <div key={d.id} style={{ fontSize: '0.8rem', color: d.status === 'accepted' ? 'var(--text)' : 'var(--text-light)', textDecoration: d.status === 'superseded' ? 'line-through' : 'none', marginBottom: '4px' }}>
                                                    {d.status === 'accepted' ? '✅' : '📜'} <strong>[{d.category.toUpperCase()}]</strong> {d.decision}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {projectMemory.length > 0 && (
                                        <div>
                                            <span style={{ fontSize: '0.6875rem', color: 'var(--text-light)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '6px' }}>Extracted Facts</span>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                                {projectMemory.map((m) => (
                                                    <span key={m.id} style={{ background: '#1f1f1f', border: '1px solid var(--border)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                        <strong>{m.key.replace('_', ' ')}:</strong> {m.value}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {!blueprintData && (
                                <p style={{ fontSize: '0.8125rem', color: 'var(--text-light)', textAlign: 'center' }}>
                                    No blueprint yet. Say "Generate everything" to build the 7-stage solution.
                                </p>
                            )}
                        </div>
                    </div>
                </>
            )}

            {/* ── KNOWLEDGE DRAWER ── */}
            {showKnowledge && activeProject && (
                <>
                    <div className="drawer-overlay" onClick={() => setShowKnowledge(false)} />
                    <div className="drawer">
                        <div className="drawer-header">
                            <span className="drawer-title">PROJECT KNOWLEDGE</span>
                            <button className="drawer-close" onClick={() => setShowKnowledge(false)}>✕</button>
                        </div>
                        <div className="drawer-body">
                            {/* Upload document */}
                            <div>
                                <span className="drawer-section-label">Upload Document</span>
                                <label className="panel-upload-btn">
                                    {uploading ? '⏳ Processing...' : '📁 PDF / DOCX / PPTX / TXT / CSV'}
                                    <input type="file" accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.csv" onChange={handleUploadKnowledgeDocument} style={{ display: 'none' }} disabled={uploading || !activeProject?.id} />
                                </label>
                            </div>

                            {/* Add website */}
                            <div>
                                <span className="drawer-section-label">Add Website URL</span>
                                <form onSubmit={handleAddWebsiteKnowledge} style={{ display: 'flex', gap: '6px' }}>
                                    <input type="url" placeholder="https://example.com" value={websiteUrlInput} onChange={(e) => setWebsiteUrlInput(e.target.value)} disabled={addingWebsite || !activeProject?.id} className="drawer-input" style={{ flex: 1 }} />
                                    <button type="submit" disabled={addingWebsite || !websiteUrlInput.trim() || !activeProject?.id} className="btn btn-primary" style={{ flexShrink: 0, padding: '6px 12px', fontSize: '0.8125rem' }}>
                                        {addingWebsite ? '⏳' : 'Add'}
                                    </button>
                                </form>
                            </div>

                            {/* Source list */}
                            <div>
                                <span className="drawer-section-label">Sources ({knowledgeSources.length})</span>
                                {knowledgeSources.length === 0 ? (
                                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-light)', margin: 0 }}>No knowledge sources yet.</p>
                                ) : (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                        {knowledgeSources.map((src) => (
                                            <div key={src.id} className="source-item">
                                                <div style={{ flex: 1, minWidth: 0 }}>
                                                    <span className="source-item-name">{src.type === 'WEBSITE' ? '🌐' : '📄'} {src.name}</span>
                                                    <span className="source-item-meta" style={{ color: src.status === 'READY' ? '#a3e4d7' : src.status === 'FAILED' ? '#fca5a5' : '#fbbf24' }}>
                                                        {src.status} · {src.chunk_count} chunks
                                                    </span>
                                                    {src.status === 'FAILED' && src.extracted_text_snippet && (
                                                        <span style={{ fontSize: '0.6875rem', color: '#fca5a5', display: 'block' }}>{src.extracted_text_snippet}</span>
                                                    )}
                                                </div>
                                                <div className="source-item-actions">
                                                    {src.type === 'WEBSITE' && src.status === 'READY' && (
                                                        <button onClick={() => handleRefreshWebsiteKnowledge(src.id)} className="source-action-btn" title="Refresh">🔄</button>
                                                    )}
                                                    <button onClick={() => handleDeleteKnowledgeSource(src.id)} className="source-action-btn" title="Delete" style={{ color: '#fca5a5' }}>🗑️</button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}

            {/* ── HUMAN HANDOFF DRAWER ── */}
            {showHelpDrawer && activeProject && (
                <>
                    <div className="drawer-overlay" onClick={() => setShowHelpDrawer(false)} />
                    <div className="drawer">
                        <div className="drawer-header">
                            <span className="drawer-title">REQUEST HUMAN HELP</span>
                            <button className="drawer-close" onClick={() => setShowHelpDrawer(false)}>✕</button>
                        </div>
                        <div className="drawer-body">
                            <form onSubmit={handleSubmitHandoff} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                <div>
                                    <span className="drawer-section-label">Subject</span>
                                    <input type="text" placeholder="Brief subject..." value={handoffForm.subject} onChange={(e) => setHandoffForm((f) => ({ ...f, subject: e.target.value }))} maxLength={255} className="drawer-input" />
                                </div>
                                <div>
                                    <span className="drawer-section-label">Description</span>
                                    <textarea placeholder="Describe what you need human help with..." value={handoffForm.description} onChange={(e) => setHandoffForm((f) => ({ ...f, description: e.target.value }))} rows={4} maxLength={2000} className="drawer-input" style={{ resize: 'vertical' }} />
                                </div>
                                <div>
                                    <span className="drawer-section-label">Priority</span>
                                    <select value={handoffForm.priority} onChange={(e) => setHandoffForm((f) => ({ ...f, priority: e.target.value }))} className="drawer-input">
                                        <option value="low">Low</option>
                                        <option value="normal">Normal</option>
                                        <option value="high">High</option>
                                    </select>
                                </div>
                                {handoffError && <span style={{ fontSize: '0.8125rem', color: '#fca5a5' }}>{handoffError}</span>}
                                <button type="submit" disabled={handoffSubmitting || !handoffForm.subject.trim() || !handoffForm.description.trim()} className="btn btn-primary" style={{ justifyContent: 'center' }}>
                                    {handoffSubmitting ? 'Submitting...' : '📨 Submit Request'}
                                </button>
                            </form>

                            {handoffList.length > 0 && (
                                <div>
                                    <span className="drawer-section-label">Your Requests</span>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                        {handoffList.map((h) => (
                                            <div key={h.id} className="handoff-item">
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                                                    <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>{h.subject}</span>
                                                    <span className="handoff-status-badge" style={{
                                                        background: h.status === 'OPEN' ? '#2a1f00' : h.status === 'IN_PROGRESS' ? '#0a1f3a' : h.status === 'RESOLVED' ? '#0a2a1a' : '#1f1f1f',
                                                        color: h.status === 'OPEN' ? '#fbbf24' : h.status === 'IN_PROGRESS' ? '#93c5fd' : h.status === 'RESOLVED' ? '#a3e4d7' : 'var(--text-muted)',
                                                    }}>{h.status}</span>
                                                </div>
                                                <span style={{ fontSize: '0.6875rem', color: 'var(--text-light)' }}>{h.priority} · {new Date(h.created_at).toLocaleDateString()}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
