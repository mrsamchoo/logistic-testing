import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';

const CHANNEL_FIELDS = {
  line: [
    { key: 'channel_access_token', label: 'Channel Access Token', type: 'password' },
    { key: 'channel_secret', label: 'Channel Secret', type: 'password' },
  ],
  facebook: [
    { key: 'page_access_token', label: 'Page Access Token', type: 'password' },
    { key: 'app_secret', label: 'App Secret', type: 'password' },
    { key: 'page_id', label: 'Page ID', type: 'text' },
  ],
  instagram: [
    { key: 'access_token', label: 'Access Token', type: 'password' },
    { key: 'app_secret', label: 'App Secret', type: 'password' },
    { key: 'ig_account_id', label: 'Instagram Account ID', type: 'text' },
  ],
};

const CHANNEL_COLORS = {
  line: 'bg-green-50 border-green-200 text-green-700',
  facebook: 'bg-blue-50 border-blue-200 text-blue-700',
  instagram: 'bg-pink-50 border-pink-200 text-pink-700',
};

export default function ChannelSettingsPage() {
  const [channels, setChannels] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', type: 'line' });
  const [credentials, setCredentials] = useState({});
  const [editChannel, setEditChannel] = useState(null);
  const [verifying, setVerifying] = useState(null);

  const load = () => api.get('/channels').then(setChannels);
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const ch = await api.post('/channels', { name: form.name, channel_type: form.type });
      await api.post(`/channels/${ch.id}/credentials`, { credentials });
      toast.success('Channel created');
      setShowForm(false);
      setForm({ name: '', type: 'line' });
      setCredentials({});
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleSaveCredentials = async (channelId) => {
    try {
      await api.post(`/channels/${channelId}/credentials`, { credentials });
      toast.success('Credentials saved');
      setEditChannel(null);
      setCredentials({});
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleVerify = async (channelId) => {
    setVerifying(channelId);
    try {
      const result = await api.post(`/channels/${channelId}/verify`);
      if (result.valid) {
        toast.success('Connection verified!');
      } else {
        toast.error(result.error || 'Verification failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
    setVerifying(null);
    load();
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this channel? This cannot be undone.')) return;
    await api.del(`/channels/${id}`);
    toast.success('Channel deleted');
    load();
  };

  const startEdit = async (ch) => {
    setEditChannel(ch.id);
    try {
      const creds = await api.get(`/channels/${ch.id}/credentials`);
      setCredentials(creds);
    } catch {
      setCredentials({});
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/settings" className="hover:text-blue-600">Settings</Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">Channels</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Channels</h1>
        <button
          onClick={() => { setShowForm(!showForm); setEditChannel(null); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
        >
          + Add Channel
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm border p-5 mb-6 space-y-4">
          <h3 className="font-semibold text-sm">New Channel</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Channel name (e.g. Main LINE)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={form.type}
              onChange={(e) => { setForm({ ...form, type: e.target.value }); setCredentials({}); }}
              className="border rounded-lg px-3 py-2 text-sm"
            >
              <option value="line">LINE</option>
              <option value="facebook">Facebook</option>
              <option value="instagram">Instagram</option>
            </select>
          </div>

          <div className="space-y-3">
            <p className="text-xs text-gray-500 font-medium uppercase">API Credentials</p>
            {CHANNEL_FIELDS[form.type].map((f) => (
              <div key={f.key}>
                <label className="text-xs text-gray-600 mb-1 block">{f.label}</label>
                <input
                  type={f.type}
                  placeholder={f.label}
                  value={credentials[f.key] || ''}
                  onChange={(e) => setCredentials({ ...credentials, [f.key]: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">Create Channel</button>
            <button type="button" onClick={() => setShowForm(false)} className="bg-gray-200 text-gray-600 px-4 py-2 rounded-lg text-sm">Cancel</button>
          </div>
        </form>
      )}

      {channels.length === 0 && !showForm ? (
        <div className="text-center text-gray-400 py-12">
          No channels connected. Add a channel to start receiving messages.
        </div>
      ) : (
        <div className="grid gap-4">
          {channels.map((ch) => (
            <div key={ch.id} className={`rounded-xl border p-5 ${CHANNEL_COLORS[ch.channel_type] || 'bg-white'}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{ch.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/50 uppercase font-medium">{ch.channel_type}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${ch.is_active ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-600'}`}>
                      {ch.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {ch.is_verified && <span className="text-xs text-green-700">Verified</span>}
                  </div>
                  {ch.webhook_url && (
                    <p className="text-xs mt-1 opacity-75">Webhook: {ch.webhook_url}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleVerify(ch.id)}
                    disabled={verifying === ch.id}
                    className="text-xs bg-white/70 hover:bg-white px-3 py-1.5 rounded-lg"
                  >
                    {verifying === ch.id ? 'Testing...' : 'Test'}
                  </button>
                  <button
                    onClick={() => startEdit(ch)}
                    className="text-xs bg-white/70 hover:bg-white px-3 py-1.5 rounded-lg"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(ch.id)}
                    className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1.5 rounded-lg"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {editChannel === ch.id && (
                <div className="mt-4 pt-4 border-t border-current/10 space-y-3">
                  <p className="text-xs font-medium uppercase opacity-75">Update Credentials</p>
                  {CHANNEL_FIELDS[ch.channel_type]?.map((f) => (
                    <div key={f.key}>
                      <label className="text-xs opacity-75 mb-1 block">{f.label}</label>
                      <input
                        type={f.type}
                        placeholder={f.label}
                        value={credentials[f.key] || ''}
                        onChange={(e) => setCredentials({ ...credentials, [f.key]: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 text-sm bg-white/80 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                  <div className="flex gap-2">
                    <button onClick={() => handleSaveCredentials(ch.id)} className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg">Save</button>
                    <button onClick={() => { setEditChannel(null); setCredentials({}); }} className="text-xs bg-white/70 px-3 py-1.5 rounded-lg">Cancel</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
