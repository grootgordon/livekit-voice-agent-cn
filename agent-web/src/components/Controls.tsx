import { useEffect, useState } from 'react';
import { ParticipantEvent } from 'livekit-client';
import type { UseSessionReturn } from '@livekit/components-react';

interface Props {
  session: UseSessionReturn;
  onDisconnected: () => void;
}

export function Controls({ session, onDisconnected }: Props) {
  const room = session.room;
  const [micOn, setMicOn] = useState(false);

  // Keep the mic button in sync with the actual local track state (the session
  // auto-publishes the mic early for the pre-connect audio buffer).
  useEffect(() => {
    const sync = () => setMicOn(Boolean(room.localParticipant.isMicrophoneEnabled));
    sync();

    const p = room.localParticipant;
    const on = () => sync();
    p.on(ParticipantEvent.LocalTrackPublished, on);
    p.on(ParticipantEvent.LocalTrackUnpublished, on);
    p.on(ParticipantEvent.TrackMuted, on);
    p.on(ParticipantEvent.TrackUnmuted, on);

    return () => {
      p.off(ParticipantEvent.LocalTrackPublished, on);
      p.off(ParticipantEvent.LocalTrackUnpublished, on);
      p.off(ParticipantEvent.TrackMuted, on);
      p.off(ParticipantEvent.TrackUnmuted, on);
    };
  }, [room]);

  const toggleMic = () => {
    const next = !room.localParticipant.isMicrophoneEnabled;
    void room.localParticipant.setMicrophoneEnabled(next);
    setMicOn(next);
  };

  const leave = () => {
    void session.end();
    onDisconnected();
  };

  return (
    <div className="controls">
      <button className={`ctrl ${micOn ? 'on' : 'off'}`} onClick={toggleMic}>
        {micOn ? '🎙️ 麦克风' : '🔇 已静音'}
      </button>
      <button className="ctrl danger" onClick={leave}>
        ⏹ 挂断
      </button>
    </div>
  );
}
