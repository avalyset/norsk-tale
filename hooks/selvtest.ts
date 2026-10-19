// /norsk selvtest — kort akseptansetest av den ekte veien inn i promptboksen.
//
// Én diktering via snarveien (ctrl+x tab, n) eller knappen: testen setter et
// kjent prefiks i promptboksen, sjekker at teksten kom inn etter prefikset, ber
// om ett Angre-trykk og sjekker at boksen ble prefikset igjen. Så tømmes boksen
// og resultatet lagres. Ingen lyd lagres, og ingenting sendes inn til Claude.
//
// Seks-setningstesten med scoring (nektelse, tall, navn, første ord, målform,
// stopp-tid) ligger i kalibreringsriggen: /norsk kalibrer → fanen «Selvtest».

import { atom, read, update } from 'claude-code'
import type { EngineInterface } from 'claude-code'

import type { NorskSelvtest } from '../types'

export const selvtest = atom({ plugin: 'norsk-tale', key: 'selvtest' } as const, null as NorskSelvtest | null)

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
