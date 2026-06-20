// ─────────────────────────────────────────────────────────────────────────────
// LiveKit token server (LiveKit Cloud endpoint)
//
// Implements the standardized LiveKit token endpoint that the browser-side
// `TokenSource.endpoint('/api/token')` (from livekit-client) calls. It mints a
// short-lived JWT joining a room, and—crucially—passes through `room_config`,
// which the client SDK fills with the agent dispatch so LiveKit Cloud auto-joins
// your agent the moment the user connects.
//
// Reference: https://docs.livekit.io/frontends/build/authentication/endpoint.md
// ─────────────────────────────────────────────────────────────────────────────
import express from 'express';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { AccessToken, RoomAgentDispatch, RoomConfiguration } from 'livekit-server-sdk';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Minimal, dependency-free .env loader (so we don't need `dotenv`).
// Only sets vars that aren't already present in the environment.
function loadEnv() {
  const envPath = path.resolve(__dirname, '../.env');
  if (!existsSync(envPath)) return;
  const text = readFileSync(envPath, 'utf8');
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const m = trimmed.match(/^([\w.-]+)\s*=\s*(.*)?$/);
    if (!m) continue;
    const [, key, raw] = m;
    if (key in process.env) continue;
    let value = (raw ?? '').trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}
// Parse a simple KEY=VALUE env file into an object (no dotenv dependency).
function parseEnvFile(filePath) {
  const out = {};
  const text = readFileSync(filePath, 'utf8');
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const m = trimmed.match(/^([\w.-]+)\s*=\s*(.*)?$/);
    if (!m) continue;
    let value = (m[2] ?? '').trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[m[1]] = value;
  }
  return out;
}

// Resolve the active LiveKit transport (Cloud ⇄ local) from the shared root
// `.livekit.env`. LIVEKIT_PROFILE picks the preset (cloud|local); its URL/KEY/SECRET
// become the canonical env vars consumed below. The profile is the single source of
// truth — flipping one line in .livekit.env switches both this token server and the agent.
function resolveLiveKitProfile() {
  // Walk up from this file to find the shared .livekit.env at the repo root.
  let dir = __dirname;
  const root = path.parse(dir).root;
  let envPath = null;
  while (dir !== root) {
    const candidate = path.join(dir, '.livekit.env');
    if (existsSync(candidate)) {
      envPath = candidate;
      break;
    }
    dir = path.dirname(dir);
  }
  if (!envPath) {
    console.warn(
      '⚠️  未找到根 .livekit.env — 沿用环境变量/项目 .env 里的 LIVEKIT_URL/API_KEY/API_SECRET。',
    );
    return;
  }
  const cfg = parseEnvFile(envPath);
  const profile = (cfg.LIVEKIT_PROFILE || process.env.LIVEKIT_PROFILE || 'cloud').toLowerCase();
  const suffix = profile === 'local' ? 'LOCAL' : 'CLOUD';
  const url = cfg[`LIVEKIT_URL_${suffix}`] || process.env.LIVEKIT_URL;
  const key = cfg[`LIVEKIT_API_KEY_${suffix}`] || process.env.LIVEKIT_API_KEY;
  const secret = cfg[`LIVEKIT_API_SECRET_${suffix}`] || process.env.LIVEKIT_API_SECRET;
  if (url) process.env.LIVEKIT_URL = url;
  if (key) process.env.LIVEKIT_API_KEY = key;
  if (secret) process.env.LIVEKIT_API_SECRET = secret;
  process.env.LIVEKIT_PROFILE = profile;
  console.log(`🛰  LiveKit transport = ${profile.toUpperCase()}  (${url ?? '(no url)'})  [${envPath}]`);
}
loadEnv();
resolveLiveKitProfile();

const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL ?? '';
const PORT = Number(process.env.PORT ?? 8787);

if (!API_KEY || !API_SECRET) {
  console.warn(
    '\n⚠️  未检测到 LIVEKIT_API_KEY / LIVEKIT_API_SECRET。\n' +
      '   请复制 .env.example 为 .env 并填入你的 LiveKit Cloud 凭据。\n',
  );
}

const app = express();
app.use(express.json());

// Standard LiveKit token endpoint.
app.post('/api/token', async (req, res) => {
  try {
    if (!API_KEY || !API_SECRET) {
      return res
        .status(500)
        .json({ error: 'Server is missing LIVEKIT_API_KEY / LIVEKIT_API_SECRET' });
    }

    const body = req.body ?? {};

    // Defaults if the client (or caller) omits them.
    const roomName = body.room_name || `room-${Math.random().toString(36).slice(2, 10)}`;
    const identity = body.participant_identity || `user-${Math.random().toString(36).slice(2, 10)}`;
    const name = body.participant_name || 'Guest';

    const at = new AccessToken(API_KEY, API_SECRET, {
      identity,
      name,
      ttl: '10m',
    });

    at.addGrant({
      roomJoin: true,
      room: roomName,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    });

    if (body.participant_attributes) {
      at.attributes = body.participant_attributes;
    }

    // The livekit-client Session API packages the requested agent dispatch into
    // `room_config` and sends it as snake_case ({ agents: [{ agent_name }] }). The
    // protobuf RoomAgentDispatch only maps camelCase ({ agentName }), so rebuild it
    // explicitly — otherwise the agent name is dropped and the dispatch becomes a
    // default (agent="") dispatch that never matches the named worker.
    if (body.room_config && Array.isArray(body.room_config.agents) && body.room_config.agents.length) {
      const agents = body.room_config.agents.map((a) => {
        const dispatch = new RoomAgentDispatch({
          agentName: a.agentName ?? a.agent_name,
        });
        if (a.metadata) dispatch.metadata = a.metadata;
        return dispatch;
      });
      at.roomConfig = new RoomConfiguration({ agents });
    } else if (body.room_config) {
      at.roomConfig = new RoomConfiguration(body.room_config);
    }

    const participantToken = await at.toJwt();

    return res.status(201).json({
      server_url: LIVEKIT_URL,
      participant_token: participantToken,
    });
  } catch (err) {
    console.error('[/api/token] error:', err);
    return res.status(500).json({ error: 'Failed to generate token' });
  }
});

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    configured: Boolean(API_KEY && API_SECRET),
    profile: process.env.LIVEKIT_PROFILE ?? '(unset)',
    livekitUrl: LIVEKIT_URL || '(unset)',
  });
});

// Production: serve the built client (output of `vite build` → dist/).
// Uses middleware (not a wildcard route) so it works the same on Express 4 and 5.
const distDir = path.resolve(__dirname, '../dist');
if (existsSync(distDir)) {
  app.use(express.static(distDir));
  app.use((req, res, next) => {
    if (req.method !== 'GET' || req.path.startsWith('/api')) return next();
    const indexFile = path.join(distDir, 'index.html');
    if (existsSync(indexFile)) return res.sendFile(indexFile);
    return next();
  });
}

app.listen(PORT, () => {
  console.log(`\n🟢 Token server:  http://localhost:${PORT}`);
  console.log(`   POST /api/token   · GET /api/health`);
  if (existsSync(distDir)) {
    console.log(`🌐 Serving built client — open http://localhost:${PORT}\n`);
  } else {
    console.log(`💬 Dev mode — run the Vite client separately (npm run dev:web)\n`);
  }
});
