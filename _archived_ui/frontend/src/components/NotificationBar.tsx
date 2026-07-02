import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Logo from './Logo';
import { Save, X, Bell } from 'lucide-react';

type HeaderState = 'boot' | 'idle' | 'notification' | 'context';

interface Notification {
    id: string;
    type: string;
    title: string;
    action_label: string;
    action_type: string;
    context_data: any;
    priority: number;
}

interface NotificationBarProps {
    user: any;
    activeContext: any;
    onSetContext: (ctx: any) => void;
    onSaveContext: () => void;
    onClearContext: () => void;
}

const NotificationBar: React.FC<NotificationBarProps> = ({
    user,
    activeContext,
    onSetContext,
    onSaveContext,
    onClearContext
}) => {
    const [headerState, setHeaderState] = useState<HeaderState>('boot');
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [bootComplete, setBootComplete] = useState(false);

    // Check if boot sequence already played (session storage)
    useEffect(() => {
        const hasBooted = sessionStorage.getItem('thoughtos_booted');
        if (hasBooted) {
            setBootComplete(true);
            setHeaderState('idle');
        }
    }, []);

    // Fetch notifications on mount and periodically
    useEffect(() => {
        const fetchNotifications = async () => {
            try {
                const res = await axios.get('/api/notifications');
                setNotifications(res.data.notifications || []);
            } catch (e) {
                console.error('Failed to fetch notifications', e);
            }
        };

        fetchNotifications();
        const interval = setInterval(fetchNotifications, 60000);
        return () => clearInterval(interval);
    }, []);

    // State machine: determine current header state
    useEffect(() => {
        if (!bootComplete) {
            setHeaderState('boot');
        } else if (activeContext) {
            setHeaderState('context');
        } else if (notifications.length > 0) {
            setHeaderState('notification');
        } else {
            setHeaderState('idle');
        }
    }, [bootComplete, activeContext, notifications]);

    const handleBootComplete = () => {
        setBootComplete(true);
        sessionStorage.setItem('thoughtos_booted', 'true');
    };

    const handleNotificationAction = async (notification: Notification) => {
        if (notification.action_type === 'set_context') {
            onSetContext(notification.context_data);
        }
        // Remove from local state
        setNotifications(prev => prev.filter(n => n.id !== notification.id));
    };

    const handleDismissNotification = async (notificationId: string) => {
        try {
            await axios.post('/api/notifications/dismiss', { notification_id: notificationId });
            setNotifications(prev => prev.filter(n => n.id !== notificationId));
        } catch (e) {
            console.error('Failed to dismiss notification', e);
        }
    };

    const currentNotification = notifications[0];
    const moreCount = notifications.length - 1;

    const renderContent = () => {
        switch (headerState) {
            case 'boot':
                return (
                    <Logo
                        animatedText={true}
                        sequence={[
                            'ThoughtOS',
                            `Logged in as ${user?.name || user?.email || 'User'}`,
                            'Sources: Plaid ✓ Google ✓',
                            'ThoughtOS'
                        ]}
                        speed={50}
                        delay={2000}
                        loop={false}
                        onSequenceComplete={handleBootComplete}
                    />
                );

            case 'idle':
                return (
                    <Logo
                        animatedText={true}
                        sequence={['ThoughtOS']}
                        speed={50}
                        loop={false}
                    />
                );

            case 'notification':
                return (
                    <div className="notification-bar-content">
                        <div className="notification-text">
                            <Bell size={16} style={{ marginRight: '8px' }} />
                            {currentNotification?.title}
                            {moreCount > 0 && (
                                <span className="notification-more">({moreCount} more)</span>
                            )}
                        </div>
                        <div className="notification-actions">
                            <button
                                className="notification-action-btn"
                                onClick={() => handleNotificationAction(currentNotification)}
                            >
                                {currentNotification?.action_label}
                            </button>
                            <button
                                className="notification-dismiss-btn"
                                onClick={() => handleDismissNotification(currentNotification.id)}
                                title="Dismiss"
                            >
                                <X size={16} />
                            </button>
                        </div>
                    </div>
                );

            case 'context':
                const contextIcon = activeContext?.type === 'event' ? '📅' :
                    activeContext?.type === 'task' ? '📋' : '⚡';
                return (
                    <div className="notification-bar-content">
                        <div className="context-text">
                            <span>{contextIcon}</span>
                            <span style={{ marginLeft: '8px' }}>
                                {activeContext?.summary || activeContext?.content_text || 'Active Context'}
                            </span>
                        </div>
                        <div className="context-actions">
                            <button className="context-save-btn" onClick={onSaveContext}>
                                <Save size={14} style={{ marginRight: '4px' }} />
                                Save
                            </button>
                            <button className="context-clear-btn" onClick={onClearContext}>
                                <X size={14} style={{ marginRight: '4px' }} />
                                Clear
                            </button>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="notification-bar" data-state={headerState}>
            {renderContent()}
        </div>
    );
};

export default NotificationBar;
