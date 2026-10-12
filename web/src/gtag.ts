declare global {
  function gtag(command: 'event' | 'config' | 'js', eventName: string, params?: Record<string, unknown>): void;
}
export {};