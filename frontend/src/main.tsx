import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google';
import './index.css'
import App from './App.tsx'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || import.meta.env.GOOGLE_CLIENT_ID || "YOUR_CLIENT_ID_PLACEHOLDER";
console.log('ContextOS Debug: Client ID loaded:', clientId);
console.log('ContextOS Debug: Client ID loaded:', clientId);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={clientId}>
      <App />
    </GoogleOAuthProvider>
  </StrictMode>,
)
