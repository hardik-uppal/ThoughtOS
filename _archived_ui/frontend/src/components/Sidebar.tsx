import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Sidebar.css';
import { Square, DollarSign, Calendar, Brain } from 'lucide-react';

interface ContextData {
    events: any[];
    tasks: any[];
    recent_activity: any[];
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

    if (!data) return (
        <div className="sidebar" style={{ justifyContent: 'center', alignItems: 'center', opacity: 0.5 }}>
            <div style={{ fontSize: '12px' }}>Updating Context...</div>
        </div>
    );

    const isActiveContext = (item: any, type: string) => {
        return activeContext && activeContext.id === item.id && activeContext.type === type;
    };

    return (
        <div className="sidebar">
            <h3>Context Rail</h3>

            {/* Events */}
            <div className="sidebar-section">
                <h4>Upcoming Events</h4>
                {data.events.length === 0 ? (
                    <div className="sidebar-empty">No upcoming events</div>
                ) : (
                    data.events.map((e: any, idx: number) => {
                        const formatDateTime = (isoString: string) => {
                            if (!isoString) return 'All Day';
                            try {
                                const date = new Date(isoString);
                                if (isNaN(date.getTime())) return 'Invalid Date';

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

                                const timeStr = isoString.includes('T') ? minTime(date) : '';
                                return timeStr ? `${dateStr} @ ${timeStr}` : dateStr;
                            } catch (e) {
                                return 'Invalid Date';
                            }
                        };

                        const minTime = (d: Date) => {
                            return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
                        };

                        const isActive = isActiveContext(e, 'event');

                        return (
                            <div
                                key={idx}
                                onClick={() => onContextSelect(e, 'event')}
                                className={`sidebar-item ${isActive ? 'active' : ''}`}
                            >
                                <div className="sidebar-item-header">
                                    {formatDateTime(e.start_iso)}
                                </div>
                                <div style={{ fontWeight: 500 }}>{e.summary}</div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Tasks */}
            <div className="sidebar-section">
                <h4>Smart Tasks</h4>
                {data.tasks.length === 0 ? (
                    <div className="sidebar-empty">No pending tasks</div>
                ) : (
                    data.tasks.map((t: any, idx: number) => {
                        const isActive = isActiveContext(t, 'task');

                        return (
                            <div
                                key={idx}
                                onClick={() => onContextSelect(t, 'task')}
                                className={`sidebar-item ${isActive ? 'active' : ''}`}
                            >
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                                    <Square size={14} />
                                    <span>{t.content_text}</span>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Recent Activity */}
            <div className="sidebar-section">
                <h4>Log Stream</h4>
                {data.recent_activity.length === 0 ? (
                    <div className="sidebar-empty">No recent activity</div>
                ) : (
                    data.recent_activity.map((item: any, idx: number) => {
                        const icon = item.type === 'transaction' ? <DollarSign size={14} /> : item.type === 'event' ? <Calendar size={14} /> : <Brain size={14} />;
                        return (
                            <div key={idx} className="sidebar-activity-item">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                                    <span style={{ fontWeight: 'bold' }}>{icon}</span>
                                    <div className="sidebar-activity-title">{item.title}</div>
                                </div>
                                {item.subtitle && <div style={{ fontSize: '11px', opacity: 0.7 }}>{item.subtitle}</div>}
                            </div>
                        );
                    })
                )}
            </div>

            {/* Tip */}
            <div className="tip-box">
                &gt; <strong>TIP:</strong> Click an event or task to insert it into the context window.
            </div>

            {/* Sync Button */}
            <div style={{ marginTop: '20px' }}>
                <button
                    onClick={async () => {
                        const btn = document.getElementById('sync-btn');
                        if (btn) {
                            btn.innerText = 'SYNCING...';
                            (btn as HTMLButtonElement).disabled = true;
                        }
                        try {
                            await axios.post('/api/sync');
                            alert('SYNC COMPLETE');
                        } catch (e) {
                            alert('SYNC FAILED');
                            console.error(e);
                        } finally {
                            if (btn) {
                                btn.innerText = 'SYNC DATA';
                                (btn as HTMLButtonElement).disabled = false;
                            }
                        }
                    }}
                    id="sync-btn"
                    className="sync-btn"
                >
                    SYNC DATA
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
