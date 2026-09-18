import React, { useState } from 'react';
import { api } from '../api/client';

export const BusinessInputForm = ({ activeProject, onBlueprintGenerated }) => {
    const [businessIdea, setBusinessIdea] = useState(activeProject?.business_idea || '');
    const [uploading, setUploading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');
    const [error, setError] = useState('');

    const handleDocumentUpload = async (e) => {
        const file = e.target.files[0];
        if (!file || !activeProject) return;

        setUploading(true);
        setUploadMessage('');
        setError('');

        try {
            const updatedProject = await api.uploadDocument(activeProject.id, file);
            setUploadMessage(`Successfully extracted text from document: "${file.name}"`);
            if (updatedProject.business_idea) {
                setBusinessIdea(updatedProject.business_idea);
            }
        } catch (err) {
            setError(err.message || 'Document upload failed.');
        } finally {
            setUploading(false);
        }
    };

    const handleGenerate = async (e) => {
        e.preventDefault();
        if (!activeProject) {
            setError('Please create or select a project first.');
            return;
        }
        if (!businessIdea.trim()) {
            setError('Please enter a business idea or upload a document context.');
            return;
        }

        setGenerating(true);
        setError('');

        try {
            const blueprint = await api.generateBlueprint(activeProject.id, businessIdea);
            if (onBlueprintGenerated) {
                onBlueprintGenerated(blueprint);
            }
        } catch (err) {
            setError(err.message || 'Pipeline generation failed.');
        } finally {
            setGenerating(false);
        }
    };

    if (!activeProject) {
        return (
            <div className="glass-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                👈 Please create or select a project from the top bar to begin.
            </div>
        );
    }

    return (
        <div className="glass-card" style={{ padding: '28px', marginBottom: '32px' }}>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '6px' }}>
                Business Context & AI Blueprint Generator
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '20px' }}>
                Enter a raw business idea, problem statement, or upload a document (PDF, DOCX, PPTX).
            </p>

            {error && (
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#fca5a5', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '16px' }}>
                    ⚠️ {error}
                </div>
            )}

            {uploadMessage && (
                <div style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#6ee7b7', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '16px' }}>
                    ✅ {uploadMessage}
                </div>
            )}

            <form onSubmit={handleGenerate}>
                <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: '500' }}>
                        Business Idea / Problem Statement:
                    </label>
                    <textarea
                        className="form-input"
                        rows={4}
                        placeholder="e.g., Hospital appointment booking is handled manually via phone calls."
                        value={businessIdea}
                        onChange={(e) => setBusinessIdea(e.target.value)}
                    />
                </div>

                {/* Document Upload Input */}
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px', background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '12px', border: '1px dashed var(--border-color)', marginBottom: '20px' }}>
                    <div>
                        <span style={{ fontSize: '0.85rem', fontWeight: '600', color: '#a5b4fc', display: 'block' }}>
                            📁 Document Intelligence Upload (PDF, DOCX, PPTX)
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            Automatically extract text and append to business context.
                        </span>
                    </div>

                    <label className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem', cursor: 'pointer' }}>
                        {uploading ? 'Extracting Text...' : 'Choose File'}
                        <input
                            type="file"
                            accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md"
                            onChange={handleDocumentUpload}
                            style={{ display: 'none' }}
                            disabled={uploading}
                        />
                    </label>
                </div>

                {/* Action Button */}
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                        type="submit"
                        className="btn-primary"
                        style={{ padding: '12px 28px', fontSize: '1rem' }}
                        disabled={generating}
                    >
                        {generating ? '✨ Generating 7-Stage AI Blueprint...' : '🚀 Transform & Generate Solution Blueprint'}
                    </button>
                </div>
            </form>
        </div>
    );
};
