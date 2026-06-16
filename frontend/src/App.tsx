import { useEffect } from 'react';
import { ChatShell } from './components/ChatShell';
import { Sidebar } from './components/Sidebar';
import { useChatStore } from './hooks/useChatStore';

export default function App() {
  const init = useChatStore((state) => state.init);

  useEffect(() => {
    void init();
  }, [init]);

  return (
    <div className="app-layout">
      <Sidebar />
      <ChatShell />
    </div>
  );
}
