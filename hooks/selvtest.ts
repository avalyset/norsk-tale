// /norsk selvtest — guidet akseptansetest av den ekte dikteringsveien.
//
// Brukeren dikterer seks kjente setninger med den vanlige knappen. Testen setter
// et kjent prefiks i promptboksen før hvert opptak, leser boksen etter
// innsettingen, scorer med kalibrering/score.py (deterministisk, ingen LLM), ber
// om ett Angre-trykk, tømmer boksen og lagrer resultatet. Ingen lyd lagres, og
// ingenting sendes inn til Claude.

import { atom, read, update } from 'claude-code'
import type { EngineInterface } from 'claude-code'

import type { NorskScore, NorskSelvtest, NorskSelvtestRad, NorskSetning } from '../types'

export const selvtest = atom({ plugin: 'norsk-tale', key: 'selvtest' } as const, null as NorskSelvtest | null)

export const PANE = 'norsk-selvtest'
export const prefiks = (n: number) => `TEST-${n}: `

export function lesSetninger(tsv: string): NorskSetning[] {
  const linjer = tsv.split('\n').filter(l => l.trim() !== '' && !l.startsWith('#'))
  const [hode, ...rader] = linjer
  const kol = (hode ?? '').split('\t')
  const i = { id: kol.indexOf('id'), malform: kol.indexOf('malform'), setning: kol.indexOf('setning') }
  return rader.map(r => {
    const f = r.split('\t')
    return { id: f[i.id] ?? '', malform: f[i.malform] ?? '', setning: f[i.setning] ?? '' }
  })
}

export async function aktivTest($: EngineInterface): Promise<NorskSelvtest | null> {
  const st = await read($, selvtest)
  return st && st.aktiv ? st : null
}

async function forbered($: EngineInterface, n: number) {
  await $.prompt.fill({ text: prefiks(n), mode: 'replace' })
}

export async function startSelvtest($: EngineInterface): Promise<string> {
  const boks = await $.prompt.read()
  if (boks.text.trim() !== '') {
    return 'Tøm promptboksen før selvtesten: den bruker boksen og tømmer den til slutt.'
  }
  const setninger = lesSetninger(await $.fs.read(`${$.plugin.root}/selvtest/setninger.tsv`))
  if (setninger.length === 0) return 'Fant ingen setninger i selvtest/setninger.tsv.'
  await update($, selvtest, () => ({
    aktiv: true, steg: 1, setninger, resultater: [], angre: null, fil: null, avbrutt: false, lagringsfeil: null,
  }))
  await forbered($, 1)
  return `Selvtest startet: ${setninger.length} setninger. Trykk 🎙 Norsk og les setningen over prompten. `
    + 'Ikke trykk Enter — ingenting sendes inn.'
}

async function scor($: EngineInterface, id: string, utdata: string): Promise<{ score: NorskScore | null; feil: string | null }> {
  const rot = $.plugin.root
  const argv = ['python3', '-I', `${rot}/kalibrering/score.py`, '--setninger', `${rot}/selvtest/setninger.tsv`, '--id', id]
  try {
    const r = await $.process.run(argv, { stdin: utdata, timeoutMs: 30000 })
    if (r.exitCode !== 0) return { score: null, feil: r.stderr.trim() || `score.py avsluttet med ${r.exitCode}` }
    return { score: JSON.parse(r.stdout) as NorskScore, feil: null }
  } catch (feil) {
    return { score: null, feil: String(feil) }
  }
}

// Kalles etter hver vellykkede innsetting mens testen er aktiv.
export async function etterInnsetting(
  $: EngineInterface,
  maling: { verbatim: string; slutt: string; stillhet_ms: number | null; stopp_til_tekst_ms: number | null; malform_valgt: string },
): Promise<boolean> {
  const st = await aktivTest($)
  if (!st || st.steg < 1 || st.steg > st.setninger.length) return false
  const n = st.steg
  const s = st.setninger[n - 1]
  if (!s) return false
  const boks = await $.prompt.read()
  const p = prefiks(n)
  const prefiks_ok = boks.text.startsWith(p)
  const utdata = (prefiks_ok ? boks.text.slice(p.length) : boks.text).trim()
  const { score, feil } = await scor($, s.id, utdata)
  const rad: NorskSelvtestRad = {
    id: s.id, setning: s.setning, malform: s.malform, prefiks_ok, boks: boks.text, utdata,
    verbatim: maling.verbatim, slutt: maling.slutt, stillhet_ms: maling.stillhet_ms, malform_valgt: maling.malform_valgt,
    stopp_til_tekst_ms: maling.stopp_til_tekst_ms, score, scorefeil: feil,
  }
  await update($, selvtest, x => (x ? { ...x, resultater: [...x.resultater, rad], steg: n + 1 } : x))
  if (n < st.setninger.length) await forbered($, n + 1)
  return true
}

// Kalles etter Angre. Returnerer true når Angre-steget ble målt.
export async function etterAngre($: EngineInterface): Promise<boolean> {
  const st = await aktivTest($)
  if (!st || st.steg !== st.setninger.length + 1) return false
  const forventet = prefiks(st.setninger.length)
  const faktisk = (await $.prompt.read()).text
  await update($, selvtest, x => (x ? { ...x, angre: { ok: faktisk === forventet, forventet, faktisk } } : x))
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
  const fil = lagringsfeil ? null : `${mappe}/selvtest-${stempel}.json`
  const ferdig: NorskSelvtest = { ...st, aktiv: false, avbrutt, fil, lagringsfeil }
  const rapport = {
    norsk_tale_selvtest: 1, tidspunkt: new Date(await $.clock.now()).toISOString(), avbrutt,
    oppsummering: oppsummer(ferdig), resultater: ferdig.resultater, angre: ferdig.angre,
    merknad: 'Ingen lyd er lagret. utdata er det som sto i promptboksen etter prefikset.',
  }
  if (fil) await $.fs.write(fil, JSON.stringify(rapport, null, 2) + '\n')
  await update($, selvtest, () => ferdig)
  await $.ui.open({ id: PANE, title: 'norsk-tale selvtest' })
  const hvor = fil ? `Resultat: ${fil}` : `Resultatet ble IKKE lagret: ${lagringsfeil}`
  return avbrutt ? `Selvtesten ble avbrutt. ${hvor}` : `Selvtest ferdig. ${hvor}`
}

export type Oppsummering = { bestatt: number; sjekker: number; funn: string[] }

export function oppsummer(st: NorskSelvtest): Oppsummering {
  let bestatt = 0
  let sjekker = 0
  const funn: string[] = []
  for (const r of st.resultater) {
    sjekker += 1
    if (r.prefiks_ok) bestatt += 1
    if (r.score) {
      for (const e of r.score.elementer) {
        sjekker += 1
        if (e.treff) bestatt += 1
      }
      sjekker += 1
      if (r.score.forste_innholdsord.treff) bestatt += 1
      if (r.score.malform.funn) {
        funn.push(`Setning ${r.id}: forventet målform ${r.score.malform.forventet}, fikk ${r.score.malform.utdata} (whisper kjørt med ${r.malform_valgt}).`)
      }
    } else {
      sjekker += 1
      funn.push(`Setning ${r.id}: scoring feilet (${r.scorefeil ?? 'ukjent'}).`)
    }
  }
  if (st.angre) {
    sjekker += 1
    if (st.angre.ok) bestatt += 1
  }
  return { bestatt, sjekker, funn }
}

const sek = (ms: number | null) => (ms === null ? '–' : `${(ms / 1000).toFixed(1).replace('.', ',')} s`)
const merke = (ok: boolean) => (ok ? '✔' : '✘')

// Tabellen som linjer, felles for panelet og testene.
export function tabell(st: NorskSelvtest): string[] {
  const ut: string[] = []
  const o = oppsummer(st)
  ut.push(`${st.avbrutt ? 'Avbrutt' : 'Ferdig'}: ${o.bestatt} av ${o.sjekker} sjekker bestått.`)
  for (const r of st.resultater) {
    const deler = [`innsetting ${merke(r.prefiks_ok)}`]
    for (const e of r.score?.elementer ?? []) deler.push(`${e.type} ${merke(e.treff)}`)
    if (r.score) deler.push(`første ord ${merke(r.score.forste_innholdsord.treff)}`)
    const stopp = r.slutt === 'stillhet' ? `stillhet→stopp ${sek(r.stillhet_ms)}` : `stopp: ${r.slutt}`
    ut.push(`${r.id} ${merke(Boolean(r.score?.bestatt) && r.prefiks_ok)}  ${deler.join(' · ')}  |  ${stopp} · stopp→tekst ${sek(r.stopp_til_tekst_ms)}`)
    for (const b of r.score?.bom ?? []) ut.push(`   bom ${b.type}: fasit «${b.fasit}» — utdata «${b.utdata}»`)
    if (!r.prefiks_ok) ut.push(`   bom innsetting: boksen var «${r.boks}»`)
    if (r.score?.malform.funn) ut.push(`   funn målform: forventet ${r.score.malform.forventet}, fikk ${r.score.malform.utdata} — «${r.utdata}»`)
    if (r.scorefeil) ut.push(`   scoring feilet: ${r.scorefeil}`)
  }
  if (st.angre) ut.push(`Angre ${merke(st.angre.ok)}  forventet «${st.angre.forventet}», fikk «${st.angre.faktisk}»`)
  if (st.fil) ut.push(`Lagret: ${st.fil}`)
  if (st.lagringsfeil) ut.push(`Ikke lagret: ${st.lagringsfeil}`)
  return ut
}
