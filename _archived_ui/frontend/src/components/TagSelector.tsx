import React, { useState } from 'react';
import axios from 'axios';

interface TagSelectorProps {
    data: {
        txn_id: string;
        merchant: string;
        amount: number;
        options: string[];
    };
}

const TagSelector: React.FC<TagSelectorProps> = ({ data }) => {
    const [selectedTag, setSelectedTag] = useState<string | null>(null);
    const [customTag, setCustomTag] = useState('');
    const [loading, setLoading] = useState(false);
    const [showRulePrompt, setShowRulePrompt] = useState(false);

    const handleTagClick = async (tag: string) => {
        // If "Other" is clicked, show input
        if (tag === 'Other') {
            setSelectedTag('Other');
            return;
        }

        // For other tags, apply immediately
        await applyTag(tag);
    };

    const handleCustomTagSubmit = async () => {
        if (!customTag.trim()) {
            alert('Please enter a category name');
            return;
        }
        await applyTag(customTag);
    };

    const applyTag = async (tag: string) => {
        setSelectedTag(tag);
        setLoading(true);

        try {
            // Apply the tag
            const res = await axios.post('/api/curator/apply', {
                txn_id: data.txn_id,
                tag: tag
            });

            // Check if we should create a rule
            if (res.data.suggest_rule) {
                setShowRulePrompt(true);
            } else {
                // Refresh the page to get next question
                window.location.reload();
            }
        } catch (error) {
            console.error('Failed to apply tag', error);
            alert('Failed to apply tag');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateRule = async (create: boolean) => {
        const finalTag = selectedTag === 'Other' ? customTag : selectedTag;

        if (create && finalTag) {
            try {
                await axios.post('/api/onboarding/rules', {
                    merchant: data.merchant,
                    category: finalTag
                });
                alert(`Rule created: All "${data.merchant}" transactions will be tagged as "${finalTag}"`);
            } catch (error) {
                console.error('Failed to create rule', error);
            }
        }
        // Refresh to get next question
        window.location.reload();
    };

    if (showRulePrompt && selectedTag) {
        const finalTag = selectedTag === 'Other' ? customTag : selectedTag;
        return (
            <div style={{
                padding: '16px',
                background: '#f0f9ff',
                border: '1px solid #0ea5e9',
                borderRadius: '8px',
                marginTop: '12px'
            }}>
                <p style={{ margin: '0 0 12px 0', fontWeight: 'bold' }}>
                    💡 Create a rule?
                </p>
                <p style={{ margin: '0 0 16px 0', fontSize: '14px' }}>
                    Should I automatically tag all "{data.merchant}" transactions as "{finalTag}" going forward?
                </p>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                        onClick={() => handleCreateRule(true)}
                        style={{
                            padding: '8px 16px',
                            background: '#0ea5e9',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                        }}
                    >
                        Yes, Create Rule
                    </button>
                    <button
                        onClick={() => handleCreateRule(false)}
                        style={{
                            padding: '8px 16px',
                            background: '#e5e7eb',
                            color: '#374151',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer'
                        }}
                    >
                        No, Just This One
                    </button>
                </div>
            </div>
        );
    }

    // Show custom input if "Other" is selected
    if (selectedTag === 'Other') {
        return (
            <div style={{
                marginTop: '12px',
                padding: '16px',
                background: '#f9fafb',
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
            }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', fontSize: '14px' }}>
                    Enter custom category:
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                        type="text"
                        value={customTag}
                        onChange={(e) => setCustomTag(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleCustomTagSubmit()}
                        placeholder="e.g., Insurance, Utilities, etc."
                        autoFocus
                        style={{
                            flex: 1,
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            fontSize: '14px'
                        }}
                    />
                    <button
                        onClick={handleCustomTagSubmit}
                        disabled={loading || !customTag.trim()}
                        style={{
                            padding: '10px 20px',
                            background: '#0ea5e9',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: loading || !customTag.trim() ? 'not-allowed' : 'pointer',
                            fontWeight: 'bold',
                            opacity: loading || !customTag.trim() ? 0.5 : 1
                        }}
                    >
                        {loading ? 'Applying...' : 'Apply'}
                    </button>
                </div>
                <button
                    onClick={() => setSelectedTag(null)}
                    style={{
                        marginTop: '8px',
                        padding: '6px 12px',
                        background: 'transparent',
                        color: '#6b7280',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '12px',
                        textDecoration: 'underline'
                    }}
                >
                    ← Back to options
                </button>
            </div>
        );
    }

    return (
        <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
            marginTop: '12px'
        }}>
            {data.options.map((option) => (
                <button
                    key={option}
                    onClick={() => handleTagClick(option)}
                    disabled={loading}
                    style={{
                        padding: '10px 20px',
                        background: selectedTag === option ? '#0ea5e9' : '#f0f0f0',
                        color: selectedTag === option ? 'white' : '#374151',
                        border: '1px solid',
                        borderColor: selectedTag === option ? '#0ea5e9' : '#ddd',
                        borderRadius: '20px',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                        fontWeight: selectedTag === option ? 'bold' : 'normal',
                        transition: 'all 0.2s'
                    }}
                >
                    {option}
                </button>
            ))}
        </div>
    );
};

export default TagSelector;

