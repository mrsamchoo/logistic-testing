import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';

const PROVIDER_INFO = {
  openai: { label: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'] },
  anthropic: { label: 'Anthropic', models: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001', 'claude-opus-4-20250514'] },
  google_gemini: { label: 'Google Gemini', models: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'] },
};

export default function AISettingsPage() {
  const [providers, setProviders] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ provider_type: 'openai', name: '', api_key: '', model_name: '', system_prompt: '' });
  const [editId, setEditId] = useState(null);
  const [testing, setTesting] = useState(null);

  const load = () => api.get('/ai-providers').then(setProviders);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editId) {
        await api.put(`/ai-providers/${editId}`, form);
        toast.success('Provider updated');
      } else {
        await api.post('/ai-providers', form);
        toast.success('Provider added');
      }
      resetForm();
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const resetForm = () => {
    setForm({ provider_type: 'openai', name: '', api_key: '', model_name: '', system_prompt: '' });
    setEditId(null);
    setShowForm(false);
  };

  const handleEdit = (p) => {
    setForm({
      provider_type: p.provider_type,
      name: p.name || '',
      api_key: '',
      model_name: p.model_name || '',
      system_prompt: p.system_prompt || '',
    });
    setEditId(p.id);
    setShowForm(true);
  };

  const handleTest = async (id) => {
    setTesting(id);
    try {
      const result = await api.post(`/ai-providers/${id}/test`);
      if (result.success) {
        toast.success('API key is valid!');
      } else {
        toast.error(result.message || 'Test failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
    setTesting(null);
  };

  const handleDelete = async (id) => {
    if (!confirm('Remove this AI provider?')) return;
    await api.del(`/ai-providers/${id}`);
    toast.success('Provider removed');
    load();
  };

  const handleSetActive = async (id) => {
    await api.post(`/ai-providers/${id}/activate`);
    toast.success('Provider activated');
    load();
  };

  const currentModels = PROVIDER_INFO[form.provider_type]?.models || [];

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/settings" className="hover:text-blue-600">Settings</Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">AI Providers</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">AI Providers</h1>
        <button
          onClick={() => { setShowForm(!showForm); setEditId(null); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
        >
          + Add Provider
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border p-5 mb-6 space-y-4">
          <h3 className="font-semibold text-sm">{editId ? 'Edit Provider' : 'New AI Provider'}</h3>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-600 mb-1 block">Provider</label>
              <select
                value={form.provider_type}
                onChange={(e) => setForm({ ...form, provider_type: e.target.value, model_name: '' })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                {Object.entries(PROVIDER_INFO).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-600 mb-1 block">Model</label>
              <select
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Select model...</option>
                {currentModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-600 mb-1 block">Name</label>
            <input
              type="text"
              placeholder="e.g. ChatGPT, Claude, Gemini..."
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="text-xs text-gray-600 mb-1 block">API Key</label>
            <input
              type="password"
              placeholder={editId ? 'Leave blank to keep current key' : 'Enter API key'}
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              required={!editId}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="text-xs text-gray-600 mb-1 block">System Prompt (optional)</label>
            <textarea
              placeholder="Custom instructions for the AI when generating suggestions..."
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              rows={3}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">{editId ? 'Update' : 'Add Provider'}</button>
            <button type="button" onClick={resetForm} className="bg-gray-200 text-gray-600 px-4 py-2 rounded-lg text-sm">Cancel</button>
          </div>
        </form>
      )}

      {providers.length === 0 && !showForm ? (
        <div className="text-center text-gray-400 py-12">
          No AI providers configured. Add one to enable smart reply suggestions.
        </div>
      ) : (
        <div className="grid gap-4">
          {providers.map((p) => (
            <div key={p.id} className={`bg-white rounded-xl shadow-sm border p-5 ${p.is_active ? 'ring-2 ring-blue-500' : ''}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{p.name || PROVIDER_INFO[p.provider_type]?.label || p.provider_type}</h3>
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{p.model_name}</span>
                    {p.is_active && <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Active</span>}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Key: {p.api_key_masked || '****'}</p>
                  {p.system_prompt && (
                    <p className="text-xs text-gray-400 mt-1 truncate max-w-md">Prompt: {p.system_prompt}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  {!p.is_active && (
                    <button onClick={() => handleSetActive(p.id)} className="text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 px-3 py-1.5 rounded-lg">
                      Set Active
                    </button>
                  )}
                  <button
                    onClick={() => handleTest(p.id)}
                    disabled={testing === p.id}
                    className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-lg"
                  >
                    {testing === p.id ? 'Testing...' : 'Test Key'}
                  </button>
                  <button onClick={() => handleEdit(p)} className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-lg">
                    Edit
                  </button>
                  <button onClick={() => handleDelete(p.id)} className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1.5 rounded-lg">
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
