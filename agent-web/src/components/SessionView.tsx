import { useEffect, useMemo, useRef } from 'react';
import { SessionProvider, useSession, type UseSessionReturn } from '@livekit/components-react';
import { TokenSource } from 'livekit-client';
import { AgentStage } from './AgentStage';
import { ChatPanel } from './ChatPanel';

const TOKEN_ENDPOINT = import.meta.env.VITE_TOKEN_ENDPOINT ?? '/api/token';

interface Props {
  agentName: string;
  onDisconnected: () => void;
}

export function SessionView({ agentName, onDisconnected }: Props) {
  // A fresh, stable token source + room name per mounted session. Each call gets
  // its own isolated room so agents dispatch independently.
  const tokenSource = useMemo(() => TokenSource.endpoint(TOKEN_ENDPOINT), []);
  const roomName = useMemo(() => `room-${Math.random().toString(36).slice(2, 10)}`, []);
  const options = useMemo(() => ({ agentName, roomName }), [agentName, roomName]);

  const session = useSession(tokenSource, options);

  // Start on mount, end on unmount. Captured in a ref so the cleanup always acts
  // on the current session regardless of referential identity.
  const sessionRef = useRef<UseSessionReturn>(session);
  sessionRef.current = session;

  useEffect(() => {
    void sessionRef.current.start();
    return () => {
      void sessionRef.current.end();
    };
  }, []);

  return (
    <SessionProvider session={session}>
      <div className="app-shell" data-lk-theme="default">
        <header className="topbar">
          <span className="brand">◉ LiveKit Agent · Web</span>
          <span className="room" title="当前房间名">
            房间 {roomName}
          </span>
        </header>

        <main className="main">
          <AgentStage session={session} onDisconnected={onDisconnected} />
          <ChatPanel />
        </main>
      </div>
    </SessionProvider>
  );
}
