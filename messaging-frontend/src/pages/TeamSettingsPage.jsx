import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Link } from 'react-router-dom';

export default function TeamSettingsPage() {
  const [members, setMembers] = useState([]);

  useEffect(() => {
    api.get('/team').then(setMembers);
  }, []);

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/settings" className="hover:text-blue-600">Settings</Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">Team</span>
      </div>

      <h1 className="text-2xl font-bold text-gray-800 mb-6">Team Members</h1>

      {members.length === 0 ? (
        <div className="text-center text-gray-400 py-12">No team members found.</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left p-3">User</th>
                <th className="text-left p-3">Role</th>
                <th className="text-left p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="border-t hover:bg-gray-50">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-xs font-bold text-blue-700">
                        {m.username?.[0]?.toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium">{m.display_name || m.username}</p>
                        <p className="text-xs text-gray-400">@{m.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      m.role === 'super_admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {m.role}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Active</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
