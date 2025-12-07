import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { usePlaidLink } from 'react-plaid-link';

interface AdminPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isOpen, onClose }) => {
    const [activeTab, setActiveTab] = useState<'logs' | 'curator'>('logs');
    const [logs, setLogs] = useState<any[]>([]);
    const [reviewItems, setReviewItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [linkToken, setLinkToken] = useState<string | null>(null);

    // --- Logs Logic ---
    const fetchLogs = async () => {
        try {
            const res = await axios.get('/api/logs');
            setLogs(res.data);
        } catch (e) {
            console.error(e);
        }
    };

    const clearLogs = async () => {
        if (!confirm("Clear all logs?")) return;
        await axios.post('/api/logs/clear');
        fetchLogs();
    };

    const runAnalysis = async () => {
        setLoading(true);
        try {
            const res = await axios.post('/api/analysis/causal');
            alert(res.data.result);
            fetchLogs();
        } catch (e) {
            alert("Analysis failed");
        } finally {
            setLoading(false);
        }
    };

    // --- Curator Logic ---
    const fetchReviewItems = async () => {
        try {
            const res = await axios.get('/api/curator/review');
            setReviewItems(res.data);
        } catch (e) {
            console.error("Failed to fetch review items", e);
        }
    };

    const runAutoTagger = async () => {
        setLoading(true);
        try {
            const res = await axios.post('/api/curator/auto');
            alert(`Auto-tagged: ${res.data.auto_tagged}, Needs Review: ${res.data.needs_review}`);
            fetchReviewItems();
        } catch (e) {
            alert("Auto-tagger failed");
        } finally {
            setLoading(false);
        }
    };

    const resetEnrichment = async () => {
        if (!confirm("Reset ALL enrichment status? This will re-process everything.")) return;
        setLoading(true);
        try {
            await axios.post('/api/curator/reset');
            alert("Enrichment reset. Running Auto-Tagger...");
            await runAutoTagger();
        } catch (e) {
            alert("Reset failed");
            setLoading(false);
        }
    };

    const applyTag = async (txnId: string, tag: string) => {
        try {
            await axios.post('/api/curator/apply', { txn_id: txnId, tag });
            // Optimistic update
            setReviewItems(prev => prev.filter(item => item.txn_id !== txnId));
        } catch (e) {
            alert("Failed to apply tag");
        }
    };

    // --- Auth Logic ---
    const initPlaidLink = async () => {
        try {
            const res = await axios.get('/api/auth/plaid/link-token');
            setLinkToken(res.data.link_token);
        } catch (e) {
            alert("Failed to initialize Plaid");
        }
    };

    const { open: openPlaidLink, ready: plaidReady } = usePlaidLink({
        token: linkToken,
        onSuccess: async (public_token) => {
            try {
                await axios.post('/api/auth/plaid/exchange', { public_token });
                alert("Plaid Connected Successfully!");
                setLinkToken(null);
            } catch (e) {
                alert("Failed to connect Plaid");
            }
        },
    });

    const handlePlaidAuth = async () => {
        await initPlaidLink();
    };

    useEffect(() => {
        if (linkToken && plaidReady) {
            openPlaidLink();
        }
    }, [linkToken, plaidReady, openPlaidLink]);

    const handleGoogleAuth = async () => {
        try {
            await axios.post('/api/auth/google');
            alert("Google Calendar Connected!");
        } catch (e) {
            alert("Google Calendar auth failed");
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchLogs();
            fetchReviewItems();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const formatTimestamp = (timestamp: string) => {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000
        }}>
            <div style={{
                width: '900px',
                height: '700px',
                background: 'white',
                borderRadius: '12px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 10px 25px rgba(0,0,0,0.2)'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <h2>Admin Console</h2>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer' }}>✕</button>
                </div>

                {/* Tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid #eee', marginBottom: '20px' }}>
                    <button
                        onClick={() => setActiveTab('logs')}
                        style={{
                            padding: '10px 20px',
                            background: 'none',
                            border: 'none',
                            borderBottom: activeTab === 'logs' ? '2px solid #007AFF' : 'none',
                            color: activeTab === 'logs' ? '#007AFF' : '#666',
                            fontWeight: activeTab === 'logs' ? 'bold' : 'normal',
                            cursor: 'pointer'
                        }}
                    >
                        System Logs
                    </button>
                    <button
                        onClick={() => setActiveTab('curator')}
                        style={{
                            padding: '10px 20px',
                            background: 'none',
                            border: 'none',
                            borderBottom: activeTab === 'curator' ? '2px solid #007AFF' : 'none',
                            color: activeTab === 'curator' ? '#007AFF' : '#666',
                            fontWeight: activeTab === 'curator' ? 'bold' : 'normal',
                            cursor: 'pointer'
                        }}
                    >
                        Curator (Review Queue)
                    </button>
                </div>

                {activeTab === 'logs' ? (
                    <>
                        {/* Auth Section */}
                        <div style={{ marginBottom: '20px', padding: '16px', background: '#f9f9f9', borderRadius: '8px' }}>
                            <h3 style={{ marginTop: 0 }}>🔐 Authentication</h3>
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button onClick={handlePlaidAuth} style={{ background: '#007AFF', color: 'white', border: 'none', padding: '10px 16px', borderRadius: '6px', cursor: 'pointer' }}>
                                    🏦 Connect Plaid
                                </button>
                                <button onClick={handleGoogleAuth} style={{ background: '#34C759', color: 'white', border: 'none', padding: '10px 16px', borderRadius: '6px', cursor: 'pointer' }}>
                                    📅 Connect Google Calendar
                                </button>
                            </div>
                        </div>

                        {/* Actions Section */}
                        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
                            <button onClick={fetchLogs}>🔄 Refresh</button>
                            <button onClick={clearLogs} style={{ background: '#FF3B30', color: 'white' }}>🗑️ Clear Logs</button>
                            <button onClick={runAnalysis} disabled={loading} style={{ background: '#5856D6', color: 'white' }}>
                                {loading ? 'Running...' : '🕵️ Run Causal Analysis'}
                            </button>
                        </div>

                        {/* Logs Table */}
                        <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #eee', borderRadius: '8px' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                                <thead style={{ background: '#f5f5f5', position: 'sticky', top: 0 }}>
                                    <tr>
                                        <th style={{ padding: '8px', textAlign: 'left' }}>Time</th>
                                        <th style={{ padding: '8px', textAlign: 'left' }}>Level</th>
                                        <th style={{ padding: '8px', textAlign: 'left' }}>Component</th>
                                        <th style={{ padding: '8px', textAlign: 'left' }}>Message</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map((log, idx) => (
                                        <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                                            <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>{formatTimestamp(log.timestamp)}</td>
                                            <td style={{ padding: '8px', color: log.level === 'ERROR' ? 'red' : 'black' }}>{log.level}</td>
                                            <td style={{ padding: '8px' }}>{log.component}</td>
                                            <td style={{ padding: '8px' }}>{log.message}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    <>
                        {/* Curator Actions */}
                        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
                            <button onClick={runAutoTagger} disabled={loading} style={{ background: '#007AFF', color: 'white', padding: '10px 16px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                                {loading ? 'Thinking...' : '🤖 Run Auto-Tagger'}
                            </button>
                            <button onClick={resetEnrichment} disabled={loading} style={{ background: '#FF9500', color: 'white', padding: '10px 16px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                                ♻️ Reset All
                            </button>
                            <button onClick={fetchReviewItems} style={{ padding: '10px 16px', border: '1px solid #ccc', borderRadius: '6px', cursor: 'pointer' }}>
                                🔄 Refresh Queue
                            </button>
                        </div>

                        {/* Review Queue */}
                        <div style={{ flex: 1, overflowY: 'auto' }}>
                            {reviewItems.length === 0 ? (
                                <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                                    🎉 All caught up! No items need review.
                                </div>
                            ) : (
                                reviewItems.map((item) => (
                                    <div key={item.txn_id} style={{
                                        border: '1px solid #eee',
                                        borderRadius: '8px',
                                        padding: '16px',
                                        marginBottom: '12px',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center'
                                    }}>
                                        <div>
                                            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{item.merchant_name}</div>
                                            <div style={{ color: '#666', fontSize: '14px' }}>
                                                ${item.amount} • {item.date_posted}
                                            </div>
                                            <div style={{ marginTop: '8px', color: '#007AFF', fontSize: '14px' }}>
                                                🤖 {item.clarification_question}
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            {JSON.parse(item.suggested_tags || '[]').map((tag: string) => (
                                                <button
                                                    key={tag}
                                                    onClick={() => applyTag(item.txn_id, tag)}
                                                    style={{
                                                        padding: '8px 12px',
                                                        background: '#f0f0f0',
                                                        border: '1px solid #ddd',
                                                        borderRadius: '20px',
                                                        cursor: 'pointer',
                                                        fontSize: '13px'
                                                    }}
                                                >
                                                    {tag}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default AdminPanel;
