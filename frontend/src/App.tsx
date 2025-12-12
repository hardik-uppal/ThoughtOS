import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import WidgetRenderer from './components/WidgetRenderer'
import Sidebar from './components/Sidebar'
import AdminPanel from './components/AdminPanel'
import OnboardingWizard from './components/Onboarding/OnboardingWizard'
import Login from './components/Login'
import { detectTemplateType, generateTemplate } from './utils/templates'
import './App.css'

interface Message {
  role: 'user' | 'assistant';
  content: string;
  widget?: {
    type: string;
    data: any;
  };
}

function App() {
  const [user, setUser] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'ContextOS v3.0 Online. How can I help?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeContext, setActiveContext] = useState<any>(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  // Setup Axios Interceptor
  useEffect(() => {
    const interceptor = axios.interceptors.request.use(config => {
      if (user?.credential) {
        config.headers.Authorization = `Bearer ${user.credential}`;
      }
      return config;
    });
    return () => axios.interceptors.request.eject(interceptor);
  }, [user]);

  // Check Onboarding Status (Only if logged in)
  useEffect(() => {
    if (!user) return;
    const checkOnboarding = async () => {
      try {
        const res = await axios.get('/api/onboarding/status');
        if (!res.data.complete) {
          setShowOnboarding(true);
        }
      } catch (e) {
        console.error("Failed to check onboarding status", e);
      }
    };
    checkOnboarding();
  }, [user]);

  const handleContextSelect = (item: any, type: 'event' | 'task') => {
    const contextData = { ...item, type, id: item.id || item.event_id || item.entry_id };
    setActiveContext(contextData);

    // Generate form directly and add to chat
    const templateType = detectTemplateType(item);
    const template = generateTemplate(templateType, item);

    // Add form widget message
    const formMessage: Message = {
      role: 'assistant',
      content: `Here's a form to capture details about "${item.summary || item.content_text}":`,
      widget: {
        type: 'form',
        data: {
          ...template,
          context_id: contextData.id,
          context_type: contextData.type
        }
      }
    };

    setMessages(prev => [...prev, formMessage]);
  };

  const clearContext = () => {
    setActiveContext(null);
  };

  const sendMessageWithText = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await axios.post('/api/chat', {
        message: text,
        thread_id: threadId,
        context: activeContext
      });

      // Update thread ID
      if (res.data.thread_id) {
        setThreadId(res.data.thread_id);
      }

      // Check for special actions
      if (res.data.type === 'action_backfill') {
        axios.post('/api/action/backfill', { days: res.data.days || 365 })
          .catch(err => console.error("Backfill trigger failed", err));
      }

      const assistantMsg: Message = {
        role: 'assistant',
        content: res.data.content,
        widget: res.data.type !== 'chat' && res.data.type !== 'action_backfill' ? { type: res.data.type, data: res.data.data || res.data } : undefined
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error connecting to brain.' }]);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    sendMessageWithText(input);
    setInput('');
  };

  if (!user) {
    return (
      <Login
        onSuccess={(credentialResponse) => setUser(credentialResponse)}
        onError={() => alert('Login Failed')}
      />
    );
  }

  return (
    <div className="app-container" style={{ flexDirection: 'row', maxWidth: '100%' }}>
      <Sidebar onContextSelect={handleContextSelect} activeContext={activeContext} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>
        <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1>ContextOS</h1>
            <span style={{ fontSize: '12px', color: '#666' }}>{user.email || 'Logged In'}</span>
          </div>
          <button
            onClick={() => setAdminOpen(true)}
            style={{
              background: 'transparent',
              border: '1px solid #e0e0e0',
              borderRadius: '6px',
              padding: '8px 16px',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#666',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f5f5f5';
              e.currentTarget.style.borderColor = '#ccc';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.borderColor = '#e0e0e0';
            }}
          >
            <span>⚙️</span>
            Admin
          </button>
        </header>

        {/* Context Banner */}
        {activeContext && (
          <div style={{
            padding: '12px 24px',
            background: '#007AFF',
            color: 'white',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.2)'
          }}>
            <div>
              <span style={{ fontSize: '12px', opacity: 0.9 }}>Linked Context:</span>
              <strong style={{ marginLeft: '8px' }}>
                {activeContext.summary || activeContext.content_text}
              </strong>
            </div>
            <button
              onClick={clearContext}
              style={{
                background: 'rgba(255,255,255,0.2)',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 12px',
                color: 'white',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Clear
            </button>
          </div>
        )}

        <div className="chat-window">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
                {msg.widget && <WidgetRenderer type={msg.widget.type} data={msg.widget.data} />}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type a message..."
            disabled={loading}
          />
          <button onClick={sendMessage} disabled={loading}>
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>

      <AdminPanel isOpen={adminOpen} onClose={() => setAdminOpen(false)} />

      {/* Onboarding Wizard Overlay */}
      {showOnboarding && (
        <OnboardingWizard onComplete={() => setShowOnboarding(false)} />
      )}
    </div>
  )
}

export default App
