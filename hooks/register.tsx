// norsk-tale — lokal norsk tale-til-tekst i promptboksen.
//
// Tynn adapter: modden eier knappen, kommandoen og promptboksen. Mikrofon og
// stillhet eier lytteren (lytter/norsk_lytter.py); modell, SHA-sjekk og
// korrektur eier NORSKRIBER-kjernen. Ingen LLM i rensingen, ingen sky, og
// modden sender aldri inn prompten.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { NorskAngre, NorskStatus } from '../types'

const status = atom({ plugin: 'norsk-tale', key: 'status' } as const, 'av' as NorskStatus)
const melding = atom({ plugin: 'norsk-tale', key: 'melding' } as const, null as string | null)
const angre = atom({ plugin: 'norsk-tale', key: 'angre' } as const, null as NorskAngre | null)
const laster = atom({ plugin: 'norsk-tale', key: 'laster' } as const, false)

type Resultat = {
  verbatim: string
  korrigert: string
  substitusjonslogg: unknown[]
  modell_sha256: string
  versjon: string
}

type Hendelse =
  | { type: 'oppe'; feil: string | null }
  | { type: 'laster' }
  | { type: 'modell_klar'; modell_sha256: string }
  | { type: 'lytter' }
  | { type: 'tale' }
  | { type: 'behandler'; slutt: string }
  | { type: 'tom'; slutt: string }
  | { type: 'feil'; melding: string }
  | { type: 'tekst'; slutt: string; resultat: Resultat }

const TEKST: Record<NorskStatus, string> = {
  av: '',
  starter: 'Åpner mikrofonen …',
  lytter: 'Lytter på norsk. Trykk igjen for å stoppe.',
  tale: 'Hører tale. 1,5 s stillhet avslutter.',
  behandler: 'Transkriberer lokalt …',
  feil: '',
}

// Mellomrom der teksten møter det brukeren alt har skrevet, så ord ikke limes.
export function medMellomrom(utkast: string, markor: number, tekst: string): string {
  const for_ = utkast.slice(0, markor)
  const etter = utkast.slice(markor)
  let t = tekst
  if (for_ && !/\s$/.test(for_)) t = ' ' + t
  if (etter && !/^\s/.test(etter)) t = t + ' '
  return t
}

// Modulens egen tilstand: nullstilles ved omlasting, som lytterprosessen.
let python = 'python3'
let norskriber = '~/norskriber'
let kontroll: string | undefined
let lopenr = 0
let lever = false

async function sett($: EngineInterface, s: NorskStatus, m: string | null = null) {
  await update($, status, () => s)
  await update($, melding, () => m)
}

// Kontrollkatalogen er per økt og bestemmes ved første behov.
async function sikreKontroll($: EngineInterface): Promise<string> {
  if (!kontroll) {
    const tmp = (await $.env.get('TMPDIR')) ?? '/tmp'
    kontroll = `${tmp.replace(/\/$/, '')}/norsk-tale-${await $.session.id()}`
  }
  return kontroll
}

async function kommando($: EngineInterface, ord: 'start' | 'stopp' | 'avslutt') {
  if (!kontroll) return
  lopenr += 1
  await $.fs.write(`${kontroll}/${lopenr}.cmd`, ord)
}

async function settInn($: EngineInterface, r: Resultat) {
  // Kjernen gir én linje per whisper-segment; i promptboksen er det løpende tekst.
  const tekst = r.korrigert.replace(/\s*\n\s*/g, ' ').trim()
  if (!tekst) {
    await sett($, 'av')
    $.ui.toast('norsk-tale: hørte ingen ord.')
    return
  }
  const boks = await $.prompt.read()
  const fylt = await $.prompt.fill({
    text: medMellomrom(boks.text, boks.cursor, tekst),
    mode: 'insert',
  })
  if (fylt.isFilled) {
    await update($, angre, () => ({ text: boks.text, cursor: boks.cursor }))
    await sett($, 'av')
  } else {
    await sett($, 'feil', 'Promptboksen tok ikke imot teksten (en dialog er åpen?). Ingenting ble sendt.')
  }
}

async function hendelse($: EngineInterface, h: Hendelse) {
  switch (h.type) {
    case 'oppe':
    case 'modell_klar':
      await update($, laster, () => false)
      return
    case 'laster':
      await update($, laster, () => true)
      return
    case 'lytter':
      return sett($, 'lytter')
    case 'tale':
      return sett($, 'tale')
    case 'behandler':
      return sett($, 'behandler')
    case 'tom':
      await sett($, 'av')
      $.ui.toast('norsk-tale: hørte ingen tale.')
      return
    case 'feil':
      await update($, laster, () => false)
      await sett($, 'feil', h.melding)
      $.ui.toast(`norsk-tale: ${h.melding}`)
      return
    case 'tekst':
      return settInn($, h.resultat)
  }
}

// En linje lytteren skrev som ikke er JSON, blir en feil i stedet for å drepe løkka.
function tolk(linje: string): Hendelse {
  try {
    return JSON.parse(linje) as Hendelse
  } catch {
    return { type: 'feil', melding: `Uventet utdata fra lytteren: ${linje.slice(0, 200)}` }
  }
}

async function startLytter($: EngineInterface) {
  if (lever) return
  lever = true
  const kontroll = await sikreKontroll($)
  const argv = [python, '-I', `${$.plugin.root}/lytter/norsk_lytter.py`,
    '--kontroll', kontroll, '--norskriber', norskriber]
  void (async () => {
    let rest = ''
    try {
      for await (const { stream, text } of $.process.spawn({ argv })) {
        if (stream !== 'stdout') continue
        rest += text
        let i = rest.indexOf('\n')
        while (i >= 0) {
          const linje = rest.slice(0, i).trim()
          rest = rest.slice(i + 1)
          if (linje) await hendelse($, tolk(linje))
          i = rest.indexOf('\n')
        }
      }
    } catch (feil) {
      await sett($, 'feil', `Lytteren kunne ikke startes med «${python}»: ${String(feil)}`)
    } finally {
      lever = false
    }
    const s = await read($, status)
    // Et trykk som kom mens en lytter var på vei ned: kommandofila ligger
    // igjen i kontrollkatalogen, og den nye lytteren leser den.
    if (s === 'starter') await startLytter($)
    else if (s === 'lytter' || s === 'tale' || s === 'behandler') {
      await sett($, 'feil', 'Lytteren stoppet uventet.')
    }
  })().catch(() => {
    // Modulen ble lastet ut (omlasting, øktslutt) mens løkka gikk: da er
    // tilstanden ikke lenger vår å skrive, og lytteren er drept med den.
  })
}

async function veksle($: EngineInterface): Promise<string> {
  const s = await read($, status)
  if (s === 'lytter' || s === 'tale' || s === 'starter') {
    await kommando($, 'stopp')
    return 'Stopper opptaket.'
  }
  if (s === 'behandler') return 'Transkriberer fortsatt.'
  await startLytter($)
  await sett($, 'starter')
  await kommando($, 'start')
  return 'Lytter på norsk. Trykk igjen, eller 1,5 s stillhet, for å stoppe.'
}

async function angreNa($: EngineInterface): Promise<string> {
  const forrige = await read($, angre)
  if (!forrige) return 'Ingenting å angre.'
  await $.prompt.fill({ text: forrige.text, mode: 'replace' })
  await update($, angre, () => null)
  return 'Prompten er satt tilbake.'
}

export const register: Register = (on, options) => {
  python = String(options.python ?? 'python3')
  norskriber = String(options.norskriber ?? '~/norskriber')

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'norsk',
      description: 'Lokal norsk diktering: start/stopp, «angre» setter prompten tilbake, «av» laster ut modellen',
      argumentHint: '[angre|av]',
      immediate: true,
    })
    await startLytter($)
    return next(e)
  })

  on('command.run', { command: 'norsk' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'angre') return { text: await angreNa($) }
    if (arg === 'av') {
      await kommando($, 'avslutt')
      await sett($, 'av')
      return { text: 'Lytteren er stoppet og modellen lastet ut.' }
    }
    if (arg !== '') return { text: `Ukjent argument «${arg}». Bruk /norsk, /norsk angre eller /norsk av.` }
    return { text: await veksle($) }
  })

  on('session.end', async ($, e, next) => {
    await kommando($, 'avslutt')
    return next(e)
  })

  // En ny innsending gjør den gamle angre-tilstanden meningsløs.
  on('prompt.submit', async ($, e, next) => {
    await update($, angre, () => null)
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const s = await read($, status)
    const m = await read($, melding)
    const a = await read($, angre)
    const l = await read($, laster)
    const aktiv = s === 'lytter' || s === 'tale' || s === 'starter'
    const linje = s === 'feil' ? m ?? 'Ukjent feil.' : TEKST[s] + (l && aktiv ? ' Modellen lastes …' : '')
    return (
      <Box>
        <Button key="norsk" label={aktiv ? '■ Stopp' : '🎙 Norsk'} onPress={() => veksle($)} />
        {a !== null && <Button key="angre" label="Angre" onPress={() => angreNa($)} />}
        {linje !== '' && <Text color={s === 'feil' ? 'red' : undefined} dimColor={s !== 'feil'}> {linje}</Text>}
      </Box>
    )
  })
}
