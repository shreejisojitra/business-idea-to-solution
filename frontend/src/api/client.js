const API_BASE_URL = '/api';

export const getAuthToken = () => localStorage.getItem('token');
export const setAuthToken = (token) => localStorage.setItem('token', token);
export const removeAuthToken = () => localStorage.removeItem('token');

/**
 * Strip any detail that looks like a credential, stack trace, or internal path
 * before showing it to the user.
 */
const sanitiseError = (msg) => {
    if (!msg || typeof msg !== 'string') return 'An unexpected error occurred.';
    // Block anything that looks like a secret, stack trace, or DB URL
    const blocked = [
        /secret/i, /password/i, /api[_-]?key/i, /token/i,
        /traceback/i, /file ".*\.py"/i, /sqlalchemy/i,
        /postgresql:\/\//i, /sqlite:\/\//i,
    ];
    if (blocked.some((re) => re.test(msg))) return 'An error occurred. Please try again.';
    // Truncate very long messages (stack traces can be huge)
    return msg.length > 200 ? msg.slice(0, 200) + '…' : msg;
};

const request = async (endpoint, options = {}) => {
    const token = getAuthToken();
    const headers = { ...options.headers };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    let response;
    try {
        response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers });
    } catch {
        throw new Error('Network error. Please check your connection.');
    }

    if (response.status === 401) {
        removeAuthToken();
        window.location.reload();
        return; // prevent further processing after reload
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        if (!response.ok) {
            throw new Error(sanitiseError(data.detail || 'Request failed.'));
        }
        return data;
    } else {
        const text = await response.text();
        if (!response.ok) {
            throw new Error(sanitiseError(text || 'Request failed.'));
        }
        return text;
    }
};

export const api = {
    // Auth
    register: (email, password, fullName) =>
        request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, password, full_name: fullName }),
        }),

    login: (username, password) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        return fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        }).then(async (res) => {
            const data = await res.json();
            if (!res.ok) throw new Error(sanitiseError(data.detail || 'Login failed.'));
            return data;
        });
    },

    getMe: () => request('/auth/me'),

    // Workspaces
    listWorkspaces: () => request('/workspaces/'),
    createWorkspace: (name) =>
        request('/workspaces/', {
            method: 'POST',
            body: JSON.stringify({ name }),
        }),

    // Projects
    listProjects: (workspaceId) =>
        request(`/projects/?workspace_id=${workspaceId || ''}`),
    createProject: (name, workspaceId, businessIdea) =>
        request('/projects/', {
            method: 'POST',
            body: JSON.stringify({ name, workspace_id: workspaceId, business_idea: businessIdea }),
        }),
    getProject: (projectId) => request(`/projects/${projectId}`),
    updateProject: (projectId, data) =>
        request(`/projects/${projectId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        }),
    uploadDocument: (projectId, file) => {
        const formData = new FormData();
        formData.append('file', file);
        return request(`/projects/${projectId}/documents`, {
            method: 'POST',
            body: formData,
        });
    },

    // AI Pipeline
    generateBlueprint: (projectId, businessIdea) =>
        request(`/projects/${projectId}/generate`, {
            method: 'POST',
            body: JSON.stringify({ business_idea: businessIdea }),
        }),
    getBlueprint: (projectId) => request(`/projects/${projectId}/blueprint`),
    updateBlueprintStage: (projectId, stageName, data) =>
        request(`/projects/${projectId}/blueprint/stages/${stageName}`, {
            method: 'PUT',
            body: JSON.stringify({ data }),
        }),
    regenerateStage: (projectId, stageName) =>
        request(`/projects/${projectId}/regenerate/${stageName}`, {
            method: 'POST',
        }),

    // Export — authenticated download (token required)
    exportProject: async (projectId, format, filename) => {
        const token = getAuthToken();
        let response;
        try {
            response = await fetch(`${API_BASE_URL}/projects/${projectId}/export?format=${format}`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
        } catch {
            throw new Error('Network error during export.');
        }
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Export failed.' }));
            throw new Error(sanitiseError(err.detail || 'Export failed.'));
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    // AI Chat Consultant
    listConversations: (projectId) =>
        request(`/ai/conversations?project_id=${projectId}`),
    getConversationMessages: (conversationId) =>
        request(`/ai/conversations/${conversationId}/messages`),
    deleteConversation: (conversationId) =>
        request(`/ai/conversations/${conversationId}`, { method: 'DELETE' }),
    sendChatMessage: (projectId, message, conversationId) =>
        request('/ai/chat', {
            method: 'POST',
            body: JSON.stringify({
                project_id: projectId,
                message,
                conversation_id: conversationId || null,
            }),
        }),

    // Project Memory & Decisions
    getProjectMemory: (projectId) => request(`/projects/${projectId}/memory`),
    getProjectDecisions: (projectId) => request(`/projects/${projectId}/decisions`),
    createProjectDecision: (projectId, decision, category = 'architecture', reason = '') =>
        request(`/projects/${projectId}/decisions`, {
            method: 'POST',
            body: JSON.stringify({ decision, category, reason }),
        }),
    deleteProjectDecision: (projectId, decisionId) =>
        request(`/projects/${projectId}/decisions/${decisionId}`, { method: 'DELETE' }),

    // Knowledge Base & RAG
    listKnowledgeSources: (projectId) =>
        request(`/projects/${projectId}/knowledge`),
    uploadKnowledgeDocument: (projectId, file, name = '') => {
        const formData = new FormData();
        formData.append('file', file);
        if (name) formData.append('name', name);
        return request(`/projects/${projectId}/knowledge/upload`, {
            method: 'POST',
            body: formData,
        });
    },
    ingestWebsiteKnowledge: (projectId, url, name = '') =>
        request(`/projects/${projectId}/knowledge/website`, {
            method: 'POST',
            body: JSON.stringify({ url, name }),
        }),
    refreshWebsiteKnowledge: (projectId, sourceId) =>
        request(`/projects/${projectId}/knowledge/${sourceId}/refresh`, {
            method: 'POST',
        }),
    deleteKnowledgeSource: (projectId, sourceId) =>
        request(`/projects/${projectId}/knowledge/${sourceId}`, {
            method: 'DELETE',
        }),

    // Public Chatbot Management (Module 8)
    listChatbots: () => request('/chatbots'),
    createChatbot: (data) => request('/chatbots', { method: 'POST', body: JSON.stringify(data) }),
    getChatbot: (id) => request(`/chatbots/${id}`),
    updateChatbot: (id, data) => request(`/chatbots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    deleteChatbot: (id) => request(`/chatbots/${id}`, { method: 'DELETE' }),
    uploadChatbotKnowledge: (id, file) => {
        const formData = new FormData();
        formData.append('file', file);
        return request(`/chatbots/${id}/knowledge`, { method: 'POST', body: formData });
    },
    clearChatbotKnowledge: (id) => request(`/chatbots/${id}/knowledge`, { method: 'DELETE' }),
    getPublicChatbotConfig: (id) => request(`/public/chatbots/${id}/config`),

    // Analytics (Module 13)
    getProjectAnalytics: (projectId, period = '30d') =>
        request(`/projects/${projectId}/analytics?period=${period}`),
    getChatbotAnalytics: (chatbotId, period = '30d') =>
        request(`/chatbots/${chatbotId}/analytics?period=${period}`),

    // Feedback (Module 14)
    submitFeedback: (projectId, rating, comment = null, messageId = null, conversationId = null) =>
        request(`/projects/${projectId}/feedback`, {
            method: 'POST',
            body: JSON.stringify({ rating, comment, message_id: messageId, conversation_id: conversationId }),
        }),
    getFeedbackSummary: (projectId) =>
        request(`/projects/${projectId}/feedback/summary`),

    // Handoff (Module 15)
    createHandoff: (projectId, subject, description, priority = 'normal', conversationId = null) =>
        request(`/projects/${projectId}/handoffs`, {
            method: 'POST',
            body: JSON.stringify({ subject, description, priority, conversation_id: conversationId }),
        }),
    listHandoffs: (projectId) =>
        request(`/projects/${projectId}/handoffs`),
    updateHandoffStatus: (projectId, handoffId, status) =>
        request(`/projects/${projectId}/handoffs/${handoffId}`, {
            method: 'PATCH',
            body: JSON.stringify({ status }),
        }),
};
