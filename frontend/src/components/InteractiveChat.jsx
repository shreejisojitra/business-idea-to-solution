import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';

export const InteractiveChat = ({ activeProject }) => {
    const [messages, setMessages] = useState([
        {
            sender: 'ai',
            text: 'Hello! I am your AI Solution Architect. Ask me anything about your project solution, AI capabilities, database schema, or workflow steps!'
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading]);

    const handleSendMessage = async (textToSend) => {
        const query = textToSend || input;
        if (!query.trim() || !activeProject || loading) return;

        const userMsg = { sender: 'user', text: query };
        setMessages((prev) => [...prev, userMsg]);
        if (!textToSend) setInput('');
        setLoading(true);

        try {
            const data = await api.sendChatMessage(activeProject.id, query);
            setMessages((prev) => [...prev, { sender: 'ai', text: data.reply }]);
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                { sender: 'ai', text: `⚠️ Error: ${err.message || 'Failed to get AI response.'}` }
            ]);
        } finally {
            setLoading(false);
        }
    };

    const suggestions = [
        "What AI can I use for this?",
        "What database should I use?",
        "Show me the workflow steps.",
        "What are the key security requirements?"
    ];

    if (!activeProject) {
        return (
            <div className="glass-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                👈 Please select a project first to chat with the AI Architect.
            </div>
        );
    }

    return (
        <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '600px' }}>
            <div style={{ marginBottom: '16px', borderBottom: '1px solid var(--border-color)', pb: '12px' }}>
                <h3 style={{ fontSize: '1.25rem', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    💬 Conversational AI Solution Architect
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    Ask interactive questions about <strong style={{ color: '#a5b4fc' }}>{activeProject.title}</strong>
                </p>
            </div>

            {/* Quick Suggestion Chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
                {suggestions.map((sug, idx) => (
                    <button
                        key={idx}
                        onClick={() => handleSendMessage(sug)}
                        disabled={loading}
                        style={{
                            background: 'rgba(99, 102, 241, 0.12)',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                            color: '#c7d2fe',
                            borderRadius: '20px',
                            padding: '6px 14px',
                            fontSize: '0.8rem',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => (e.target.style.background = 'rgba(99, 102, 241, 0.25)')}
                        onMouseOut={(e) => (e.target.style.background = 'rgba(99, 102, 241, 0.12)')}
                    >
                        💡 {sug}
                    </button>
                ))}
            </div>

            {/* Messages Area */}
            <div style={{
                flex: 1,
                overflowY: 'auto',
                paddingRight: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                marginBottom: '16px'
            }}>
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        style={{
                            alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                            maxWidth: '80%',
                            background: msg.sender === 'user'
                                ? 'linear-gradient(135deg, #6366f1, #4f46e5)'
                                : 'rgba(255, 255, 255, 0.06)',
                            color: '#ffffff',
                            padding: '12px 16px',
                            borderRadius: msg.sender === 'user' ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                            border: msg.sender === 'user' ? 'none' : '1px solid var(--border-color)',
                            whiteSpace: 'pre-wrap',
                            lineHeight: '1.5',
                            fontSize: '0.9rem',
                            boxShadow: msg.sender === 'user' ? '0 4px 14px rgba(99, 102, 241, 0.3)' : 'none'
                        }}
                    >
                        {msg.text}
                    </div>
                ))}

                {loading && (
                    <div style={{
                        alignSelf: 'flex-start',
                        background: 'rgba(255, 255, 255, 0.06)',
                        padding: '12px 16px',
                        borderRadius: '16px 16px 16px 2px',
                        fontSize: '0.85rem',
                        color: 'var(--text-muted)'
                    }}>
                        🧠 Thinking & analyzing blueprint context...
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Form */}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage();
                }}
                style={{ display: 'flex', gap: '10px' }}
            >
                <input
                    type="text"
                    className="form-input"
                    placeholder="Ask a question (e.g. What database should I use?)..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={loading}
                    style={{ flex: 1 }}
                />
                <button
                    type="submit"
                    className="btn-primary"
                    disabled={loading || !input.trim()}
                    style={{ padding: '10px 24px' }}
                >
                    Send
                </button>
            </form>
        </div>
    );
};
