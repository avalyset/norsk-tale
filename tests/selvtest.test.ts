import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, ProcessSpawnChunk, ProcessSpawnResult } from 'claude-code'

// Tre av selvtestens setninger, én nynorsk; flyten er den samme for seks.
const TSV = [
  '# selvtest',
  'id\tmalform\tklasse\tsetning\telementer',
  '1\tnb\tkombinert\tJeg har ikke betalt de tre tusen fire hundre og femti kronene til Skatteetaten ennå.\t[]',
  '4\tnb\tkombinert\tIngen av de sju sakene hos NAV ble avvist i tjuetjuefem.\t[]',
  '6\tnn\tkombinert\tEg har ikkje fått svar frå Statsforvaltaren om dei tre søknadene.\t[]',
].join('\n')

// Det «lytteren» hører for hver setning, i rekkefølge.
const HORT = [
  'Jeg har ikke betalt de 3450 kronene til Skatteetaten ennå.',
  'Ingen av de seks sakene hos NAV ble avvist i 2025.',
  'Jeg har ikke fått svar fra Statsforvalteren om de tre søknadene.',
]

const linje = (h: object): ProcessSpawnChunk => ({ stream: 'stdout', text: `${JSON.stringify(h)}\n` })
const tekst = (t: string) => ({ verbatim: t, korrigert: t, substitusjonslogg: [], modell_sha256: 'f'.repeat(64), versjon: '0.1.0' })

// Hva score.py ville svart, ut fra id og utdata.
function score(id: string, utdata: string) {
  const tallBom = id === '4' && !utdata.includes(' 7 ') && !utdata.includes('sju')
  const nb = /\bjeg\b|\bikke\b|\bfra\b/i.test(utdata)
  return {
    id, setning: '', utdata,
    elementer: [{ type: 'nektelse', former: ['x'], treff: true, funnet: 'x' },
      { type: 'tall', former: ['7'], treff: !tallBom, funnet: tallBom ? null : '7' }],
    forste_innholdsord: { ord: 'x', treff: true },
    malform: { forventet: id === '6' ? 'nn' : 'nb', utdata: nb ? 'nb' : 'nn', funn: id === '6' && nb },
    bom: tallBom ? [{ type: 'tall', fasit: '7', utdata }] : [],
    bestatt: !tallBom, wer: 0, cer: 0,
  }
}

const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 120, scroll: { offset: 0, bodyRows: 6 }, view: {} },
} as const

const rig = (on: On, startUtkast = '') => {
  const boks = { text: startUtkast, cursor: startUtkast.length }
  const fills: { text: string; mode: string }[] = []
  const skrevet: { path: string; text: string }[] = []
  const scorekall: { id: string; stdin: string }[] = []
  const submits: string[] = []
  const apnet: string[] = []
  const ko: ProcessSpawnChunk[][] = []
  let hort = 0
  let vekk: (() => void) | undefined

  mock.env(on, { TMPDIR: '/tmp/test/', HOME: '/hjem/test' })
  mock.clock(on)
  on('session.id', () => ({ value: 'okt-1' }))
  on('fs.read', ($, e) => ({ value: JSON.stringify(e).includes('setninger.tsv') ? TSV : '' }))
  on('fs.write', ($, e) => {
    skrevet.push({ path: e.path, text: e.text })
    if (e.path.endsWith('.cmd')) {
      ko.push(e.text === 'start'
        ? [linje({ type: 'lytter' }), linje({ type: 'tale' }),
            linje({ type: 'behandler', slutt: 'stillhet', stillhet_ms: 1500, tale_ms: 3000 }),
            linje({ type: 'tekst', slutt: 'stillhet', stillhet_ms: 1500, resultat: tekst(HORT[hort++] ?? '') })]
        : [])
      vekk?.()
    }
    return { value: undefined }
  })
  on('process.spawn', async function* () {
    yield linje({ type: 'oppe', feil: null })
    for (;;) {
      while (ko.length === 0) await new Promise<void>(r => { vekk = r })
      for (const c of ko.shift() ?? []) yield c
    }
    return { value: { code: 0, signal: null } as ProcessSpawnResult }
  })
  on('process.run', ($, e) => {
    const id = e.argv[e.argv.indexOf('--id') + 1] ?? ''
    const stdin = e.init?.stdin ?? ''
    scorekall.push({ id, stdin })
    return { value: { exitCode: 0, stdout: JSON.stringify(score(id, stdin)), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('prompt.read', () => ({ value: { ...boks } }))
  on('prompt.fill', ($, e) => {
    fills.push({ text: e.text, mode: e.mode })
    if (e.mode === 'replace') { boks.text = e.text; boks.cursor = e.text.length }
    else if (e.mode === 'append') { boks.text += e.text; boks.cursor = boks.text.length }
    else { boks.text = boks.text.slice(0, boks.cursor) + e.text + boks.text.slice(boks.cursor); boks.cursor += e.text.length }
    return { isFilled: true }
  })
  on('prompt.submit', ($, e) => {
    submits.push(e.text)
    return { drop: 'testens bunn' }
  })
  on('ui.open', ($, e) => { apnet.push(e.id); return { value: { isPlaced: true } } })
  on('ui.toast', () => ({ value: undefined }))
  on('ui.render', ($, e) => $.ui.resolve(e).Box({}))
  return { boks, fills, skrevet, scorekall, submits, apnet }
}

const kjor = ($: Engine, args: string) => $.command.run({
  command: 'norsk', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 },
})
declare const setTimeout: (f: () => void, ms: number) => unknown
const vent = () => new Promise<void>(r => setTimeout(r, 30))

describe('norsk-tale: /norsk selvtest', () => {
  test('hele flyten: prefiks, innsetting, scoring, Angre, tømming og resultatfil', async ($, on) => {
    const rec = rig(on)
    const start = await kjor($, 'selvtest')
    expect(start.text).toContain('Selvtest startet: 3 setninger')
    expect(rec.boks.text).toBe('TEST-1: ')

    const ui = await $.ui.mount({ plugin: 'norsk-tale', surface: 'terminal', ...BAND })
    expect(await ui.find({ type: 'Text', text: /setning 1 av 3/ })).toBeDefined()

    await ui.press({ key: 'norsk' }); await vent()
    expect(rec.fills).toContainEqual({ text: HORT[0], mode: 'insert' })   // inn ved markøren, uten ekstra mellomrom
    expect(rec.boks.text).toBe('TEST-2: ')
    expect(await ui.find({ key: 'angre' })).toBeUndefined()               // Angre bare i siste steg

    await ui.press({ key: 'norsk' }); await vent()
    expect(rec.boks.text).toBe('TEST-3: ')
    expect(await ui.find({ type: 'Text', text: /setning 3 av 3 \(nynorsk\)/ })).toBeDefined()

    await ui.press({ key: 'norsk' }); await vent()
    expect(rec.boks.text).toBe(`TEST-3: ${HORT[2]}`)
    expect(await ui.find({ type: 'Text', text: /siste steg: trykk Angre/ })).toBeDefined()

    await ui.press({ key: 'angre' }); await vent()
    expect(rec.boks.text).toBe('')                                          // tømt til slutt

    expect(rec.scorekall).toEqual([
      { id: '1', stdin: HORT[0] }, { id: '4', stdin: HORT[1] }, { id: '6', stdin: HORT[2] },
    ])
    const fil = rec.skrevet.find(w => w.path.endsWith('.json'))
    expect(fil?.path).toMatch(/^\/hjem\/test\/norsk-tale-opptak\/selvtest-\d{4}-\d{2}-\d{2}T\d{6}\.json$/)
    const rapport = JSON.parse(fil?.text ?? '{}')
    expect(rapport.avbrutt).toBe(false)
    expect(rapport.resultater.map((r: { prefiks_ok: boolean }) => r.prefiks_ok)).toEqual([true, true, true])
    expect(rapport.resultater[0].stillhet_ms).toBe(1500)
    expect(typeof rapport.resultater[0].stopp_til_tekst_ms).toBe('number')
    expect(rapport.resultater[1].score.bom).toEqual([{ type: 'tall', fasit: '7', utdata: HORT[1] }])
    expect(rapport.angre).toEqual({ ok: true, forventet: 'TEST-3: ', faktisk: 'TEST-3: ' })
    // nynorsk som kom ut på bokmål er et funn, ikke en bom
    expect(rapport.resultater[2].score.malform.funn).toBe(true)
    expect(rapport.resultater[2].score.bestatt).toBe(true)
    expect(rapport.oppsummering.funn).toEqual(['Setning 6: forventet målform nn, fikk nb.'])
    expect(JSON.stringify(rapport)).not.toMatch(/\.wav|base64/)            // ingen lyd

    expect(rec.apnet).toContain('norsk-selvtest')
    expect(await ui.find({ type: 'Text', text: /Selvtest ferdig: \d+ av \d+ sjekker bestått, 1 funn/ })).toBeDefined()
    expect(rec.submits).toEqual([])
    await ui.unmount()
  })

  test('Enter under selvtesten sendes ikke inn', async ($, on) => {
    const rec = rig(on)
    await kjor($, 'selvtest')
    const r = await $.prompt.submit({ text: 'TEST-1: Jeg har ikke betalt', wait: false, origin: { kind: 'composer' } })
    expect(r.drop).toContain('Selvtesten pågår')
    expect(rec.submits).toEqual([])
  })

  test('starter ikke når promptboksen har tekst', async ($, on) => {
    const rec = rig(on, 'Et utkast jeg ikke vil miste')
    const r = await kjor($, 'selvtest')
    expect(r.text).toContain('Tøm promptboksen')
    expect(rec.boks.text).toBe('Et utkast jeg ikke vil miste')
  })

  test('avbryt tømmer boksen og lagrer delresultat', async ($, on) => {
    const rec = rig(on)
    await kjor($, 'selvtest')
    const ui = await $.ui.mount({ plugin: 'norsk-tale', surface: 'terminal', ...BAND })
    await ui.press({ key: 'norsk' }); await vent()
    await ui.press({ key: 'avbryt' }); await vent()
    expect(rec.boks.text).toBe('')
    const rapport = JSON.parse(rec.skrevet.find(w => w.path.endsWith('.json'))?.text ?? '{}')
    expect(rapport.avbrutt).toBe(true)
    expect(rapport.resultater.length).toBe(1)
    expect(rec.submits).toEqual([])
  })
})
