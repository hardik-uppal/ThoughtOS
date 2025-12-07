import React from 'react';
import FormWidget from './FormWidget';
import ChartWidget from './ChartWidget';
import ListWidget from './ListWidget';
import StatWidget from './StatWidget';
import TagSelector from './TagSelector';

interface WidgetRendererProps {
    type: string;
    data: any;
}

const WidgetRenderer: React.FC<WidgetRendererProps> = ({ type, data }) => {
    if (!data) return null;

    switch (type) {
        case 'action_backfill':
            return null;

        case 'form':
            return <FormWidget data={data} contextId={data.context_id} contextType={data.context_type} />;

        case 'tag_selector':
            return <TagSelector data={data} />;

        case 'bar_chart':
        case 'line_chart':
            return <ChartWidget data={data} />;

        case 'transaction_list':
            return <ListWidget data={data} />;

        case 'stat_card':
            return <StatWidget data={data} />;

        default:
            // Fallback for unknown widgets or legacy types
            return (
                <div style={{
                    padding: '12px',
                    background: '#f5f5f5',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#666'
                }}>
                    Unknown Widget: {type}
                    <pre>{JSON.stringify(data, null, 2)}</pre>
                </div>
            );
    }
};

export default WidgetRenderer;
