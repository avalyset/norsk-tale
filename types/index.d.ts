export type NorskStatus = 'av' | 'starter' | 'lytter' | 'tale' | 'behandler' | 'feil'
export type NorskAngre = { text: string; cursor: number }

export type NorskSelvtest = {
  aktiv: boolean
  steg: 'dikter' | 'angre' | 'ferdig'
  innsetting: { ok: boolean; boks: string; tekst: string } | null
  angre: { ok: boolean; forventet: string; faktisk: string } | null
  fil: string | null
  avbrutt: boolean
  lagringsfeil: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'norsk-tale': {
      status: NorskStatus
      melding: string | null
      angre: NorskAngre | null
      laster: boolean
      selvtest: NorskSelvtest | null
      rigg: string | null
    }
  }
}
