export type NorskStatus = 'av' | 'starter' | 'lytter' | 'tale' | 'behandler' | 'feil'
export type NorskAngre = { text: string; cursor: number }

export type NorskSetning = { id: string; malform: string; setning: string }

export type NorskScore = {
  id: string
  setning: string
  utdata: string
  elementer: { type: string; former: string[]; treff: boolean; funnet: string | null }[]
  forste_innholdsord: { ord: string | null; treff: boolean }
  malform: { forventet: string; utdata: string; funn: boolean }
  bom: { type: string; fasit: string; utdata: string }[]
  bestatt: boolean
  wer: number
  cer: number
}

export type NorskSelvtestRad = {
  id: string
  setning: string
  malform: string
  prefiks_ok: boolean
  boks: string
  utdata: string
  verbatim: string
  slutt: string
  malform_valgt: string
  stillhet_ms: number | null
  stopp_til_tekst_ms: number | null
  score: NorskScore | null
  scorefeil: string | null
}

export type NorskSelvtest = {
  aktiv: boolean
  steg: number
  setninger: NorskSetning[]
  resultater: NorskSelvtestRad[]
  angre: { ok: boolean; forventet: string; faktisk: string } | null
  fil: string | null
  avbrutt: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'norsk-tale': {
      status: NorskStatus
      melding: string | null
      angre: NorskAngre | null
      laster: boolean
      selvtest: NorskSelvtest | null
    }
  }
}
