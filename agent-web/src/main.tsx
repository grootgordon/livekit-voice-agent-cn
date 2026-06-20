import ReactDOM from 'react-dom/client';
import App from './App';

// LiveKit Components base styles + our app styles.
import '@livekit/components-styles';
import './index.css';

// NOTE: Intentionally NOT wrapped in <React.StrictMode>. StrictMode double-invokes
// effects in development, which would call session.start()/end() twice and can
// race the WebRTC negotiation. The session lifecycle is managed explicitly.
ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
