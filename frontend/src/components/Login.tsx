import React from 'react';
import { useGoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import Logo from './Logo';

interface LoginProps {
    onSuccess: (credentialResponse: any) => void;
    onError: () => void;
}

const Login: React.FC<LoginProps> = ({ onSuccess, onError }) => {

    const login = useGoogleLogin({
        onSuccess: async (codeResponse) => {
            try {
                // Exchange code for tokens via backend
                const res = await axios.post('/api/auth/google/login', {
                    code: codeResponse.code
                });
                onSuccess(res.data);
            } catch (error) {
                console.error("Login exchange failed", error);
                onError();
            }
        },
        onError: onError,
        flow: 'auth-code',
        scope: 'https://www.googleapis.com/auth/calendar.readonly openid email profile'
    });

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            background: '#ffffff',
            color: '#000000',
            fontFamily: "'Courier Prime', 'Courier New', monospace"
        }}>
            <div style={{
                textAlign: 'center',
                marginBottom: '40px'
            }}>
                <Logo animatedText={true} sequence={["ThoughtOS"]} loop={false} speed={80} />
            </div>

            <div style={{ marginBottom: '40px', textAlign: 'center' }}>
                <p style={{ fontSize: '14px', marginBottom: '8px', opacity: 0.7 }}>PROPRIETARY THOUGHT PROCESSING UNIT</p>
                <p style={{ fontSize: '12px', opacity: 0.5 }}>VERSION 1.0.0</p>
            </div>

            <button
                onClick={() => login()}
                style={{
                    padding: '16px 32px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    background: 'black',
                    color: 'white',
                    border: '1px solid black',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    textTransform: 'uppercase',
                    transition: 'all 0.2s',
                    boxShadow: '4px 4px 0px rgba(0,0,0,0.1)'
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'white';
                    e.currentTarget.style.color = 'black';
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'black';
                    e.currentTarget.style.color = 'white';
                }}
            >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'block' }}>
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="currentColor" />
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="currentColor" />
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.84z" fill="currentColor" />
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="currentColor" />
                </svg>
                Authenticate with Google
            </button>
        </div>
    );
};

export default Login;
