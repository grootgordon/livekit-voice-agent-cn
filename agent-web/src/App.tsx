import { useState } from 'react';
import { ConnectScreen } from './components/ConnectScreen';
import { SessionView } from './components/SessionView';

const DEFAULT_AGENT_NAME = import.meta.env.VITE_AGENT_NAME ?? 'my-agent';

export default function App() {
  // Bumping sessionKey forces SessionView to fully unmount/remount, which tears
  // down the old room and creates a fresh one for the next call.
  const [sessionKey, setSessionKey] = useState(0);
  const [agentName, setAgentName] = useState(DEFAULT_AGENT_NAME);
  const [started, setStarted] = useState(false);

  if (!started) {
    return (
      <ConnectScreen
        defaultAgentName={DEFAULT_AGENT_NAME}
        onStart={(name) => {
          setAgentName(name.trim() || DEFAULT_AGENT_NAME);
          setSessionKey((k) => k + 1);
          setStarted(true);
        }}
      />
    );
  }

  return (
    <SessionView
      key={sessionKey}
      agentName={agentName}
      onDisconnected={() => setStarted(false)}
    />
  );
}
