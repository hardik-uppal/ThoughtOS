import React, { useState } from 'react';
import axios from 'axios';
import { Save } from 'lucide-react';

interface FormWidgetProps {
    data: {
        title: string;
        fields: Array<{
            name: string;
            label: string;
            type: string;
            placeholder: string;
        }>;
    };
    contextId: string;
    contextType: string;
}

const FormWidget: React.FC<FormWidgetProps> = ({ data, contextId, contextType }) => {
    const [formData, setFormData] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);

    const handleChange = (name: string, value: string) => {
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            await axios.post('/api/context/submit', {
                contextId,
                contextType,
                formData
            });
            alert('✅ Saved successfully!');
            setFormData({});
        } catch (e) {
            alert('❌ Failed to save');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div style={{
            margin: '16px 0',
            padding: '20px',
            background: '#f9f9f9',
            borderRadius: '12px',
            border: '1px solid #e0e0e0'
        }}>
            <h3 style={{ marginTop: 0, marginBottom: '16px' }}>{data.title}</h3>

            {data.fields.map((field) => (
                <div key={field.name} style={{ marginBottom: '16px' }}>
                    <label style={{
                        display: 'block',
                        marginBottom: '6px',
                        fontWeight: '600',
                        fontSize: '14px'
                    }}>
                        {field.label}
                    </label>

                    {field.type === 'textarea' ? (
                        <textarea
                            value={formData[field.name] || ''}
                            onChange={(e) => handleChange(field.name, e.target.value)}
                            placeholder={field.placeholder}
                            style={{
                                width: '100%',
                                minHeight: '80px',
                                padding: '10px',
                                border: '1px solid #ddd',
                                borderRadius: '6px',
                                fontSize: '14px',
                                fontFamily: 'inherit',
                                resize: 'vertical'
                            }}
                        />
                    ) : (
                        <input
                            type="text"
                            value={formData[field.name] || ''}
                            onChange={(e) => handleChange(field.name, e.target.value)}
                            placeholder={field.placeholder}
                            style={{
                                width: '100%',
                                padding: '10px',
                                border: '1px solid #ddd',
                                borderRadius: '6px',
                                fontSize: '14px'
                            }}
                        />
                    )}
                </div>
            ))}

            <button
                onClick={handleSubmit}
                disabled={submitting}
                style={{
                    width: '100%',
                    padding: '12px 20px',
                    background: 'var(--bg-color)',
                    color: 'var(--text-color)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '0',
                    fontWeight: '700',
                    fontSize: '14px',
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    opacity: submitting ? 0.6 : 1,
                    textTransform: 'uppercase',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    fontFamily: 'inherit',
                    transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                    if (!submitting) {
                        e.currentTarget.style.backgroundColor = 'var(--hover-bg)';
                        e.currentTarget.style.color = 'var(--hover-text)';
                    }
                }}
                onMouseLeave={(e) => {
                    if (!submitting) {
                        e.currentTarget.style.backgroundColor = 'var(--bg-color)';
                        e.currentTarget.style.color = 'var(--text-color)';
                    }
                }}
            >
                <Save size={16} />
                {submitting ? 'SAVING...' : 'SAVE ENTRY'}
            </button>
        </div>
    );
};

export default FormWidget;
