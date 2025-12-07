import React, { useState } from 'react';
import axios from 'axios';
import { usePlaidLink } from 'react-plaid-link';

interface ConnectStepProps {
    onNext: () => void;
}

const ConnectStep: React.FC<ConnectStepProps> = ({ onNext }) => {
    const [plaidConnected, setPlaidConnected] = useState(false);
    const [googleConnected, setGoogleConnected] = useState(false);
    const [linkToken, setLinkToken] = useState<string | null>(null);

    // Initialize Plaid Link Token and Check Status
    React.useEffect(() => {
        const init = async () => {
            try {
                // Check status
                const statusRes = await axios.get('/api/auth/status');
                setPlaidConnected(statusRes.data.plaid);
                setGoogleConnected(statusRes.data.google);

                // Get link token
                const res = await axios.get('/api/auth/plaid/link-token');
                setLinkToken(res.data.link_token);
            } catch (e) {
                console.error("Failed to init auth step", e);
            }
        };
        init();
    }, []);

    const { open: openPlaidLink, ready: plaidReady } = usePlaidLink({
        token: linkToken,
        onSuccess: async (public_token) => {
            await axios.post('/api/auth/plaid/exchange', { public_token });
            setPlaidConnected(true);
        },
    });

    const handleGoogleAuth = async () => {
        try {
            await axios.post('/api/auth/google');
            setGoogleConnected(true);
        } catch (e) {
            alert("Failed to connect Google Calendar");
        }
    };

    return (
        <div>
            <h2 style={{ fontSize: '28px', marginBottom: '12px' }}>Let's get connected.</h2>
            <p style={{ color: '#666', marginBottom: '32px', lineHeight: '1.5' }}>
                ContextOS needs access to your financial and calendar data to build your personalized graph.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '32px' }}>
                {/* Plaid Button */}
                <div style={{
                    padding: '20px',
                    border: '1px solid #eee',
                    borderRadius: '12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: plaidConnected ? '#f0fff4' : 'white',
                    borderColor: plaidConnected ? '#34C759' : '#eee'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '24px' }}>🏦</span>
                        <div>
                            <div style={{ fontWeight: '600' }}>Bank Account</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>Powered by Plaid</div>
                        </div>
                    </div>
                    {plaidConnected ? (
                        <span style={{ color: '#34C759', fontWeight: '600' }}>Connected ✓</span>
                    ) : (
                        <button
                            onClick={() => openPlaidLink()}
                            disabled={!plaidReady}
                            style={{
                                padding: '8px 16px',
                                background: 'black',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer'
                            }}
                        >
                            Connect
                        </button>
                    )}
                </div>

                {/* Google Button */}
                <div style={{
                    padding: '20px',
                    border: '1px solid #eee',
                    borderRadius: '12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: googleConnected ? '#f0fff4' : 'white',
                    borderColor: googleConnected ? '#34C759' : '#eee'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '24px' }}>📅</span>
                        <div>
                            <div style={{ fontWeight: '600' }}>Google Calendar</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>Events & Schedule</div>
                        </div>
                    </div>
                    {googleConnected ? (
                        <span style={{ color: '#34C759', fontWeight: '600' }}>Connected ✓</span>
                    ) : (
                        <button
                            onClick={handleGoogleAuth}
                            style={{
                                padding: '8px 16px',
                                background: 'black',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer'
                            }}
                        >
                            Connect
                        </button>
                    )}
                </div>
            </div>

            <button
                onClick={onNext}
                style={{
                    width: '100%',
                    padding: '16px',
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
};

export default ConnectStep;
