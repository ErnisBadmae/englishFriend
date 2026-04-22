declare module 'https://cdn.jsdelivr.net/npm/@mintplex-labs/piper-tts-web@1.0.3/dist/piper-tts-web.js' {
  export function predict(options: { text: string; voiceId: string }): Promise<Blob>;
  export function download(
    voiceId: string,
    onProgress?: (progress: { loaded: number; total: number }) => void
  ): Promise<void>;
  export function stored(): Promise<string[]>;
}
