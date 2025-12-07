import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface CalibrationStepProps {
    onNext: () => void;
}

const CalibrationStep: React.FC<CalibrationStepProps> = ({ onNext }) => {
    const [questions, setQuestions] = useState<any[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchQuestions = async () => {
            try {
                const res = await axios.post('/api/onboarding/calibrate/finance');
                setQuestions(res.data.questions);
            } catch (e) {
                console.error("Failed to fetch questions", e);
            } finally {
                setLoading(false);
            }
        };
        fetchQuestions();
    }, []);

    const handleAnswer = async (category: string) => {
        const currentQ = questions[currentIndex];
        try {
            await axios.post('/api/onboarding/rules', {
                merchant: currentQ.merchant,
                category: category
            });

            if (currentIndex < questions.length - 1) {
                setCurrentIndex(i => i + 1);
            } else {
                onNext();
            }
        } catch (e) {
            console.error("Failed to save rule", e);
        }
    };

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '40px', marginBottom: '20px' }}>🤔</div>
                <h3>Analyzing your spending patterns...</h3>
            </div>
        );
    }

    if (questions.length === 0) {
        return (
            <div style={{ textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '40px', marginBottom: '20px' }}>✨</div>
                <h3>Your finances look clean!</h3>
                <p style={{ color: '#666', marginBottom: '32px' }}>
                    I didn't find any ambiguous transactions that need clarification.
                </p>
                <button
                    onClick={onNext}
                    style={{
                        padding: '12px 32px',
                        background: '#007AFF',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        fontSize: '16px',
                        fontWeight: '600',
                        cursor: 'pointer'
                    }}
                >
                    Continue
                </button>
            </div>
        );
    }

    const currentQ = questions[currentIndex];

    return (
        <div>
            <h2 style={{ fontSize: '28px', marginBottom: '12px' }}>Help me learn.</h2>
            <p style={{ color: '#666', marginBottom: '32px', lineHeight: '1.5' }}>
                I found some transactions I'm not sure about. Help me categorize them.
            </p>

            <div style={{
                padding: '32px',
                background: '#f9f9f9',
                borderRadius: '20px',
                textAlign: 'center',
                marginBottom: '32px'
            }}>
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>
                    QUESTION {currentIndex + 1} OF {questions.length}
                </div>
                <h3 style={{ fontSize: '24px', margin: '0 0 12px 0' }}>{currentQ.merchant}</h3>
                <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '24px' }}>
                    ${currentQ.total_spend}
                </div>
                <p style={{ fontSize: '16px', color: '#444', marginBottom: '32px' }}>
                    {currentQ.question}
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
                    {currentQ.options.map((opt: string) => (
                        <button
                            key={opt}
                            onClick={() => handleAnswer(opt)}
                            style={{
                                padding: '16px',
                                background: 'white',
                                border: '1px solid #ddd',
                                borderRadius: '12px',
                                fontSize: '16px',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.borderColor = '#007AFF'}
                            onMouseLeave={(e) => e.currentTarget.style.borderColor = '#ddd'}
                        >
                            {opt}
                        </button>
                    ))}
                </div>

                {/* Custom Input */}
                <div style={{ borderTop: '1px solid #eee', paddingTop: '20px' }}>
                    <p style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>Or type your own:</p>
                    <input
                        type="text"
                        placeholder="e.g. Subscriptions, Hobbies..."
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                handleAnswer(e.currentTarget.value);
                                e.currentTarget.value = '';
                            }
                        }}
                        style={{
                            width: '100%',
                            padding: '12px',
                            borderRadius: '8px',
                            border: '1px solid #ddd',
                            fontSize: '16px',
                            outline: 'none'
                        }}
                    />
                </div>
            </div>

            <div style={{ textAlign: 'center', color: '#999', fontSize: '14px' }}>
                Your answers help automate future categorization.
            </div>
        </div>
    );
};

export default CalibrationStep;
