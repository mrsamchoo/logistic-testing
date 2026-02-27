import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useSocket } from '../contexts/SocketContext';
import ChannelBadge from '../components/shared/ChannelBadge';
import { formatDistanceToNow } from 'date-fns';

// === Tag color utility ===
const TAG_COLORS = [
  'bg-blue-100 text-blue-700', 'bg-green-100 text-green-700', 'bg-purple-100 text-purple-700',
  'bg-pink-100 text-pink-700', 'bg-yellow-100 text-yellow-700', 'bg-indigo-100 text-indigo-700',
  'bg-teal-100 text-teal-700', 'bg-orange-100 text-orange-700',
];
function getTagColor(tag) {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
}

// === Priority helpers ===
const PRIORITY_OPTIONS = [
  { value: 'normal', label: 'Normal', dot: '' },
  { value: 'high', label: 'High', dot: '🟡' },
  { value: 'urgent', label: 'Urgent', dot: '🔴' },
];

// === Media Lightbox Component (Image + Video) ===
function MediaLightbox({ src, type, onClose }) {
  if (!src) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={onClose}>
      <button onClick={onClose} className="absolute top-4 right-4 text-white text-3xl hover:text-gray-300 z-10">&times;</button>
      {type === 'video' ? (
        <video src={src} controls autoPlay className="max-w-full max-h-[90vh] rounded-lg shadow-2xl" onClick={(e) => e.stopPropagation()} />
      ) : (
        <img src={src} alt="Full size" className="max-w-full max-h-[90vh] rounded-lg shadow-2xl" onClick={(e) => e.stopPropagation()} />
      )}
    </div>
  );
}

// === Message Bubble with Image/Video Support ===
function MessageBubble({ msg, onMediaClick }) {
  const isContact = msg.sender_type === 'contact';
  const isAi = msg.sender_type === 'ai';

  // Parse metadata for media messages (image/video)
  let mediaUrl = null;
  let mediaType = null;
  if (msg.message_type === 'image' || msg.message_type === 'video') {
    try {
      const meta = typeof msg.metadata_json === 'string' ? JSON.parse(msg.metadata_json) : (msg.metadata_json || {});
      if (meta.media_url) {
        // Admin-uploaded file
        mediaUrl = meta.media_url;
      } else if (meta.message_id) {
        // LINE content API proxy
        mediaUrl = `/api/messaging/media/line/${meta.message_id}?channel_id=${meta.channel_id || ''}`;
      }
      mediaType = msg.message_type;
    } catch (e) { /* ignore */ }
  }

  return (
    <div className={`flex ${isContact ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-md px-3 py-2 rounded-2xl text-sm ${
        isContact
          ? 'bg-white border shadow-sm'
          : isAi
          ? 'bg-purple-100 text-purple-800'
          : 'bg-blue-600 text-white'
      }`}>
        {mediaUrl && mediaType === 'image' ? (
          <img
            src={mediaUrl}
            alt="Shared image"
            className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
            onClick={() => onMediaClick(mediaUrl, 'image')}
            onError={(e) => { e.target.onerror = null; e.target.src = ''; e.target.alt = '[Image not available]'; e.target.className = 'text-gray-400 text-xs'; }}
          />
        ) : mediaUrl && mediaType === 'video' ? (
          <div className="relative cursor-pointer" onClick={() => onMediaClick(mediaUrl, 'video')}>
            <video src={mediaUrl} className="max-w-xs rounded-lg" preload="metadata" />
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-lg hover:bg-black/20 transition-colors">
              <span className="text-white text-4xl">&#x25B6;</span>
            </div>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        )}
        <p className={`text-xs mt-1 ${isContact ? 'text-gray-400' : 'opacity-70'}`}>
          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          {msg.sender_type === 'admin' && msg.admin_username && ` · ${msg.admin_username}`}
          {isAi && ' · AI'}
        </p>
      </div>
    </div>
  );
}


function ConversationList({ conversations, selectedId, onSelect, onTogglePin }) {
  if (!conversations.length) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm p-4">
        No conversations yet. Messages from customers will appear here.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {conversations.map((conv) => {
        const isUrgent = conv.priority === 'urgent';
        const isHigh = conv.priority === 'high';
        const isPinned = conv.is_pinned === 1;

        return (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`flex items-start gap-3 p-3 cursor-pointer border-b transition-colors ${
              conv.id === selectedId ? 'bg-blue-50 border-l-4 border-l-blue-600' :
              isUrgent ? 'border-l-4 border-l-red-500 hover:bg-red-50' :
              isHigh ? 'border-l-4 border-l-yellow-400 hover:bg-yellow-50' :
              'hover:bg-gray-50'
            }`}
          >
            <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center text-sm font-bold text-gray-600 shrink-0 relative">
              {conv.contact_name?.[0]?.toUpperCase() || '?'}
              {isUrgent && <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white"></span>}
              {isHigh && !isUrgent && <span className="absolute -top-1 -right-1 w-3 h-3 bg-yellow-400 rounded-full border-2 border-white"></span>}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                {isPinned && <span className="text-xs" title="Pinned">📌</span>}
                <span className="font-medium text-sm truncate">{conv.contact_name || 'Unknown'}</span>
                <ChannelBadge type={conv.channel_type} />
              </div>
              <p className="text-xs text-gray-500 truncate mt-0.5">{conv.last_message_preview || 'No messages'}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-gray-400">
                  {conv.last_message_at ? formatDistanceToNow(new Date(conv.last_message_at), { addSuffix: true }) : ''}
                </span>
                {conv.unread_count > 0 && (
                  <span className="bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {conv.unread_count}
                  </span>
                )}
              </div>
            </div>
            {/* Pin button */}
            <button
              onClick={(e) => { e.stopPropagation(); onTogglePin(conv.id, isPinned); }}
              className={`text-xs shrink-0 px-1 py-0.5 rounded hover:bg-gray-100 ${isPinned ? 'text-blue-600' : 'text-gray-300 hover:text-gray-500'}`}
              title={isPinned ? 'Unpin' : 'Pin'}
            >
              📌
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ChatPanel({ conversationId, onConversationUpdated }) {
  const [messages, setMessages] = useState([]);
  const [conversation, setConversation] = useState(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [tags, setTags] = useState([]);
  const [showTagInput, setShowTagInput] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [lightbox, setLightbox] = useState({ src: null, type: 'image' });
  const [showPriorityMenu, setShowPriorityMenu] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const isInitialLoad = useRef(true);
  const socket = useSocket();

  const loadMessages = useCallback(() => {
    if (!conversationId) return;
    // Reset pagination state on conversation change
    setHasMore(false);
    isInitialLoad.current = true;
    api.get(`/conversations/${conversationId}`).then(setConversation);
    api.get(`/conversations/${conversationId}/messages?limit=50`).then((data) => {
      setMessages(data.messages);
      setHasMore(data.messages.length < data.total);
    });
    api.post(`/conversations/${conversationId}/read`).catch(() => {});
  }, [conversationId]);

  // Auto-scroll to bottom on initial load
  useEffect(() => {
    if (isInitialLoad.current && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView();
      isInitialLoad.current = false;
    }
  }, [messages]);

  const loadOlderMessages = useCallback(async () => {
    if (!conversationId || loadingMore || !hasMore || messages.length === 0) return;
    setLoadingMore(true);

    const container = messagesContainerRef.current;
    const prevScrollHeight = container?.scrollHeight || 0;
    const oldestId = messages[0].id;

    try {
      const data = await api.get(
        `/conversations/${conversationId}/messages?limit=50&before_id=${oldestId}`
      );
      if (data.messages.length === 0) {
        setHasMore(false);
      } else {
        setMessages(prev => [...data.messages, ...prev]);
        setHasMore(data.messages.length >= 50);
        // Restore scroll position after prepending older messages
        requestAnimationFrame(() => {
          if (container) {
            container.scrollTop = container.scrollHeight - prevScrollHeight;
          }
        });
      }
    } catch (e) {
      console.error('Failed to load older messages:', e);
    }
    setLoadingMore(false);
  }, [conversationId, loadingMore, hasMore, messages]);

  const loadTags = useCallback(() => {
    if (!conversationId) return;
    api.get(`/conversations/${conversationId}/tags`).then(setTags).catch(() => setTags([]));
  }, [conversationId]);

  useEffect(() => {
    loadMessages();
    loadTags();
  }, [loadMessages, loadTags]);

  useEffect(() => {
    if (!socket || !conversationId) return;
    socket.emit('join_conversation', { conversation_id: conversationId });

    const handler = (data) => {
      if (data.conversation_id === conversationId) {
        // Fetch only the newest message and append (don't reload all + lose older messages)
        api.get(`/conversations/${conversationId}/messages?limit=1`).then((resp) => {
          if (resp.messages.length > 0) {
            const newMsg = resp.messages[0];
            setMessages(prev => {
              if (prev.some(m => m.id === newMsg.id)) return prev;
              return [...prev, newMsg];
            });
            // Scroll to new message
            requestAnimationFrame(() => {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            });
          }
        }).catch(() => {});
        // Also refresh conversation metadata (unread count, last message)
        api.get(`/conversations/${conversationId}`).then(setConversation);
        api.post(`/conversations/${conversationId}/read`).catch(() => {});
      }
    };
    socket.on('new_message', handler);

    return () => {
      socket.off('new_message', handler);
      socket.emit('leave_conversation', { conversation_id: conversationId });
    };
  }, [socket, conversationId, loadMessages]);

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    try {
      await api.post(`/conversations/${conversationId}/messages`, { content: input.trim() });
      setInput('');
      // Fetch the newest message and append
      const resp = await api.get(`/conversations/${conversationId}/messages?limit=1`);
      if (resp.messages.length > 0) {
        const sent = resp.messages[0];
        setMessages(prev => {
          if (prev.some(m => m.id === sent.id)) return prev;
          return [...prev, sent];
        });
      }
      requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }));
      if (onConversationUpdated) onConversationUpdated();
    } catch (e) {
      alert(e.message);
    }
    setSending(false);
  };

  const handleAiSuggest = async () => {
    setAiLoading(true);
    setAiSuggestion('');
    try {
      const data = await api.post('/ai/suggest', { conversation_id: conversationId });
      setAiSuggestion(data.suggestion);
    } catch (e) {
      alert(e.message);
    }
    setAiLoading(false);
  };

  const handleAddTag = async () => {
    const tag = newTag.trim();
    if (!tag) return;
    await api.post(`/conversations/${conversationId}/tags`, { tag });
    setNewTag('');
    setShowTagInput(false);
    loadTags();
  };

  const handleRemoveTag = async (tag) => {
    await api.del(`/conversations/${conversationId}/tags/${encodeURIComponent(tag)}`);
    loadTags();
  };

  const handlePriorityChange = async (priority) => {
    await api.put(`/conversations/${conversationId}`, { priority });
    setShowPriorityMenu(false);
    setConversation((prev) => prev ? { ...prev, priority } : prev);
    if (onConversationUpdated) onConversationUpdated();
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'video/mp4', 'video/quicktime', 'video/webm'];
    if (!allowed.includes(file.type)) {
      alert('รองรับเฉพาะไฟล์ภาพ (JPG, PNG, GIF) และวิดีโอ (MP4, WebM)');
      return;
    }

    // Check file size (max 10 MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('ไฟล์ใหญ่เกินไป (สูงสุด 10 MB)');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch(`/api/messaging/conversations/${conversationId}/upload`, {
        method: 'POST',
        body: formData,
      });

      // Handle non-JSON responses (e.g. server error pages)
      const contentType = resp.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error(`Server error (${resp.status}). Please try again.`);
      }

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Upload failed');
      }
      if (data.warning) {
        alert(data.warning);
      }
      loadMessages();
    } catch (err) {
      alert('Upload failed: ' + err.message);
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleExportCSV = () => {
    window.open(`/api/messaging/conversations/${conversationId}/export`, '_blank');
  };

  if (!conversationId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        Select a conversation to start chatting
      </div>
    );
  }

  // Determine channel_id for media proxy
  const channelId = conversation?.channel_id || '';

  return (
    <div className="flex-1 flex flex-col">
      {/* Lightbox */}
      <MediaLightbox src={lightbox.src} type={lightbox.type} onClose={() => setLightbox({ src: null, type: 'image' })} />

      {/* Header */}
      {conversation && (
        <div className="p-3 border-b bg-white">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-sm font-bold">
              {conversation.contact_name?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1">
              <p className="font-medium text-sm">{conversation.contact_name || 'Unknown'}</p>
              <p className="text-xs text-gray-500">via {conversation.channel_name}</p>
            </div>
            <ChannelBadge type={conversation.channel_type} />

            {/* Priority selector */}
            <div className="relative">
              <button
                onClick={() => setShowPriorityMenu(!showPriorityMenu)}
                className={`text-xs px-2 py-1 rounded-full border ${
                  conversation.priority === 'urgent' ? 'bg-red-100 text-red-700 border-red-300' :
                  conversation.priority === 'high' ? 'bg-yellow-100 text-yellow-700 border-yellow-300' :
                  'bg-gray-100 text-gray-600 border-gray-200'
                }`}
              >
                {PRIORITY_OPTIONS.find(p => p.value === (conversation.priority || 'normal'))?.dot || ''}{' '}
                {conversation.priority || 'normal'}
              </button>
              {showPriorityMenu && (
                <div className="absolute right-0 top-8 bg-white border rounded-lg shadow-lg z-20 py-1 w-32">
                  {PRIORITY_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => handlePriorityChange(opt.value)}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 ${
                        conversation.priority === opt.value ? 'font-bold' : ''
                      }`}
                    >
                      {opt.dot} {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <span className={`text-xs px-2 py-1 rounded-full ${
              conversation.status === 'open' ? 'bg-green-100 text-green-700' :
              conversation.status === 'resolved' ? 'bg-gray-100 text-gray-700' : 'bg-yellow-100 text-yellow-700'
            }`}>
              {conversation.status}
            </span>

            {/* Export CSV button */}
            <button
              onClick={handleExportCSV}
              className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 border"
              title="Export this conversation as CSV"
            >
              📥 CSV
            </button>
          </div>

          {/* Tags row */}
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {tags.map((tag) => (
              <span key={tag} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${getTagColor(tag)}`}>
                {tag}
                <button onClick={() => handleRemoveTag(tag)} className="hover:opacity-70 font-bold">&times;</button>
              </span>
            ))}
            {showTagInput ? (
              <div className="inline-flex items-center gap-1">
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
                  placeholder="Tag name..."
                  className="text-xs border rounded px-2 py-0.5 w-24 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                />
                <button onClick={handleAddTag} className="text-xs text-blue-600 hover:text-blue-800">Add</button>
                <button onClick={() => { setShowTagInput(false); setNewTag(''); }} className="text-xs text-gray-400 hover:text-gray-600">&times;</button>
              </div>
            ) : (
              <button onClick={() => setShowTagInput(true)} className="text-xs text-gray-400 hover:text-blue-600 px-1">+ Tag</button>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
        {/* Load older messages button */}
        {hasMore && (
          <div className="text-center py-2">
            <button
              onClick={loadOlderMessages}
              disabled={loadingMore}
              className="text-xs px-4 py-2 bg-white border rounded-full text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              {loadingMore ? '⏳ กำลังโหลด...' : '⬆ โหลดข้อความเก่า'}
            </button>
          </div>
        )}

        {messages.map((msg) => {
          // Enrich metadata with channel_id for media proxy
          const enrichedMsg = { ...msg };
          if ((msg.message_type === 'image' || msg.message_type === 'video') && channelId) {
            try {
              const meta = typeof msg.metadata_json === 'string' ? JSON.parse(msg.metadata_json) : (msg.metadata_json || {});
              meta.channel_id = channelId;
              enrichedMsg.metadata_json = meta;
            } catch (e) { /* ignore */ }
          }
          return (
            <MessageBubble
              key={msg.id}
              msg={enrichedMsg}
              onMediaClick={(src, type) => setLightbox({ src, type })}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* AI Suggestion */}
      {aiSuggestion && (
        <div className="mx-4 mt-2 p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
          <p className="text-xs text-purple-600 font-medium mb-1">AI Suggestion:</p>
          <p className="text-gray-700">{aiSuggestion}</p>
          <div className="flex gap-2 mt-2">
            <button onClick={() => { setInput(aiSuggestion); setAiSuggestion(''); }} className="text-xs bg-purple-600 text-white px-2 py-1 rounded">Use</button>
            <button onClick={() => setAiSuggestion('')} className="text-xs bg-gray-200 text-gray-600 px-2 py-1 rounded">Dismiss</button>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t bg-white">
        <div className="flex gap-2">
          <button
            onClick={handleAiSuggest}
            disabled={aiLoading}
            className="px-3 py-2 bg-purple-100 text-purple-700 rounded-lg text-sm hover:bg-purple-200 disabled:opacity-50 shrink-0"
            title="AI Suggest"
          >
            {aiLoading ? '...' : '✨'}
          </button>
          {/* File Upload Button */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50 shrink-0"
            title="Send image or video"
          >
            {uploading ? '⏳' : '📎'}
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Type a message..."
            className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 shrink-0"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([]);
  const [filter, setFilter] = useState('all');
  const { id } = useParams();
  const navigate = useNavigate();
  const socket = useSocket();

  const load = useCallback(() => {
    const params = filter !== 'all' ? `?status=${filter}` : '';
    api.get(`/conversations${params}`).then(setConversations);
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!socket) return;
    const handler = () => load();
    socket.on('new_message', handler);
    socket.on('new_conversation', handler);
    return () => {
      socket.off('new_message', handler);
      socket.off('new_conversation', handler);
    };
  }, [socket, load]);

  const handleTogglePin = async (convId, isPinned) => {
    const endpoint = isPinned ? 'unpin' : 'pin';
    await api.post(`/conversations/${convId}/${endpoint}`);
    load();
  };

  const handleExportAll = () => {
    window.open('/api/messaging/conversations/export-all', '_blank');
  };

  return (
    <div className="flex h-full">
      {/* Conversation List */}
      <div className="w-80 border-r bg-white flex flex-col shrink-0">
        <div className="p-3 border-b">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-sm">Conversations</h2>
            <button
              onClick={handleExportAll}
              className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-500 hover:bg-gray-200 border"
              title="Export all conversations as CSV"
            >
              📥 Export All
            </button>
          </div>
          <div className="flex gap-1">
            {['all', 'open', 'assigned', 'resolved'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-xs px-2 py-1 rounded-full capitalize ${filter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        <ConversationList
          conversations={conversations}
          selectedId={id ? parseInt(id) : null}
          onSelect={(convId) => navigate(`/conversations/${convId}`)}
          onTogglePin={handleTogglePin}
        />
      </div>

      {/* Chat */}
      <ChatPanel conversationId={id ? parseInt(id) : null} onConversationUpdated={load} />
    </div>
  );
}
