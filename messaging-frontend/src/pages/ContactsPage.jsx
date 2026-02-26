import { useState, useEffect } from 'react';
import { api } from '../api/client';
import ChannelBadge from '../components/shared/ChannelBadge';

export default function ContactsPage() {
  const [contacts, setContacts] = useState([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    api.get(`/contacts${params}`).then(setContacts);
  }, [search]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Contacts</h1>
        <input
          type="text"
          placeholder="Search contacts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {contacts.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          No contacts yet. Contacts are created when customers send messages.
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Platform</th>
                <th className="text-left p-3">Customer Code</th>
                <th className="text-left p-3">Last Seen</th>
                <th className="text-left p-3">Notes</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{c.display_name || 'Unknown'}</td>
                  <td className="p-3"><ChannelBadge type={c.channel_id ? 'line' : 'unknown'} /></td>
                  <td className="p-3 text-gray-500">{c.customer_code || '-'}</td>
                  <td className="p-3 text-gray-500">{new Date(c.last_seen_at).toLocaleDateString()}</td>
                  <td className="p-3 text-gray-500 truncate max-w-xs">{c.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
