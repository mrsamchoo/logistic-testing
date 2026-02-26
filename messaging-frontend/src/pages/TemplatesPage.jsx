import { useState, useEffect } from 'react';
import { api } from '../api/client';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', content: '', category: 'general', shortcut: '' });
  const [editId, setEditId] = useState(null);

  const load = () => api.get('/templates').then(setTemplates);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (editId) {
      await api.put(`/templates/${editId}`, form);
    } else {
      await api.post('/templates', form);
    }
    setForm({ name: '', content: '', category: 'general', shortcut: '' });
    setEditId(null);
    setShowForm(false);
    load();
  };

  const handleEdit = (t) => {
    setForm({ name: t.name, content: t.content, category: t.category, shortcut: t.shortcut || '' });
    setEditId(t.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this template?')) return;
    await api.del(`/templates/${id}`);
    load();
  };

  const categories = ['general', 'greeting', 'shipping_update', 'faq', 'closing'];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Message Templates</h1>
        <button
          onClick={() => { setShowForm(!showForm); setEditId(null); setForm({ name: '', content: '', category: 'general', shortcut: '' }); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
        >
          + New Template
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Template name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-2">
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="border rounded-lg px-3 py-2 text-sm flex-1"
              >
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <input
                placeholder="/shortcut"
                value={form.shortcut}
                onChange={(e) => setForm({ ...form, shortcut: e.target.value })}
                className="border rounded-lg px-3 py-2 text-sm w-28"
              />
            </div>
          </div>
          <textarea
            placeholder="Message content..."
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            required
            rows={3}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">{editId ? 'Update' : 'Create'}</button>
            <button type="button" onClick={() => setShowForm(false)} className="bg-gray-200 text-gray-600 px-4 py-2 rounded-lg text-sm">Cancel</button>
          </div>
        </form>
      )}

      {templates.length === 0 ? (
        <div className="text-center text-gray-400 py-12">No templates yet. Create one to use quick replies in conversations.</div>
      ) : (
        <div className="grid gap-3">
          {templates.map((t) => (
            <div key={t.id} className="bg-white rounded-xl shadow-sm border p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-sm">{t.name}</h3>
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t.category}</span>
                    {t.shortcut && <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">{t.shortcut}</span>}
                  </div>
                  <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">{t.content}</p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => handleEdit(t)} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => handleDelete(t.id)} className="text-xs text-red-600 hover:underline">Delete</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
