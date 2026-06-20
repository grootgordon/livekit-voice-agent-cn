/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the agent name (must match your deployed agent's agentName). */
  readonly VITE_AGENT_NAME?: string;
  /** Override the token endpoint URL (defaults to the relative "/api/token"). */
  readonly VITE_TOKEN_ENDPOINT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
