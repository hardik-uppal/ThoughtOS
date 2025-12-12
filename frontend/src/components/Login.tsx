import React from 'react';
import { useGoogleLogin } from '@react-oauth/google';
import axios from 'axios';

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
            background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
        }}>
            <div style={{
                background: 'white',
                padding: '40px',
                borderRadius: '16px',
                boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                textAlign: 'center'
            }}>
                <h1 style={{ marginBottom: '10px', color: '#333' }}>ThoughtOS</h1>
                <p style={{ marginBottom: '30px', color: '#666' }}>Sign in with Google to access your Context.</p>

                <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <button
                        onClick={() => login()}
                        style={{
                            padding: '12px 24px',
                            fontSize: '16px',
                            borderRadius: '4px',
                            border: '1px solid #ddd',
                            background: 'white',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                        }}
                    >
                        <img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="G" style={{ width: '20px' }} />
                        Sign in with Google
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Login;
