import { useState } from 'react';

interface Props {
  defaultAgentName: string;
  onStart: (agentName: string) => void;
}

export function ConnectScreen({ defaultAgentName, onStart }: Props) {
  const [name, setName] = useState(defaultAgentName);

  return (
    <div className="connect">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          onStart(name);
        }}
      >
        <div className="logo" aria-hidden>
          ◉
        </div>
        <h1>LiveKit Agent</h1>
        <p className="subtitle">基于 LiveKit Cloud 的实时语音 Agent · Web 端</p>

        <label className="field">
          <span>Agent 名称</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-agent"
            autoComplete="off"
            spellCheck={false}
          />
          <small>必须与你已部署 agent 的 <code>agentName</code> 一致，才会被派发进房间。</small>
        </label>

        <button type="submit" className="primary">
          开始通话
        </button>

        <p className="hint">
          开始后将请求麦克风权限。请确保 token 服务（<code>.env</code>）已配置 LiveKit Cloud 凭据，
          且对应名称的 agent 正在运行。
        </p>
      </form>
    </div>
  );
}
