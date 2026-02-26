import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from '../api/client';

const settingsSections = [
  { to: '/settings/channels', icon: '📡', label: 'Channels', desc: 'Connect LINE, Facebook, and Instagram accounts' },
  { to: '/settings/ai', icon: '🤖', label: 'AI Providers', desc: 'Configure AI for smart reply suggestions' },
  { to: '/settings/team', icon: '👥', label: 'Team', desc: 'Manage admin users and roles' },
];

function AiToggle() {
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/settings/ai-toggle').then((data) => {
      setEnabled(data.ai_auto_reply_enabled);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const toggle = async () => {
    const newVal = !enabled;
    setEnabled(newVal);
    try {
      await api.put('/settings/ai-toggle', { ai_auto_reply_enabled: newVal });
    } catch (e) {
      setEnabled(!newVal); // revert
      alert('Error: ' + e.message);
    }
  };

  if (loading) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 flex items-center gap-4">
      <span className="text-3xl">🤖</span>
      <div className="flex-1">
        <h3 className="font-semibold text-gray-800">AI Auto-Reply</h3>
        <p className="text-sm text-gray-500 mt-0.5">
          {enabled ? 'AI จะตอบกลับลูกค้าอัตโนมัติเมื่อมีข้อความเข้ามา' : 'ปิดอยู่ — แอดมินจะตอบเองทั้งหมด'}
        </p>
      </div>
      <button
        onClick={toggle}
        className={`relative w-14 h-7 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${enabled ? 'bg-green-500' : 'bg-gray-300'}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow transition-transform duration-200 ${enabled ? 'translate-x-7' : 'translate-x-0'}`}
        />
      </button>
    </div>
  );
}

function PublicUrlSetting() {
  const [url, setUrl] = useState('');
  const [saved, setSaved] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get('/settings/public-url').then((data) => {
      setUrl(data.public_base_url || '');
      setSaved(data.public_base_url || '');
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/settings/public-url', { public_base_url: url });
      setSaved(url);
    } catch (e) {
      alert('Error: ' + e.message);
    }
    setSaving(false);
  };

  if (loading) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <div className="flex items-start gap-4">
        <span className="text-3xl">🌐</span>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-800">Public URL (สำหรับส่งรูป/วิดีโอ)</h3>
          <p className="text-sm text-gray-500 mt-0.5 mb-3">
            ใส่ URL สาธารณะ (Cloudflare Tunnel / ngrok) เพื่อให้ LINE สามารถเข้าถึงรูปที่ส่งได้
          </p>
          <div className="flex gap-2">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://xxxxx.trycloudflare.com"
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSave}
              disabled={saving || url === saved}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 shrink-0"
            >
              {saving ? '...' : 'Save'}
            </button>
          </div>
          {saved && (
            <p className="text-xs text-green-600 mt-2">✅ บันทึกแล้ว: {saved}</p>
          )}
          <p className="text-xs text-gray-400 mt-2">
            💡 ระบบจะตรวจจับอัตโนมัติจาก webhook ที่ LINE ส่งเข้ามา แต่คุณสามารถตั้งค่าเองได้ที่นี่
          </p>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const location = useLocation();

  if (location.pathname !== '/settings') return null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Settings</h1>
      <div className="grid gap-4 max-w-2xl">
        {/* AI Toggle */}
        <AiToggle />

        {/* Public URL */}
        <PublicUrlSetting />

        {settingsSections.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            className="bg-white rounded-xl shadow-sm border p-5 hover:border-blue-300 hover:shadow-md transition-all flex items-center gap-4"
          >
            <span className="text-3xl">{s.icon}</span>
            <div>
              <h3 className="font-semibold text-gray-800">{s.label}</h3>
              <p className="text-sm text-gray-500 mt-0.5">{s.desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
