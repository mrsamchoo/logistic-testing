import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { SocketProvider } from './contexts/SocketContext';
import { Toaster } from 'react-hot-toast';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';
import ConversationsPage from './pages/ConversationsPage';
import ContactsPage from './pages/ContactsPage';
import TemplatesPage from './pages/TemplatesPage';
import SettingsPage from './pages/SettingsPage';
import ChannelSettingsPage from './pages/ChannelSettingsPage';
import AISettingsPage from './pages/AISettingsPage';
import TeamSettingsPage from './pages/TeamSettingsPage';
import CustomerAnalyticsPage from './pages/CustomerAnalyticsPage';

export default function App() {
  return (
    <BrowserRouter basename="/messaging">
      <AuthProvider>
        <SocketProvider>
          <Toaster position="top-right" />
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="conversations" element={<ConversationsPage />} />
              <Route path="conversations/:id" element={<ConversationsPage />} />
              <Route path="contacts" element={<ContactsPage />} />
              <Route path="templates" element={<TemplatesPage />} />
              <Route path="analytics" element={<CustomerAnalyticsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="settings/channels" element={<ChannelSettingsPage />} />
              <Route path="settings/ai" element={<AISettingsPage />} />
              <Route path="settings/team" element={<TeamSettingsPage />} />
            </Route>
          </Routes>
        </SocketProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
