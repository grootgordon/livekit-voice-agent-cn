import { useEffect, useRef, useState } from 'react';
import { useAgent, useSessionMessages } from '@livekit/components-react';

export function ChatPanel() {
  const { messages, send, isSending } = useSessionMessages();
  const agent = useAgent();
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || isSending) return;
    setText('');
    try {
      await send(t);
    } catch (err) {
      console.error('send failed', err);
    }
  };

  const showTyping = agent.state === 'thinking';

  return (
    <aside className="chat">
      <header className="chat-head">
        <span>对话记录</span>
        <small>语音转写 + 文字消息</small>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="empty">语音或文字开始对话，内容会实时显示在这里。</p>
        )}

        {messages.map((m) => {
          const mine = Boolean(m.from?.isLocal);
          return (
            <div key={m.id} className={`bubble ${mine ? 'mine' : 'agent'}`}>
              <span className="role">{mine ? '我' : 'Agent'}</span>
              <span className="text">{m.message}</span>
            </div>
          );
        })}

        {showTyping && (
          <div className="bubble agent typing">
            <span className="role">Agent</span>
            <span className="dots">
              <i /> <i /> <i />
            </span>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={agent.canListen ? '输入文字…' : '连接建立后可输入文字…'}
          disabled={!agent.canListen}
          autoComplete="off"
        />
        <button type="submit" disabled={!text.trim() || isSending || !agent.canListen}>
          {isSending ? '…' : '发送'}
        </button>
      </form>
    </aside>
  );
}
