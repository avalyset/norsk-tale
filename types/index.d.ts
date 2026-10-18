export type NorskStatus = 'av' | 'starter' | 'lytter' | 'tale' | 'behandler' | 'feil'
export type NorskAngre = { text: string; cursor: number }

declare module 'claude-code' {
  interface PluginState {
    'norsk-tale': {
      status: NorskStatus
      melding: string | null
      angre: NorskAngre | null
      laster: boolean
    }
  }
}
