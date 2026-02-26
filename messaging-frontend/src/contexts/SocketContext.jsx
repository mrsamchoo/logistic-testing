import { createContext, useContext, useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { useAuth } from './AuthContext';

const SocketContext = createContext(null);

export function SocketProvider({ children }) {
  const [socket, setSocket] = useState(null);
  const admin = useAuth();

  useEffect(() => {
    if (!admin) return;

    const s = io(window.location.origin, {
      transports: ['websocket', 'polling'],
    });

    s.on('connect', () => {
      console.log('Socket connected');
      s.emit('join_org', { org_id: admin.org_id });
    });

    s.on('disconnect', () => {
      console.log('Socket disconnected');
    });

    setSocket(s);

    return () => {
      s.disconnect();
    };
  }, [admin]);

  return (
    <SocketContext.Provider value={socket}>
      {children}
    </SocketContext.Provider>
  );
}

export const useSocket = () => useContext(SocketContext);
