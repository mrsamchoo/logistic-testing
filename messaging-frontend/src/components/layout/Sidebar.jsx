import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import NotificationCenter from '../shared/NotificationCenter';

const navItems = [
  { to: '/', icon: '📊', label: 'Dashboard', end: true },
  { to: '/conversations', icon: '💬', label: 'Conversations' },
  { to: '/contacts', icon: '👥', label: 'Contacts' },
  { to: '/templates', icon: '📝', label: 'Templates' },
  { to: '/analytics', icon: '📈', label: 'พฤติกรรมลูกค้า' },
  { to: '/settings', icon: '⚙️', label: 'Settings' },
];

export default function Sidebar() {
  const admin = useAuth();

  return (
    <aside className="w-60 bg-gray-900 text-white flex flex-col h-screen shrink-0">
      <div className="p-4 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">💬 Messaging</h1>
          <p className="text-xs text-gray-400 mt-1">{admin?.org_name}</p>
        </div>
        <NotificationCenter />
      </div>

      <nav className="flex-1 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
            {admin?.username?.[0]?.toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{admin?.username}</p>
            <p className="text-xs text-gray-400">{admin?.role}</p>
          </div>
        </div>
        <a href="/admin" className="block mt-3 text-xs text-gray-400 hover:text-white transition-colors">
          ← Back to Admin
        </a>
      </div>
    </aside>
  );
}
