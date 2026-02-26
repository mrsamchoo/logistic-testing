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

const CHANNEL_ICONS = { line: '\uD83D\uDCAC', facebook: '\uD83D\uDCAC', instagram: '\uD83D\uDCAC' };

const CHANNEL_COLORS = {
  line: 'bg-green-50 border-green-200',
  facebook: 'bg-blue-50 border-blue-200',
  instagram: 'bg-pink-50 border-pink-200',
};

/* ─── Webhook URL Copy Box ─── */
function WebhookUrlBox({ url, label }) {
  const [copied, setCopied] = useState(false);
  const copyUrl = () => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      toast.success('Copied!');
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="mt-3">
      {label && <p className="text-xs font-medium text-gray-500 mb-1">{label}</p>}
      <div className="flex items-center gap-2 bg-gray-900 rounded-lg p-3">
        <code className="flex-1 text-green-400 text-xs break-all select-all">{url}</code>
        <button
          onClick={copyUrl}
          className="shrink-0 bg-white/10 hover:bg-white/20 text-white text-xs px-3 py-1.5 rounded-md transition"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
    </div>
  );
}

/* ─── Setup Guide (shown after creating channel) ─── */
function SetupGuide({ channelType, webhookUrl, verified, verifyMessage, onClose }) {
  const lineSteps = [
    { text: 'Copy Webhook URL ด้านบน' },
    { text: 'ไปที่ LINE Developer Console (developers.line.biz)' },
    { text: 'เลือก Provider แล้วเลือก Channel ของคุณ' },
    { text: 'ไปที่แท็บ "Messaging API"' },
    { text: 'เลื่อนลงไปหา "Webhook URL" แล้วกด Edit แล้ววาง URL ที่ Copy ไว้' },
    { text: 'เปิด "Use webhook" ให้เป็นสีเขียว' },
    { text: 'กลับมาที่หน้านี้แล้วกดปุ่ม "Test" เพื่อทดสอบ' },
  ];
  const fbSteps = [
    { text: 'Copy Webhook URL ด้านบน' },
    { text: 'ไปที่ Facebook Developer Console (developers.facebook.com)' },
    { text: 'เลือก App แล้วไปที่ Webhooks แล้ว Edit Subscription' },
    { text: 'วาง Callback URL = Webhook URL ที่ Copy ไว้' },
    { text: 'กลับมาที่หน้านี้แล้วกดปุ่ม "Test"' },
  ];
  const steps = channelType === 'line' ? lineSteps : fbSteps;

  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-blue-200 p-6 mb-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-gray-800">
          สร้าง Channel สำเร็จ!
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
      </div>

      {/* Verification status */}
      <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${verified ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'}`}>
        <span>{verified ? 'เชื่อมต่อสำเร็จ: ' + verifyMessage : 'ยังไม่ได้เชื่อมต่อ Webhook — ทำตามขั้นตอนด้านล่าง'}</span>
      </div>

      {/* Webhook URL */}
      <WebhookUrlBox url={webhookUrl} label="Webhook URL (Copy ไปวางใน LINE Developer Console)" />

      {/* Steps */}
      <div className="bg-blue-50 rounded-lg p-4">
        <p className="text-sm font-semibold text-blue-800 mb-3">ขั้นตอนการตั้งค่า:</p>
        <ol className="space-y-2">
          {steps.map((step, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-blue-700">
              <span className="bg-blue-200 text-blue-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{i + 1}</span>
              <span>{step.text}</span>
            </li>
          ))}
        </ol>
      </div>

      <button
        onClick={onClose}
        className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition"
      >
        เข้าใจแล้ว ปิดคำแนะนำ
      </button>
    </div>
  );
}

/* ─── Main Page ─── */
export default function ChannelSettingsPage() {
  const [channels, setChannels] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', type: 'line' });
  const [credentials, setCredentials] = useState({});
  const [editChannel, setEditChannel] = useState(null);
  const [verifying, setVerifying] = useState(null);
  const [creating, setCreating] = useState(false);
  const [setupGuide, setSetupGuide] = useState(null);

  const load = () => api.get('/channels').then(setChannels);
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      const result = await api.post('/channels', {
        name: form.name,
        channel_type: form.type,
        credentials,
      });
      toast.success('Channel created!');
      setShowForm(false);
      setForm({ name: '', type: 'line' });
      setCredentials({});
      load();
      setSetupGuide({
        channelType: form.type,
        webhookUrl: result.webhook_url,
        verified: result.verified,
        verifyMessage: result.verify_message || '',
      });
    } catch (err) {
      toast.error(err.message);
    }
    setCreating(false);
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
      if (result.success) {
        toast.success(result.message || 'Connection verified!');
      } else {
        toast.error(result.message || 'Verification failed');
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
          onClick={() => { setShowForm(!showForm); setEditChannel(null); setSetupGuide(null); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
        >
          + Add Channel
        </button>
      </div>

      {/* ─── Setup Guide (after channel creation) ─── */}
      {setupGuide && (
        <SetupGuide
          channelType={setupGuide.channelType}
          webhookUrl={setupGuide.webhookUrl}
          verified={setupGuide.verified}
          verifyMessage={setupGuide.verifyMessage}
          onClose={() => setSetupGuide(null)}
        />
      )}

      {/* ─── Create Channel Form ─── */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm border p-5 mb-6 space-y-4">
          <h3 className="font-semibold text-sm">เพิ่ม Channel ใหม่</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="ชื่อ Channel (เช่น LINE หลัก)"
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
            <button
              type="submit"
              disabled={creating}
              className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'กำลังสร้าง...' : 'สร้าง Channel + Generate Webhook'}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="bg-gray-200 text-gray-600 px-4 py-2 rounded-lg text-sm">ยกเลิก</button>
          </div>
        </form>
      )}

      {/* ─── Channel List ─── */}
      {channels.length === 0 && !showForm ? (
        <div className="text-center text-gray-400 py-12">
          <p className="text-4xl mb-3">📡</p>
          <p>ยังไม่มี Channel — กด "Add Channel" เพื่อเริ่มต้น</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {channels.map((ch) => (
            <div key={ch.id} className={`rounded-xl border-2 p-5 ${CHANNEL_COLORS[ch.channel_type] || 'bg-white border-gray-200'}`}>
              {/* Header row */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-gray-800">{ch.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/70 uppercase font-medium text-gray-600">{ch.channel_type}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${ch.is_active ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-600'}`}>
                      {ch.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {ch.is_verified ? (
                      <span className="text-xs text-green-700 font-medium">Verified</span>
                    ) : (
                      <span className="text-xs text-orange-600">Not Verified</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleVerify(ch.id)}
                    disabled={verifying === ch.id}
                    className="text-xs bg-white hover:bg-gray-50 border px-3 py-1.5 rounded-lg transition"
                  >
                    {verifying === ch.id ? 'Testing...' : 'Test'}
                  </button>
                  <button
                    onClick={() => startEdit(ch)}
                    className="text-xs bg-white hover:bg-gray-50 border px-3 py-1.5 rounded-lg transition"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(ch.id)}
                    className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1.5 rounded-lg transition"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Webhook URL — always visible */}
              {ch.webhook_url && (
                <WebhookUrlBox
                  url={ch.webhook_url}
                  label="Webhook URL — นำ URL นี้ไปวางใน LINE Developer Console > Messaging API > Webhook URL"
                />
              )}

              {/* Edit Credentials */}
              {editChannel === ch.id && (
                <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
                  <p className="text-xs font-medium text-gray-500 uppercase">แก้ไข Credentials</p>
                  {CHANNEL_FIELDS[ch.channel_type]?.map((f) => (
                    <div key={f.key}>
                      <label className="text-xs text-gray-600 mb-1 block">{f.label}</label>
                      <input
                        type={f.type}
                        placeholder={f.label}
                        value={credentials[f.key] || ''}
                        onChange={(e) => setCredentials({ ...credentials, [f.key]: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                  <div className="flex gap-2">
                    <button onClick={() => handleSaveCredentials(ch.id)} className="text-xs bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700">Save</button>
                    <button onClick={() => { setEditChannel(null); setCredentials({}); }} className="text-xs bg-gray-200 px-4 py-1.5 rounded-lg">Cancel</button>
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
