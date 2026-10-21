// norsk-tale — lokal norsk tale-til-tekst i promptboksen.
//
// Tynn adapter: modden eier knappen, kommandoen og promptboksen. Mikrofon,
// stillhet og modellens livsløp eier lytteren (lytter/norsk_lytter.py), som
// kjører i pluginens MCP-server (mcp/server.py); modell, SHA-sjekk og korrektur
// eier kjernen (kjerne/). Modden starter ingen prosesser, bruker ingen LLM i
// rensingen og sender aldri inn prompten.

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

export async function avslutt($: EngineInterface, avbrutt: boolean): Promise<string> {
  const st = await read($, selvtest)
  if (!st) return 'Ingen selvtest å avslutte.'
  await $.prompt.fill({ text: '', mode: 'replace' })
  const naa = new Date(await $.clock.now())
  const stempel = naa.toISOString().replace(/[:]/g, '').replace(/\..*$/, '')
  const rapport = {
    norsk_tale_selvtest: 2, kilde: 'claude-code', tidspunkt: naa.toISOString(), avbrutt,
    oppsummering: oppsummer({ ...st, avbrutt }), innsetting: st.innsetting, angre: st.angre,
    merknad: 'Ingen lyd er lagret. Seks-setningstesten med scoring kjøres i kalibreringsriggen (/norsk kalibrer → Selvtest).',
  }
  // Rapporten skrives av MCP-serveren, som bestemmer mappe og filnavn og stopper ved et
  // umontert eksternt volum. Modden skriver ingen filer og leser ingen miljøvariabler.
  let fil: string | null = null
  let lagringsfeil: string | null = null
  try {
    const r = await kall($, 'lagre_selvtest', { rapport: JSON.stringify(rapport, null, 2), stempel })
    if (r.ok === true && typeof r.fil === 'string') fil = r.fil
    else lagringsfeil = String(r.melding ?? 'Opptaksmappa er ikke tilgjengelig.')
  } catch (feil) {
    lagringsfeil = `Kunne ikke lagre selvtestrapporten: ${String(feil)}`
  }
  const ferdig: NorskSelvtest = { ...st, aktiv: false, steg: 'ferdig', avbrutt, fil, lagringsfeil }
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

// ---------------------------------------------------------------- MCP-serveren
// All oppstart av lokale programmer skjer i pluginens MCP-server (mcp/server.py,
// .mcp.json; docs/decisions/NTA-0007). Modden starter ingen prosesser selv: den
// kaller serveren med $.mcp.connect og $.mcp.call.
export const SERVERNOKKEL = 'norsk-tale'
// Verktøyene som bare modden får kalle. Modellen ser og får kalle bare
// transkriber_fil (en lydfil brukeren peker på). Claude kan aldri starte mikrofonen.
export const BARE_MODDEN = ['start_opptak', 'stopp_opptak', 'status', 'frigjor', 'oppsett', 'lagre_selvtest',
  'start_kalibrering'] as const
export const AVVIST = 'norsk-tale: verktøyet brukes bare av pluginens knapp og kommandoer. '
  + 'Claude kan aldri starte mikrofonen; bare brukerens trykk eller snarvei gjør det.'
const SLUTT = new Set(['tekst', 'tom', 'feil'])

// Navnet modellen og hookene ser: mcp__plugin_norsk-tale_norsk-tale__<verktøy>.
// Mikrofonvernets hooks matcher bare disse navnene og ser ingen andre verktøy.
export const VERNEDE = /^mcp__.*norsk[-_]tale.*__(start_opptak|stopp_opptak|status|frigjor|oppsett|lagre_selvtest|start_kalibrering)$/

export function bareForModden(navn: string): boolean {
  const m = /^mcp__.*norsk[-_]tale.*__([a-z_]+)$/.exec(navn)
  return m !== null && (BARE_MODDEN as readonly string[]).includes(m[1] ?? '')
}

// Modulens egen tilstand: nullstilles ved omlasting.
let server: string | null = null
let folger = false

async function sett($: EngineInterface, s: NorskStatus, m: string | null = null) {
  await update($, status, () => s)
  await update($, melding, () => m)
}

async function kobleTil($: EngineInterface): Promise<string> {
  if (server) return server
  const r = await $.mcp.connect(SERVERNOKKEL)
  if (!r.isConnected) throw new Error(r.message)
  server = r.server
  return r.server
}

// Ett verktøykall. Hvert verktøynavn står som fast tekst ved kallet; det finnes ingen
// annen vei til $.mcp.call. Serveren svarer med et objekt: som structuredContent og som
// JSON i en tekstblokk. structuredContent leses først; en innpakket «result»
// (en verdi SDK-en pakket inn) pakkes ut.
type Verktoy = 'start_opptak' | 'stopp_opptak' | 'status' | 'frigjor' | 'oppsett' | 'lagre_selvtest' | 'start_kalibrering'

async function kall($: EngineInterface, verktoy: Verktoy, args: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
  const navn = await kobleTil($)
  let r
  switch (verktoy) {
    case 'start_opptak': r = await $.mcp.call(navn, 'start_opptak', args); break
    case 'stopp_opptak': r = await $.mcp.call(navn, 'stopp_opptak', args); break
    case 'status': r = await $.mcp.call(navn, 'status', args); break
    case 'frigjor': r = await $.mcp.call(navn, 'frigjor', args); break
    case 'oppsett': r = await $.mcp.call(navn, 'oppsett', args); break
    case 'lagre_selvtest': r = await $.mcp.call(navn, 'lagre_selvtest', args); break
    case 'start_kalibrering': r = await $.mcp.call(navn, 'start_kalibrering', args); break
  }
  const tekst = r.content.map(b => (typeof b.text === 'string' ? b.text : '')).join('')
  if (r.isError) throw new Error(tekst || `${verktoy} feilet`)
  return tolkSvar(r.structuredContent, tekst)
}

export function tolkSvar(strukturert: unknown, tekst: string): Record<string, unknown> {
  if (strukturert && typeof strukturert === 'object') {
    const o = strukturert as Record<string, unknown>
    if (typeof o.result === 'string' && Object.keys(o).length === 1) return JSON.parse(o.result) as Record<string, unknown>
    if (o.result && typeof o.result === 'object' && Object.keys(o).length === 1) return o.result as Record<string, unknown>
    return o
  }
  return JSON.parse(tekst) as Record<string, unknown>
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

// Følger ett opptak: henter lytterens hendelser fra serveren til opptaket er
// ferdig (tekst, tom eller feil). Høyst 30 minutter.
async function folgOpptak($: EngineInterface, etter: number) {
  if (folger) return
  folger = true
  let nr = etter
  try {
    for (let runde = 0; runde < 12000; runde += 1) {
      await $.clock.sleep(150)
      const st = await kall($, 'status', { etter: nr })
      for (const hd of (st.hendelser as (Hendelse & { nr: number })[])) {
        nr = hd.nr
        await hendelse($, hd)
        if (SLUTT.has(hd.type)) return
      }
    }
  } catch (feil) {
    await sett($, 'feil', `MCP-serveren svarte ikke: ${String(feil)}`)
  } finally {
    folger = false
  }
}

async function veksle($: EngineInterface): Promise<string> {
  const s = await read($, status)
  if (s === 'lytter' || s === 'tale' || s === 'starter') {
    try {
      await kall($, 'stopp_opptak')
    } catch (feil) {
      await sett($, 'feil', `Kunne ikke stoppe opptaket: ${String(feil)}`)
    }
    return 'Stopper opptaket.'
  }
  if (s === 'behandler') return 'Transkriberer fortsatt.'
  const st = await read($, selvtest)
  if (st && !st.aktiv) await update($, selvtest, () => null)   // gammel oppsummering bort
  await sett($, 'starter')
  try {
    const r = await kall($, 'start_opptak')
    void folgOpptak($, Number(r.etter ?? 0)).catch(() => {
      // Modulen ble lastet ut (omlasting, øktslutt) mens løkka gikk.
    })
  } catch (feil) {
    await sett($, 'feil', `Lytteren kunne ikke startes: ${String(feil)}`)
    return 'Lytteren kunne ikke startes.'
  }
  return 'Lytter på norsk. Trykk igjen, eller 1,5 s stillhet, for å stoppe.'
}

async function oppsett($: EngineInterface): Promise<string> {
  try {
    const r = await kall($, 'oppsett')
    return String(r.melding ?? 'Oppsettsjekken ga ikke noe svar.')
  } catch (feil) {
    return `Oppsettsjekken kunne ikke kjøres: ${String(feil)}`
  }
}

async function frigjor($: EngineInterface): Promise<string> {
  try {
    await kall($, 'frigjor')
  } catch (feil) {
    return `Kunne ikke frigjøre modellen: ${String(feil)}`
  }
  await sett($, 'av')
  return 'Lytteren er stoppet og modellen frigjort.'
}

async function startRigg($: EngineInterface): Promise<string> {
  let r: Record<string, unknown>
  try {
    r = await kall($, 'start_kalibrering')
  } catch (feil) {
    await sett($, 'feil', `Kalibreringsriggen kunne ikke startes: ${String(feil)}`)
    return 'Kalibreringsriggen kunne ikke startes.'
  }
  if (typeof r.url !== 'string') {
    await sett($, 'feil', `Kalibreringsriggen startet ikke: ${String(r.feil ?? 'ukjent feil')}`)
    return 'Kalibreringsriggen startet ikke.'
  }
  const url = r.url
  await update($, rigg, () => url)
  $.ui.toast(r.apnet ? 'norsk-tale: kalibreringsriggen er åpnet i nettleseren.'
    : 'norsk-tale: åpne adressen over prompten i nettleseren.')
  return r.allerede ? 'Kalibreringsriggen kjører allerede. Adressen står over prompten.'
    : 'Starter kalibreringsriggen. Den åpnes i nettleseren, og adressen står over prompten. Alt skjer på denne maskinen.'
}

async function angreNa($: EngineInterface): Promise<string> {
  const forrige = await read($, angre)
  if (!forrige) return 'Ingenting å angre.'
  await $.prompt.fill({ text: forrige.text, mode: 'replace' })
  await update($, angre, () => null)
  if (await etterAngre($)) return 'Prompten er satt tilbake. Selvtesten er ferdig.'
  return 'Prompten er satt tilbake.'
}

export const register: Register = (on) => {

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
    if (arg === 'av') return { text: await frigjor($) }
    if (arg !== '') return { text: `Ukjent argument «${arg}». Bruk /norsk, /norsk angre, /norsk av, /norsk oppsett, /norsk selvtest eller /norsk kalibrer.` }
    return { text: await veksle($) }
  })

  // Mikrofonvern: verktøyene som kan åpne mikrofonen (og resten av moddens egne)
  // skjules for Claude og avvises for alle kall som ikke kommer fra denne modden.
  // Modellens egne kall har next.origin.plugin === 'engine'. Matcheren gjør at
  // hookene bare ser disse sju verktøyene; alle andre verktøy går forbi urørt.
  on('tool.describe', { tool: VERNEDE }, async ($, e, next) => {
    if (!bareForModden(e.tool)) return next(e)
    return { description: 'Ikke tilgjengelig for Claude: brukes bare av norsk-tale-modden etter brukerens trykk.',
      isDeferred: true }
  })

  on('tool.check', { tool: VERNEDE }, async ($, e, next) => {
    if (bareForModden(e.tool) && next.origin.plugin !== 'norsk-tale') return { decision: 'deny', reason: AVVIST }
    return next(e)
  })

  on('tool.call', { tool: VERNEDE }, async ($, e, next) => {
    if (bareForModden(e.tool) && next.origin.plugin !== 'norsk-tale') return { deny: AVVIST }
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
