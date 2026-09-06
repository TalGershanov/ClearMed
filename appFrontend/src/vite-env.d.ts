/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for API requests. Empty string means same-origin (production). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
