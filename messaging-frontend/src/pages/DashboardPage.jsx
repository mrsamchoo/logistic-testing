import { useState, useEffect } from 'react';
import { api } from '../api/client';

const LineIcon = () => (
  <svg viewBox="0 0 24 24" className="w-8 h-8" fill="#06C755">
    <path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314"/>
  </svg>
);

export default function DashboardPage() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get('/analytics/overview').then(setStats);
  }, []);

  if (!stats) return <div className="p-6">Loading...</div>;

  const cards = [
    { label: 'Total Conversations', value: stats.total_conversations, icon: '💬', color: 'bg-blue-50 text-blue-700' },
    { label: 'Open', value: stats.open_conversations, icon: '📩', color: 'bg-yellow-50 text-yellow-700' },
    { label: 'Total Messages', value: stats.total_messages, icon: '✉️', color: 'bg-green-50 text-green-700' },
    { label: 'รายชื่อ', value: stats.total_contacts, icon: '👥', color: 'bg-purple-50 text-purple-700' },
    { label: 'LINE', value: stats.channels, icon: 'line', color: 'bg-green-50 text-green-700' },
    { label: 'ข้อความใหม่', value: stats.unread_messages, icon: '🔔', color: 'bg-red-50 text-red-700' },
  ];

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <div key={card.label} className={`rounded-xl p-5 ${card.color}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm opacity-75">{card.label}</p>
                <p className="text-3xl font-bold mt-1">{card.value}</p>
              </div>
              {card.icon === 'line' ? <LineIcon /> : <span className="text-3xl">{card.icon}</span>}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 bg-white rounded-xl p-6 shadow-sm border">
        <h2 className="text-lg font-semibold mb-4">Quick Start</h2>
        <div className="space-y-3 text-sm text-gray-600">
          {stats.channels === 0 && (
            <p>📡 <a href="/messaging/settings/channels" className="text-blue-600 hover:underline">Connect your first channel</a> (LINE, Facebook, or Instagram)</p>
          )}
          <p>⚙️ <a href="/messaging/settings/ai" className="text-blue-600 hover:underline">Configure AI provider</a> for smart reply suggestions</p>
          <p>📝 <a href="/messaging/templates" className="text-blue-600 hover:underline">Create message templates</a> for quick replies</p>
        </div>
      </div>
    </div>
  );
}
