import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface ContextData {
    energy_level: string;
    events: any[];
    tasks: any[];
}

interface SidebarProps {
    onContextSelect: (item: any, type: 'event' | 'task') => void;
    activeContext: any;
}

const Sidebar: React.FC<SidebarProps> = ({ onContextSelect, activeContext }) => {
    const [data, setData] = useState<ContextData | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await axios.get('/api/context');
                setData(res.data);
            } catch (e) {
                console.error("Failed to fetch context", e);
            }
        };
        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, []);

    if (!data) return <div style={{ padding: 20 }}>Loading Context...</div>;

    const energyColor = data.energy_level === 'HIGH' ? '#34C759' : data.energy_level === 'MEDIUM' ? '#FF9500' : '#FF3B30';

    const isActiveContext = (item: any, type: string) => {
        return activeContext && activeContext.id === item.id && activeContext.type === type;
    };

    return (
        <div style={{
            width: '250px',
            borderRight: '1px solid #eee',
            padding: '20px',
            background: '#f9f9f9',
            height: '100%',
            overflowY: 'auto'
        }}>
            <h3>Context Rail</h3>

            {/* Energy Badge */}
            <div style={{
                padding: '12px',
                background: 'white',
                borderRadius: '12px',
                marginBottom: '20px',
                border: '1px solid #e0e0e0',
                textAlign: 'center'
            }}>
                <div style={{ fontSize: '12px', color: '#666' }}>ENERGY LEVEL</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: energyColor }}>
                    {data.energy_level}
                </div>
            </div>

            {/* Events */}
            <div style={{ marginBottom: '20px' }}>
                <h4>📅 Upcoming</h4>
                {data.events.length === 0 ? (
                    <div style={{ fontSize: '14px', color: '#999' }}>No events</div>
                ) : (
                    data.events.map((e: any, idx: number) => {
                        const formatDateTime = (isoString: string) => {
                            if (!isoString) return 'All Day';
                            const date = new Date(isoString);
                            const today = new Date();
                            const tomorrow = new Date(today);
                            tomorrow.setDate(tomorrow.getDate() + 1);

                            let dateStr = '';
                            if (date.toDateString() === today.toDateString()) {
                                dateStr = 'Today';
                            } else if (date.toDateString() === tomorrow.toDateString()) {
                                dateStr = 'Tomorrow';
                            } else {
                                dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            }

                            const timeStr = isoString.includes('T') ? isoString.split('T')[1].slice(0, 5) : '';
                            return timeStr ? `${dateStr} ${timeStr}` : dateStr;
                        };

                        const isActive = isActiveContext(e, 'event');

                        return (
                            <div
                                key={idx}
                                onClick={() => onContextSelect(e, 'event')}
                                style={{
                                    marginBottom: '8px',
                                    fontSize: '13px',
                                    padding: '8px',
                                    background: isActive ? '#007AFF' : 'white',
                                    color: isActive ? 'white' : 'inherit',
                                    borderRadius: '6px',
                                    border: isActive ? '2px solid #007AFF' : '1px solid #eee',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                                onMouseEnter={(el) => !isActive && (el.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)')}
                                onMouseLeave={(el) => !isActive && (el.currentTarget.style.boxShadow = 'none')}
                            >
                                <div style={{ fontWeight: 'bold', color: isActive ? 'white' : '#666', fontSize: '11px', marginBottom: '4px' }}>
                                    {formatDateTime(e.start_iso)}
                                </div>
                                <div>{e.summary}</div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Tasks */}
            <div>
                <h4>✅ Smart Tasks</h4>
                {data.tasks.length === 0 ? (
                    <div style={{ fontSize: '14px', color: '#999' }}>No tasks</div>
                ) : (
                    data.tasks.map((t: any, idx: number) => {
                        const isActive = isActiveContext(t, 'task');

                        return (
                            <div
                                key={idx}
                                onClick={() => onContextSelect(t, 'task')}
                                style={{
                                    marginBottom: '8px',
                                    fontSize: '14px',
                                    padding: '8px',
                                    background: isActive ? '#007AFF' : 'white',
                                    color: isActive ? 'white' : 'inherit',
                                    borderRadius: '6px',
                                    border: isActive ? '2px solid #007AFF' : '1px solid #eee',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                                onMouseEnter={(el) => !isActive && (el.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)')}
                                onMouseLeave={(el) => !isActive && (el.currentTarget.style.boxShadow = 'none')}
                            >
                                {t.content_text}
                            </div>
                        );
                    })
                )}
            </div>

            {/* Tip */}
            <div style={{
                marginTop: '20px',
                padding: '12px',
                background: '#fff3cd',
                borderRadius: '8px',
                fontSize: '12px',
                border: '1px solid #ffc107'
            }}>
                💡 <strong>Tip:</strong> Click an event or task, then type notes in chat to link them!
            </div>

            {/* Sync Button */}
            <div style={{ marginTop: '20px' }}>
                <button
                    onClick={async () => {
                        const btn = document.getElementById('sync-btn');
                        if (btn) {
                            btn.innerText = 'Syncing...';
                            (btn as HTMLButtonElement).disabled = true;
                        }
                        try {
                            await axios.post('/api/sync');
                            alert('Sync & Enrichment Complete!');
                        } catch (e) {
                            alert('Sync failed');
                            console.error(e);
                        } finally {
                            if (btn) {
                                btn.innerText = '🔄 Sync Data';
                                (btn as HTMLButtonElement).disabled = false;
                            }
                        }
                    }}
                    id="sync-btn"
                    style={{
                        width: '100%',
                        padding: '10px',
                        background: '#1C1C1C',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontWeight: 500
                    }}
                >
                    🔄 Sync Data
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
