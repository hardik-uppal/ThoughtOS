import React from 'react';
import {
    BarChart, Bar,
    LineChart, Line,
    PieChart, Pie,
    XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend
} from 'recharts';

interface ChartWidgetProps {
    data: {
        type: 'bar' | 'line' | 'pie';
        title: string;
        labels: string[];
        values: number[];
        series_name: string;
        colors?: string[];
    };
}

const COLORS = ['#007AFF', '#FF3B30', '#FF9500', '#34C759', '#5856D6', '#AF52DE'];

const ChartWidget: React.FC<ChartWidgetProps> = ({ data }) => {
    const chartData = data.labels.map((label, i) => ({
        name: label,
        value: data.values[i]
    }));

    const renderChart = () => {
        switch (data.type) {
            case 'line':
                return (
                    <LineChart data={chartData}>
                        <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip />
                        <Line type="monotone" dataKey="value" stroke="#007AFF" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                );
            case 'pie':
                return (
                    <PieChart>
                        <Pie
                            data={chartData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={50}
                            outerRadius={80}
                            fill="#8884d8"
                            paddingAngle={5}
                            label={(entry) => entry.name}
                        >
                            {chartData.map((_entry, index) => (
                                <Cell key={`cell-${index}`} fill={data.colors?.[index] || COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                    </PieChart>
                );
            case 'bar':
            default:
                return (
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
                );
        }
    };

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
            <div style={{ height: '250px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                    {renderChart()}
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default ChartWidget;
