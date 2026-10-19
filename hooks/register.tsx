// norsk-tale — lokal norsk tale-til-tekst i promptboksen.
//
// Tynn adapter: modden eier knappen, kommandoen og promptboksen. Mikrofon,
// stillhet og modellens livsløp eier lytteren (lytter/norsk_lytter.py); modell,
// SHA-sjekk og korrektur eier kjernen (kjerne/). Ingen LLM i rensingen, ingen
// sky, og modden sender aldri inn prompten. Lytteren startes ved første trykk.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { NorskAngre, NorskSelvtest, NorskStatus } from '../types'

const status = atom({ plugin: 'norsk-tale', key: 'status' } as const, 'av' as NorskStatus)
const melding = atom({ plugin: 'norsk-tale', key: 'melding' } as const, null as string | null)
const angre = atom({ plugin: 'norsk-tale', key: 'angre' } as const, null as NorskAngre | null)
const laster = atom({ plugin: 'norsk-tale', key: 'laster' } as const, false)
const selvtest = atom({ plugin: 'norsk-tale', key: 'selvtest' } as const, null as NorskSelvtest | null)
// Adressen til kalibreringsriggen. Inneholder et token, så den vises bare i
// båndet over prompten, aldri i kommandoteksten modellen leser.
const rigg = atom({ plugin: 'norsk-tale', key: 'rigg' } as const, null as string | null)

// ------------------------------------------------------------------ selvtest
// /norsk selvtest — kort akseptansetest av den ekte veien inn i promptboksen.
//
// Én diktering via snarveien (ctrl+x tab, n) eller knappen: testen setter et
// kjent prefiks i promptboksen, sjekker at teksten kom inn etter prefikset, ber
// om ett Angre-trykk og sjekker at boksen ble prefikset igjen. Så tømmes boksen
// og resultatet lagres. Ingen lyd lagres, og ingenting sendes inn til Claude.
//
// Seks-setningstesten med scoring (nektelse, tall, navn, første ord, målform,
// stopp-tid) ligger i kalibreringsriggen: /norsk kalibrer → fanen «Selvtest».
//
// I samme fil som hookene: katalogen godtar at $ bare sendes til funksjoner
// som er deklarert på toppnivå i fila som deklarerer hookene.

export const PANE = 'norsk-selvtest'
export const PREFIKS = 'TEST: '

export async function aktivTest($: EngineInterface): Promise<NorskSelvtest | null> {
  const st = await read($, selvtest)
  return st && st.aktiv ? st : null
}

export async function startSelvtest($: EngineInterface): Promise<string> {
  const boks = await $.prompt.read()
  if (boks.text.trim() !== '') {
    return 'Tøm promptboksen før selvtesten: den bruker boksen og tømmer den til slutt.'
  }
  await update($, selvtest, () => ({
    aktiv: true, steg: 'dikter' as const, innsetting: null, angre: null, fil: null, avbrutt: false, lagringsfeil: null,
  }))
  await $.prompt.fill({ text: PREFIKS, mode: 'replace' })
  return 'Selvtest startet: én diktering. Trykk ctrl+x tab og så n (eller 🎙 Norsk), si en kort setning og vent. '
    + 'Trykk deretter Angre (a). Ikke trykk Enter: ingenting sendes inn.'
}

// Kalles etter hver vellykkede innsetting. Returnerer true når den ble målt.
export async function etterInnsetting($: EngineInterface): Promise<boolean> {
  const st = await aktivTest($)
  if (!st || st.steg !== 'dikter') return false
  const boks = (await $.prompt.read()).text
  const tekst = boks.startsWith(PREFIKS) ? boks.slice(PREFIKS.length).trim() : ''
  const ok = boks.startsWith(PREFIKS) && tekst !== ''
  await update($, selvtest, x => (x ? { ...x, steg: 'angre' as const, innsetting: { ok, boks, tekst } } : x))
  return true
}

// Kalles etter Angre. Returnerer true når Angre-steget ble målt.
export async function etterAngre($: EngineInterface): Promise<boolean> {
  const st = await aktivTest($)
  if (!st || st.steg !== 'angre') return false
  const faktisk = (await $.prompt.read()).text
  await update($, selvtest, x => (x ? { ...x, angre: { ok: faktisk === PREFIKS, forventet: PREFIKS, faktisk } } : x))
  await avslutt($, false)
  return true
}

// Opptaksmappa: userConfig «opptak», ellers NORSK_TALE_OPPTAK, ellers ~/norsk-tale-opptak.
let opptakValg = ''
export function settOpptaksmappe(v: string) { opptakValg = v }

export async function opptaksmappe($: EngineInterface): Promise<string> {
  const home = (await $.env.get('HOME')) ?? ''
  const valgt = opptakValg || (await $.env.get('NORSK_TALE_OPPTAK')) || `${home}/norsk-tale-opptak`
  return valgt.startsWith('~/') ? home + valgt.slice(1) : valgt
}

// Et eksternt volum som ikke er montert, skal stoppe skrivingen: $.fs.write ville
// ellers opprettet mappa under /Volumes på intern disk.
async function montert($: EngineInterface, mappe: string): Promise<string | null> {
  try {
    const r = await $.process.run(['python3', '-I', `${$.plugin.root}/kjerne/kjerne.py`, '--krev-montert', mappe], { timeoutMs: 15000 })
    return r.exitCode === 0 ? null : (r.stderr.trim() || 'Opptaksmappa er ikke tilgjengelig.')
  } catch (feil) {
    return `Kunne ikke sjekke opptaksmappa: ${String(feil)}`
  }
}

export async function avslutt($: EngineInterface, avbrutt: boolean): Promise<string> {
  const st = await read($, selvtest)
  if (!st) return 'Ingen selvtest å avslutte.'
  await $.prompt.fill({ text: '', mode: 'replace' })
  const mappe = await opptaksmappe($)
  const stempel = new Date(await $.clock.now()).toISOString().replace(/[:]/g, '').replace(/\..*$/, '')
  const lagringsfeil = await montert($, mappe)
  const fil = lagringsfeil ? null : `${mappe}/selvtest-claude-${stempel}.json`
  const ferdig: NorskSelvtest = { ...st, aktiv: false, steg: 'ferdig', avbrutt, fil, lagringsfeil }
  const rapport = {
    norsk_tale_selvtest: 2, kilde: 'claude-code', tidspunkt: new Date(await $.clock.now()).toISOString(), avbrutt,
    oppsummering: oppsummer(ferdig), innsetting: ferdig.innsetting, angre: ferdig.angre,
    merknad: 'Ingen lyd er lagret. Seks-setningstesten med scoring kjøres i kalibreringsriggen (/norsk kalibrer → Selvtest).',
  }
  if (fil) await $.fs.write(fil, JSON.stringify(rapport, null, 2) + '\n')
  await update($, selvtest, () => ferdig)
  await $.ui.open({ id: PANE, title: 'norsk-tale selvtest' })
  const hvor = fil ? `Resultat: ${fil}` : `Resultatet ble IKKE lagret: ${lagringsfeil}`
  return avbrutt ? `Selvtesten ble avbrutt. ${hvor}` : `Selvtest ferdig. ${hvor}`
}

export type Oppsummering = { bestatt: number; sjekker: number }

export function oppsummer(st: NorskSelvtest): Oppsummering {
  const sjekk = [st.innsetting?.ok, st.angre?.ok].filter(x => x !== undefined)
  return { bestatt: sjekk.filter(Boolean).length, sjekker: sjekk.length }
}

const merke = (ok: boolean) => (ok ? '✔' : '✘')

// Tabellen som linjer, felles for panelet og testene.
export function tabell(st: NorskSelvtest): string[] {
  const o = oppsummer(st)
  const ut = [`${st.avbrutt ? 'Avbrutt' : 'Ferdig'}: ${o.bestatt} av ${o.sjekker} sjekker bestått.`]
  if (st.innsetting) {
    ut.push(`Innsetting etter prefikset ${merke(st.innsetting.ok)}  boksen var «${st.innsetting.boks}»`)
  }
  if (st.angre) ut.push(`Angre ${merke(st.angre.ok)}  forventet «${st.angre.forventet}», fikk «${st.angre.faktisk}»`)
  if (st.fil) ut.push(`Lagret: ${st.fil}`)
  if (st.lagringsfeil) ut.push(`Ikke lagret: ${st.lagringsfeil}`)
  return ut
}

// --------------------------------------------------------------- diktering

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
  | { type: 'frigjort'; etter_s: number }
  | { type: 'lytter' }
  | { type: 'tale' }
  | { type: 'behandler'; slutt: string; stillhet_ms?: number | null }
  | { type: 'tom'; slutt: string }
  | { type: 'feil'; melding: string }
  | { type: 'tekst'; slutt: string; resultat: Resultat; stillhet_ms?: number | null; malform?: string }

const TEKST: Record<NorskStatus, string> = {
  av: '',
  starter: 'Åpner mikrofonen …',
  lytter: 'Lytter på norsk. Trykk igjen for å stoppe.',
  tale: 'Hører tale. 1,5 s stillhet avslutter.',
  behandler: 'Transkriberer lokalt …',
  feil: '',
}

// Tastatur: ctrl+x tab (Claude Codes egen «abovePrompt:focus») flytter fokus til
// båndet, også når promptboksen har tekst; der trykker en bokstav knappen. Ingen
// bokstav er bundet i AbovePrompt-konteksten, så de kolliderer ikke. Esc går
// tilbake til prompten. Snarveien står i knappeteksten, for terminaler som ikke
// sender museklikk.
export const TAST = { norsk: 'n', angre: 'a', avbryt: 'x' } as const
export const FOKUS = 'ctrl+x tab'

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
let modellvalg = 'large'
let modell = ''
let whisper = ''
let malform = 'nb'
let kontroll: string | undefined
let lopenr = 0
let lever = false
let riggLever = false

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

async function kommando($: EngineInterface, ord: string) {
  if (!kontroll) return
  lopenr += 1
  await $.fs.write(`${kontroll}/${lopenr}.cmd`, ord)
}

async function settInn($: EngineInterface, hd: { slutt: string; resultat: Resultat }) {
  const r = hd.resultat
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
    await etterInnsetting($)
  } else {
    await sett($, 'feil', 'Promptboksen tok ikke imot teksten (en dialog er åpen?). Ingenting ble sendt.')
  }
}

async function hendelse($: EngineInterface, hd: Hendelse) {
  switch (hd.type) {
    case 'oppe':
    case 'modell_klar':
    case 'frigjort':
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
      await sett($, 'feil', hd.melding)
      $.ui.toast(`norsk-tale: ${hd.melding}`)
      return
    case 'tekst':
      return settInn($, hd)
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
  const argv = ['python3', '-I', `${$.plugin.root}/lytter/norsk_lytter.py`,
    '--kontroll', kontroll, ...konfigArgv()]
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
      await sett($, 'feil', `Lytteren kunne ikke startes (python3): ${String(feil)}`)
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
  const st = await read($, selvtest)
  if (st && !st.aktiv) await update($, selvtest, () => null)   // gammel oppsummering bort
  await startLytter($)
  await sett($, 'starter')
  await kommando($, 'start')
  return 'Lytter på norsk. Trykk igjen, eller 1,5 s stillhet, for å stoppe.'
}

// userConfig til kjernen, likt for lytteren og /norsk oppsett.
function konfigArgv(): string[] {
  return ['--modellvalg', modellvalg, '--modell', modell, '--whisper', whisper, '--malform', malform]
}

async function oppsett($: EngineInterface): Promise<string> {
  const argv = ['python3', '-I', `${$.plugin.root}/kjerne/kjerne.py`, '--sjekk', ...konfigArgv()]
  try {
    const r = await $.process.run(argv, { timeoutMs: 120000 })
    const rapport = JSON.parse(r.stdout) as { melding: string }
    return rapport.melding
  } catch (feil) {
    return `Oppsettsjekken kunne ikke kjøres (python3): ${String(feil)}`
  }
}

async function aapneNettleser($: EngineInterface, url: string): Promise<boolean> {
  for (const argv of [['open', url], ['xdg-open', url]]) {
    try {
      const r = await $.process.run(argv, { timeoutMs: 10000 })
      if (r.exitCode === 0) return true
    } catch {
      // prøv neste
    }
  }
  return false
}

async function startRigg($: EngineInterface): Promise<string> {
  if (riggLever) {
    const url = await read($, rigg)
    if (url) await aapneNettleser($, url)
    return 'Kalibreringsriggen kjører allerede. Adressen står over prompten.'
  }
  riggLever = true
  const argv = ['python3', '-I', `${$.plugin.root}/kalibrering/rigg.py`,
    '--modellvalg', modellvalg, '--modell', modell, '--whisper', whisper, '--opptak', await opptaksmappe($)]
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
          i = rest.indexOf('\n')
          let svar: { type?: string; url?: string; melding?: string } = {}
          try { svar = JSON.parse(linje) } catch { continue }
          if (svar.type === 'feil') {
            await sett($, 'feil', `Kalibreringsriggen startet ikke: ${svar.melding ?? 'ukjent feil'}`)
          }
          if (svar.type === 'klar' && svar.url) {
            const url = svar.url
            await update($, rigg, () => url)
            const apnet = await aapneNettleser($, url)
            $.ui.toast(apnet ? 'norsk-tale: kalibreringsriggen er åpnet i nettleseren.'
              : 'norsk-tale: åpne adressen over prompten i nettleseren.')
          }
        }
      }
    } catch (feil) {
      await sett($, 'feil', `Kalibreringsriggen kunne ikke startes (python3): ${String(feil)}`)
    } finally {
      riggLever = false
    }
    await update($, rigg, () => null)
  })().catch(() => {
    // modulen ble lastet ut; riggen stoppes med den
  })
  return 'Starter kalibreringsriggen. Den åpnes i nettleseren, og adressen står over prompten. '
    + 'Alt skjer på denne maskinen.'
}

async function angreNa($: EngineInterface): Promise<string> {
  const forrige = await read($, angre)
  if (!forrige) return 'Ingenting å angre.'
  await $.prompt.fill({ text: forrige.text, mode: 'replace' })
  await update($, angre, () => null)
  if (await etterAngre($)) return 'Prompten er satt tilbake. Selvtesten er ferdig.'
  return 'Prompten er satt tilbake.'
}

export const register: Register = (on, options) => {
  modellvalg = String(options.modellvalg ?? 'large')
  modell = String(options.modell ?? '')
  whisper = String(options.whisper ?? '')
  malform = String(options.malform ?? 'nb')
  settOpptaksmappe(String(options.opptak ?? ''))

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'norsk',
      description: 'Lokal norsk diktering: start/stopp; «angre», «av» (frigjør modellen), «oppsett», «selvtest», «kalibrer»',
      argumentHint: '[angre|av|oppsett|selvtest|kalibrer]',
      immediate: true,
    })
    return next(e)
  })

  on('command.run', { command: 'norsk' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'angre') return { text: await angreNa($) }
    if (arg === 'oppsett') return { text: await oppsett($) }
    if (arg === 'kalibrer') return { text: await startRigg($) }
    if (arg === 'selvtest') {
      if (await aktivTest($)) return { text: 'Selvtesten pågår allerede. Avbryt med /norsk selvtest avbryt.' }
      return { text: await startSelvtest($) }
    }
    if (arg === 'selvtest avbryt') {
      if (!(await aktivTest($))) return { text: 'Ingen selvtest pågår.' }
      await update($, angre, () => null)
      return { text: await avslutt($, true) }
    }
    if (arg === 'av') {
      await kommando($, 'avslutt')
      await sett($, 'av')
      return { text: 'Lytteren er stoppet og modellen frigjort.' }
    }
    if (arg !== '') return { text: `Ukjent argument «${arg}». Bruk /norsk, /norsk angre, /norsk av, /norsk oppsett, /norsk selvtest eller /norsk kalibrer.` }
    return { text: await veksle($) }
  })

  on('session.end', async ($, e, next) => {
    if (lever) await kommando($, 'avslutt')
    return next(e)
  })

  // Under selvtesten sendes ingenting inn: Enter på «TEST: …» stoppes her.
  // Ellers gjør en ny innsending den gamle angre-tilstanden meningsløs.
  on('prompt.submit', async ($, e, next) => {
    if (!e.command && (await aktivTest($))) {
      return { drop: 'Selvtesten pågår, og ingenting sendes inn. Avbryt med /norsk selvtest avbryt.' }
    }
    await update($, angre, () => null)
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const st = await read($, selvtest)
    if (!st) return <Text dimColor>Ingen selvtest er kjørt i denne økten.</Text>
    return (
      <Box flexDirection="column">
        {tabell(st).map((l, i) => <Text key={`l${i}`} color={l.includes('✘') || l.trimStart().startsWith('bom') ? 'red' : undefined}>{l}</Text>)}
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const s = await read($, status)
    const m = await read($, melding)
    const a = await read($, angre)
    const l = await read($, laster)
    const st = await read($, selvtest)
    const riggUrl = await read($, rigg)
    const aktiv = s === 'lytter' || s === 'tale' || s === 'starter'
    const linje = s === 'feil' ? m ?? 'Ukjent feil.' : TEKST[s] + (l && aktiv ? ' Modellen lastes …' : '')
    const knapper = (
      <Box>
        <Button key="norsk" hotkey={TAST.norsk} label={`${aktiv ? '■ Stopp' : '🎙 Norsk'} (${FOKUS}, ${TAST.norsk})`}
          onPress={() => veksle($)} />
        {a !== null && <Button key="angre" hotkey={TAST.angre} label={`Angre (${TAST.angre})`} onPress={() => angreNa($)} />}
        {st?.aktiv && <Button key="avbryt" hotkey={TAST.avbryt} label={`Avbryt test (${TAST.avbryt})`}
          onPress={() => avslutt($, true)} />}
        {linje !== '' && <Text color={s === 'feil' ? 'red' : undefined} dimColor={s !== 'feil'}> {linje}</Text>}
      </Box>
    )
    const riggLinje = riggUrl ? <Text key="rigg" dimColor>Kalibreringsriggen: {riggUrl}</Text> : null
    if (!st) return riggLinje ? <Box flexDirection="column">{knapper}{riggLinje}</Box> : knapper
    let tekst1 = ''
    let tekst2 = ''
    if (st.aktiv && st.steg === 'dikter') {
      tekst1 = `Selvtest – trykk ${FOKUS} og så ${TAST.norsk} (eller 🎙 Norsk), si en kort setning og vent.`
      tekst2 = 'Ikke trykk Enter: ingenting sendes inn. Seks-setningstesten ligger i /norsk kalibrer → Selvtest.'
    } else if (st.aktiv) {
      tekst1 = `Selvtest – trykk Angre (${TAST.angre}).`
      tekst2 = `Testen sjekker at prompten blir «${PREFIKS}» igjen, og tømmer den etterpå.`
    } else {
      const o = oppsummer(st)
      tekst1 = `Selvtest ${st.avbrutt ? 'avbrutt' : 'ferdig'}: ${o.bestatt} av ${o.sjekker} sjekker bestått.`
      tekst2 = st.fil ? `Detaljer i panelet «norsk-tale selvtest». Lagret: ${st.fil}` : `Resultatet ble ikke lagret: ${st.lagringsfeil ?? 'ukjent'}`
    }
    return (
      <Box flexDirection="column">
        {knapper}
        <Text key="selvtest1">{tekst1}</Text>
        <Text key="selvtest2" dimColor>{tekst2}</Text>
        {riggLinje}
      </Box>
    )
  })
}
