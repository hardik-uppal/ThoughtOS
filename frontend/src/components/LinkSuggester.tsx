import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface LinkSuggesterProps {
    content: string;
    onConfirm: (links: string[]) => void;
    onCancel: () => void;
}

interface Suggestion {
    id: string;
    name: string;
    type: string;
    similarity: number;
}

const LinkSuggester: React.FC<LinkSuggesterProps> = ({ content, onConfirm, onCancel }) => {
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSuggestions = async () => {
            try {
                // Fetch suggestions from backend based on content
                const res = await axios.post('/api/graph/analyze', { text: content });
                setSuggestions(res.data.suggestions || []);
                // Auto-select high confidence ones? Maybe not, let user choose.
            } catch (e) {
                console.error("Failed to fetch suggestions", e);
            } finally {
                setLoading(false);
            }
        };
        fetchSuggestions();
    }, [content]);

    const toggleSelection = (id: string) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
    };

    const handleConfirm = () => {
        onConfirm(Array.from(selectedIds));
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
                background: 'white',
                padding: '24px',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '500px',
                maxHeight: '80vh',
                display: 'flex',
                flexDirection: 'column'
            }}>
                <h3 style={{ margin: '0 0 16px 0' }}>Link to Context</h3>
                <p style={{ margin: '0 0 16px 0', fontSize: '14px', color: '#666' }}>
                    Select existing topics to link this thought to:
                </p>

                {loading ? (
                    <div style={{ padding: '20px', textAlign: 'center' }}>Analyzing...</div>
                ) : (
                    <div style={{ flex: 1, overflowY: 'auto', minHeight: '200px' }}>
                        {suggestions.length === 0 ? (
                            <div style={{ textAlign: 'center', color: '#999' }}>No suggestions found.</div>
                        ) : (
                            suggestions.map(s => (
                                <div
                                    key={s.id}
                                    onClick={() => toggleSelection(s.id)}
                                    style={{
                                        padding: '12px',
                                        border: `1px solid ${selectedIds.has(s.id) ? '#007AFF' : '#eee'}`,
                                        borderRadius: '8px',
                                        marginBottom: '8px',
                                        cursor: 'pointer',
                                        background: selectedIds.has(s.id) ? '#f0f9ff' : 'white',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center'
                                    }}
                                >
                                    <div>
                                        <div style={{ fontWeight: '500' }}>{s.name}</div>
                                        <div style={{ fontSize: '12px', color: '#666' }}>{s.type} • {(s.similarity * 100).toFixed(0)}% Match</div>
                                    </div>
                                    {selectedIds.has(s.id) && <span style={{ color: '#007AFF' }}>✓</span>}
                                </div>
                            ))
                        )}
                    </div>
                )}

                <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
                    <button
                        onClick={onCancel}
                        style={{
                            flex: 1,
                            padding: '12px',
                            border: '1px solid #ddd',
                            background: 'white',
                            borderRadius: '8px',
                            cursor: 'pointer'
                        }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConfirm}
                        style={{
                            flex: 1,
                            padding: '12px',
                            border: 'none',
                            background: '#007AFF',
                            color: 'white',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontWeight: '600'
                        }}
                    >
                        Save & Link ({selectedIds.size})
                    </button>
                </div>
            </div>
        </div>
    );
};

export default LinkSuggester;
