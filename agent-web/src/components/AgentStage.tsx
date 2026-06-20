import { BarVisualizer, RoomAudioRenderer, useAgent, type UseSessionReturn } from '@livekit/components-react';
import type { AgentState } from '@livekit/components-react';
import { Controls } from './Controls';

interface Props {
  session: UseSessionReturn;
  onDisconnected: () => void;
}

const STATE_LABEL: Record<AgentState, string> = {
  connecting: '连接房间中…',
  'pre-connect-buffering': '准备就绪，正在聆听…',
  initializing: 'Agent 初始化中…',
  idle: '待命',
  listening: '聆听中',
  thinking: '思考中…',
  speaking: '回答中…',
  disconnected: '已结束',
  failed: '出错',
};

const STATE_TONE: Record<AgentState, string> = {
  connecting: 'tone-pending',
  'pre-connect-buffering': 'tone-active',
  initializing: 'tone-pending',
  idle: 'tone-idle',
  listening: 'tone-active',
  thinking: 'tone-thinking',
  speaking: 'tone-active',
  disconnected: 'tone-idle',
  failed: 'tone-failed',
};

export function AgentStage({ session, onDisconnected }: Props) {
  const agent = useAgent();
  const state = agent.state;
  const failed = state === 'failed' && agent.failureReasons && agent.failureReasons.length > 0;

  return (
    <section className="stage">
      {/* Plays all remote audio — i.e. the agent's speech. */}
      <RoomAudioRenderer />

      <div className={`badge ${STATE_TONE[state]}`}>
        <span className="dot" />
        {STATE_LABEL[state]}
      </div>

      <div className="visualizer-wrap">
        <BarVisualizer
          track={agent.microphoneTrack}
          state={state}
          barCount={9}
          style={{ width: '100%', height: 220 }}
        />
      </div>

      {failed ? (
        <p className="error">
          {agent.failureReasons!.join('；')}
          <br />
          <small>请确认对应名称的 agent 已部署并正在运行。</small>
        </p>
      ) : (
        <p className="caption">
          {agent.canListen
            ? '说话或输入文字开始对话'
            : agent.isPending
              ? '正在与 Agent 建立连接…'
              : ''}
        </p>
      )}

      <Controls session={session} onDisconnected={onDisconnected} />
    </section>
  );
}
