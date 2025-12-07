import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface ChartWidgetProps {
    data: {
        title: string;
        labels: string[];
        values: number[];
        series_name: string;
    };
}

const ChartWidget: React.FC<ChartWidgetProps> = ({ data }) => {
    const chartData = data.labels.map((label, i) => ({
        name: label,
        value: data.values[i]
    }));

    return (
        <div style={{
            background: 'white',
            padding: '20px',
            borderRadius: '16px',
            border: '1px solid #eee',
            marginTop: '12px',
            width: '100%',
            maxWidth: '500px'
        }}>
            <h4 style={{ margin: '0 0 16px 0', fontSize: '14px', color: '#666', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                {data.title}
            </h4>
            <div style={{ height: '200px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                        <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}`} />
                        <Tooltip
                            cursor={{ fill: '#f5f5f5' }}
                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.value < 0 ? '#FF3B30' : '#007AFF'} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default ChartWidget;
