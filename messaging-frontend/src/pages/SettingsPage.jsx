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

function BackupSection() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoringFile, setRestoringFile] = useState('');

  const loadBackups = () => {
    api.get('/backups').then(setBackups).catch(() => []).finally(() => setLoading(false));
  };

  useEffect(() => { loadBackups(); }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const data = await api.post('/backups/create');
      loadBackups();
    } catch (e) {
      alert('Backup error: ' + e.message);
    }
    setCreating(false);
  };

  const handleRestoreFromList = async (filename) => {
    if (!confirm(`คุณต้องการคืนค่าฐานข้อมูลจาก ${filename} ใช่ไหม?\n\nระบบจะสร้าง backup ก่อนอัตโนมัติ`)) return;
    setRestoringFile(filename);
    try {
      const data = await api.post('/backups/restore', { filename });
      alert('คืนค่าสำเร็จ! หน้าจะรีโหลด');
      window.location.reload();
    } catch (e) {
      alert('Restore error: ' + e.message);
    }
    setRestoringFile('');
  };

  const handleUploadRestore = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!confirm('คุณต้องการคืนค่าฐานข้อมูลจากไฟล์ที่อัปโหลดใช่ไหม?\n\nระบบจะสร้าง backup ก่อนอัตโนมัติ')) {
      e.target.value = '';
      return;
    }
    setRestoring(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await fetch('/api/messaging/backups/restore', {
        method: 'POST',
        body: formData,
      });
      const contentType = resp.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error(`Server error (${resp.status})`);
      }
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Restore failed');
      alert('คืนค่าสำเร็จ! หน้าจะรีโหลด');
      window.location.reload();
    } catch (e) {
      alert('Restore error: ' + e.message);
    }
    setRestoring(false);
    e.target.value = '';
  };

  const formatDate = (iso) => {
    try {
      return new Date(iso).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
    } catch { return iso; }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <div className="flex items-start gap-4">
        <span className="text-3xl">💾</span>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-800">Database Backup</h3>
          <p className="text-sm text-gray-500 mt-0.5 mb-3">
            Auto-backup ทุก 6 ชม. + backup ตอน server เริ่มทำงาน (เก็บล่าสุด 5 ตัว)
          </p>

          {/* Create + Upload buttons */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={handleCreate}
              disabled={creating}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? '⏳ กำลังสร้าง...' : '📦 สร้าง Backup ตอนนี้'}
            </button>
            <label className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 cursor-pointer border">
              {restoring ? '⏳ กำลัง Restore...' : '📂 Restore จากไฟล์'}
              <input type="file" accept=".db" onChange={handleUploadRestore} className="hidden" disabled={restoring} />
            </label>
          </div>

          {/* Backup list */}
          {loading ? (
            <p className="text-sm text-gray-400">กำลังโหลด...</p>
          ) : backups.length === 0 ? (
            <p className="text-sm text-gray-400">ยังไม่มี backup</p>
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">ไฟล์</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">ขนาด</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">วันที่</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {backups.map((b, i) => (
                    <tr key={b.filename} className={i === 0 ? 'bg-green-50' : ''}>
                      <td className="px-3 py-2 font-mono text-xs">
                        {i === 0 && <span className="text-green-600 mr-1">●</span>}
                        {b.filename}
                      </td>
                      <td className="px-3 py-2 text-gray-500">{b.size_mb} MB</td>
                      <td className="px-3 py-2 text-gray-500">{formatDate(b.created_at)}</td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex gap-1 justify-end">
                          <a
                            href={`/api/messaging/backups/${b.filename}/download`}
                            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
                          >
                            ⬇ Download
                          </a>
                          <button
                            onClick={() => handleRestoreFromList(b.filename)}
                            disabled={restoringFile === b.filename}
                            className="px-2 py-1 text-xs bg-orange-50 hover:bg-orange-100 rounded text-orange-600 disabled:opacity-50"
                          >
                            {restoringFile === b.filename ? '⏳' : '↩'} Restore
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
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

        {/* Backup */}
        <BackupSection />

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
