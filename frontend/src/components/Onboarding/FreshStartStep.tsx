import React, { useState } from 'react';
import axios from 'axios';

interface FreshStartStepProps {
    onComplete: () => void;
}

const FreshStartStep: React.FC<FreshStartStepProps> = ({ onComplete }) => {
    const [task, setTask] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async () => {
        if (!task.trim()) return;
        setSubmitting(true);
        try {
            // Send as a chat message to create the task
            await axios.post('/api/chat', { message: `Task: ${task}` });
            onComplete();
        } catch (e) {
            console.error("Failed to create task", e);
            setSubmitting(false);
        }
    };

    return (
        <div>
            <h2 style={{ fontSize: '28px', marginBottom: '12px' }}>Fresh Start.</h2>
            <p style={{ color: '#666', marginBottom: '32px', lineHeight: '1.5' }}>
                Let's prime your brain. What is the <strong>one thing</strong> you absolutely must do tomorrow?
            </p>

            <div style={{ marginBottom: '32px' }}>
                <input
                    type="text"
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    placeholder="e.g. Finish the Q4 report..."
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                    style={{
                        width: '100%',
                        padding: '20px',
                        fontSize: '20px',
                        border: '2px solid #eee',
                        borderRadius: '16px',
                        outline: 'none',
                        transition: 'border-color 0.2s'
                    }}
                    onFocus={(e) => e.target.style.borderColor = '#007AFF'}
                    onBlur={(e) => e.target.style.borderColor = '#eee'}
                />
            </div>

            <button
                onClick={handleSubmit}
                disabled={!task.trim() || submitting}
                style={{
                    width: '100%',
                    padding: '16px',
                    background: '#007AFF',
                    color: 'white',
                    border: 'none',
                    borderRadius: '12px',
                    fontSize: '16px',
                    fontWeight: '600',
                    cursor: (!task.trim() || submitting) ? 'not-allowed' : 'pointer',
                    opacity: (!task.trim() || submitting) ? 0.6 : 1
                }}
            >
                {submitting ? 'Setting up your OS...' : 'Finish Setup'}
            </button>
        </div>
    );
};

export default FreshStartStep;
