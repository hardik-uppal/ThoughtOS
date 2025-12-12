import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import WidgetRenderer from './components/WidgetRenderer'
import Sidebar from './components/Sidebar'
import AdminPanel from './components/AdminPanel'
import OnboardingWizard from './components/Onboarding/OnboardingWizard'
import Login from './components/Login'
import { detectTemplateType, generateTemplate } from './utils/templates'
import LinkSuggester from './components/LinkSuggester'
import Logo from './components/Logo'
import { Settings, Camera, Save, Archive, Check } from 'lucide-react'
import './App.css'

interface Message {
  role: 'user' | 'assistant';
  content: string;
  widget?: {
    type: string;
    data: any;
  };
  // Track status of user messages
  saved?: boolean;
  archived?: boolean;
}

function App() {
  const [user, setUser] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'ThoughtOS v3.0 Online. How can I help?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeContext, setActiveContext] = useState<any>(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);

  // New State for Features
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [messageToLink, setMessageToLink] = useState<{ idx: number, content: string } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  // Restore Session
  useEffect(() => {
    const storedUser = localStorage.getItem('thoughtos_user');
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        console.error("Failed to restore session");
        localStorage.removeItem('thoughtos_user');
      }
    }
  }, []);

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
        // If 401, maybe token expired?
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
    if (activeContext) {
      const currentId = activeContext.id;
      setMessages(prev => prev.filter(msg =>
        !(msg.widget?.type === 'form' && msg.widget.data.context_id === currentId)
      ));
    }
    setActiveContext(null);
  };

  const sendMessageWithText = async (text: string) => {
    if (!text.trim() && !selectedImage) return;

    // Convert image to base64 if present
    let imageBase64 = null;
    if (selectedImage) {
      imageBase64 = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(selectedImage);
      });
    }

    const userMsg: Message = { role: 'user', content: text };
    // We don't display the image in the chat bubbles yet, but we could.
    // Ideally we append "[Image Uploaded]" to text or rendering logic.
    if (selectedImage) {
      userMsg.content = text ? `${text} \n\n[Image Uploaded]` : '[Image Uploaded]';
    }

    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    // Clear Input State immediately
    setInput('');
    setSelectedImage(null);
    setImagePreview(null);

    try {
      const res = await axios.post('/api/chat', {
        message: text,
        image: imageBase64,
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
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveToGraph = (idx: number, content: string) => {
    setMessageToLink({ idx, content });
    setLinkModalOpen(true);
  };

  const handleArchive = async (idx: number, content: string) => {
    try {
      await axios.post('/api/graph/archive', { text: content });
      // Reset Chat for "Scratchpad" feel
      setMessages([
        { role: 'assistant', content: 'Archived. Fresh scratchpad ready.' }
      ]);
      setThreadId(null);
    } catch (e) {
      alert('Failed to archive');
    }
  };

  const confirmLink = async (links: string[]) => {
    if (!messageToLink) return;
    try {
      await axios.post('/api/graph/save', {
        text: messageToLink.content,
        links: links
      });
      // Reset Chat for "Scratchpad" feel
      setMessages([
        { role: 'assistant', content: 'Saved to Graph. Fresh scratchpad ready.' }
      ]);
      setThreadId(null);
      setLinkModalOpen(false);
      setMessageToLink(null);
    } catch (e) {
      alert('Failed to save to graph');
    }
  };

  if (!user) {
    return (
      <Login
        onSuccess={(credentialResponse) => {
          localStorage.setItem('thoughtos_user', JSON.stringify(credentialResponse));
          setUser(credentialResponse);
        }}
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
            <Logo
              animatedText={true}
              sequence={[
                `Logged in as ${user.name || user.email}`,
                "Sources Connected: Google, Plaid",
                "ThoughtOS"
              ]}
              speed={50}
              delay={3000}
              loop={false}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => {
                setUser(null);
                localStorage.removeItem('thoughtos_user');
                window.location.reload();
              }}
              style={{
                background: 'transparent',
                border: '1px solid #ff4444',
                color: '#ff4444',
                borderRadius: '6px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              Sign Out
            </button>
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
              <Settings size={16} />
              Admin
            </button>
          </div>
        </header>

        {/* Context Banner */}
        {activeContext && (
          <div style={{
            padding: '12px 24px',
            background: 'var(--bg-color)',
            color: 'var(--text-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--border-color)'
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
                background: 'var(--bg-color)',
                border: '1px solid var(--border-color)',
                borderRadius: '0',
                padding: '4px 12px',
                color: 'var(--text-color)',
                cursor: 'pointer',
                fontSize: '12px',
                fontFamily: 'inherit',
                textTransform: 'uppercase',
                fontWeight: 'bold'
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

                {/* Actions for User Messages */}
                {msg.role === 'user' && !msg.saved && !msg.archived && (
                  <div className="message-actions" style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => handleSaveToGraph(idx, msg.content)}
                      style={{
                        fontSize: '12px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #ddd', background: 'white', cursor: 'pointer'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Save size={14} /> Save to Graph</div>
                    </button>
                    <button
                      onClick={() => handleArchive(idx, msg.content)}
                      style={{
                        fontSize: '12px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #ddd', background: 'white', cursor: 'pointer', color: '#666'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Archive size={14} /> Archive</div>
                    </button>
                  </div>
                )}
                {msg.saved && <div style={{ fontSize: '10px', color: '#2ecc71', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={12} /> Saved to Graph</div>}
                {msg.archived && <div style={{ fontSize: '10px', color: '#95a5a6', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={12} /> Archived</div>}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          {imagePreview && (
            <div style={{ position: 'absolute', bottom: '60px', left: '20px', background: 'white', padding: '8px', borderRadius: '8px', boxShadow: '0 -2px 10px rgba(0,0,0,0.1)' }}>
              <img src={imagePreview} alt="Preview" style={{ height: '80px', borderRadius: '4px' }} />
              <button onClick={() => { setSelectedImage(null); setImagePreview(null); }} style={{ position: 'absolute', top: -5, right: -5, background: 'red', color: 'white', borderRadius: '50%', width: '20px', height: '20px', border: 'none', cursor: 'pointer' }}>×</button>
            </div>
          )}

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImageSelect}
            accept="image/*"
            style={{ display: 'none' }}
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            className="icon-btn"
            title="Upload Image"
          >
            <Camera size={20} />
          </button>

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

      {/* Link Suggester Modal */}
      {linkModalOpen && messageToLink && (
        <LinkSuggester
          content={messageToLink.content}
          onConfirm={confirmLink}
          onCancel={() => setLinkModalOpen(false)}
        />
      )}
    </div>
  )
}

export default App
