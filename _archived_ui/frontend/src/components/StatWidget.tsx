import React from 'react';

interface StatWidgetProps {
    data: {
        label: string;
        value: string;
        trend?: string;
    };
}

const StatWidget: React.FC<StatWidgetProps> = ({ data }) => {
    return (
        <div style={{
            background: 'white',
            padding: '20px',
            borderRadius: '16px',
            border: '1px solid #eee',
            marginTop: '12px',
            display: 'inline-flex',
            flexDirection: 'column',
            minWidth: '200px'
        }}>
            <span style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>{data.label}</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '32px', fontWeight: 'bold' }}>{data.value}</span>
                {data.trend && (
                    <span style={{
                        fontSize: '14px',
                        fontWeight: '600',
                        color: data.trend.startsWith('+') ? '#34C759' : '#FF3B30'
                    }}>
                        {data.trend}
                    </span>
                )}
            </div>
        </div>
    );
};

export default StatWidget;
