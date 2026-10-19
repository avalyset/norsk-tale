import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, ProcessSpawnChunk, ProcessSpawnResult } from 'claude-code'

// /norsk selvtest: én diktering via snarveien, så Angre.
const HORT = 'Jeg har ikke betalt de 3450 kronene til Skatteetaten ennå.'

const linje = (h: object): ProcessSpawnChunk => ({ stream: 'stdout', text: `${JSON.stringify(h)}\n` })
const tekst = (t: string) => ({ verbatim: t, korrigert: t, substitusjonslogg: [], modell_sha256: 'f'.repeat(64), versjon: '0.1.0' })

const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 120, scroll: { offset: 0, bodyRows: 6 }, view: {} },
} as const

const rig = (on: On, startUtkast = '', montert = true, hort = HORT) => {
  const boks = { text: startUtkast, cursor: startUtkast.length }
  const fills: { text: string; mode: string }[] = []
  const skrevet: { path: string; text: string }[] = []
  const submits: string[] = []
  const apnet: string[] = []
  const ko: ProcessSpawnChunk[][] = []
  let vekk: (() => void) | undefined

  mock.env(on, { TMPDIR: '/tmp/test/', HOME: '/hjem/test' })
  mock.clock(on)
  on('session.id', () => ({ value: 'okt-1' }))
  on('fs.write', ($, e) => {
    skrevet.push({ path: e.path, text: e.text })
    if (e.path.endsWith('.cmd')) {
      ko.push(e.text.startsWith('start')
        ? [linje({ type: 'lytter' }), linje({ type: 'tale' }), linje({ type: 'behandler', slutt: 'stillhet' }),
            linje({ type: 'tekst', slutt: 'stillhet', resultat: tekst(hort) })]
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
  on('process.run', () => ({
    value: { exitCode: montert ? 0 : 5, stdout: '', stderr: montert ? '' : 'norsk-tale: /Volumes/Vault er ikke montert.',
      isStdoutTruncated: false, isStderrTruncated: false },
  }))
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
  return { boks, fills, skrevet, submits, apnet }
}

const kjor = ($: Engine, args: string) => $.command.run({
  command: 'norsk', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 },
})
declare const setTimeout: (f: () => void, ms: number) => unknown
const vent = () => new Promise<void>(r => setTimeout(r, 30))

describe('norsk-tale: /norsk selvtest', () => {
  test('én diktering: teksten kommer inn etter prefikset, Angre gjenoppretter, boksen tømmes', async ($, on) => {
    const rec = rig(on)
    const start = await kjor($, 'selvtest')
    expect(start.text).toContain('én diktering')
    expect(start.text).toContain('ctrl+x tab')
    expect(rec.boks.text).toBe('TEST: ')

    const ui = await $.ui.mount({ plugin: 'norsk-tale', surface: 'terminal', ...BAND })
    expect(await ui.find({ type: 'Text', text: /trykk ctrl\+x tab og så n/ })).toBeDefined()
    expect((await ui.find({ key: 'norsk' }))?.props.hotkey).toBe('n')

    await ui.press({ key: 'norsk' }); await vent()          // som hurtigtasten n gjør
    expect(rec.boks.text).toBe(`TEST: ${HORT}`)
    expect(rec.fills).toContainEqual({ text: HORT, mode: 'insert' })
    expect(await ui.find({ type: 'Text', text: /trykk Angre \(a\)/ })).toBeDefined()
    expect((await ui.find({ key: 'angre' }))?.props.hotkey).toBe('a')

    await ui.press({ key: 'angre' }); await vent()
    expect(rec.boks.text).toBe('')                            // tømt til slutt

    const fil = rec.skrevet.find(w => w.path.endsWith('.json'))
    expect(fil?.path).toMatch(/^\/hjem\/test\/norsk-tale-opptak\/selvtest-claude-\d{4}-\d{2}-\d{2}T\d{6}\.json$/)
    const rapport = JSON.parse(fil?.text ?? '{}')
    expect(rapport.avbrutt).toBe(false)
    expect(rapport.innsetting).toEqual({ ok: true, boks: `TEST: ${HORT}`, tekst: HORT })
    expect(rapport.angre).toEqual({ ok: true, forventet: 'TEST: ', faktisk: 'TEST: ' })
    expect(rapport.oppsummering).toEqual({ bestatt: 2, sjekker: 2 })
    expect(JSON.stringify(rapport)).not.toMatch(/\.wav|base64/)
    expect(rec.apnet).toContain('norsk-selvtest')
    expect(await ui.find({ type: 'Text', text: /Selvtest ferdig: 2 av 2 sjekker bestått/ })).toBeDefined()
    expect(rec.submits).toEqual([])
    await ui.unmount()
  })

  test('tom diktering setter ingenting inn, og testen venter fortsatt', async ($, on) => {
    const rec = rig(on, '', true, '   ')
    await kjor($, 'selvtest')
    const ui = await $.ui.mount({ plugin: 'norsk-tale', surface: 'terminal', ...BAND })
    await ui.press({ key: 'norsk' }); await vent()
    // ingen ord: ingenting settes inn, testen venter fortsatt på dikteringen
    expect(rec.boks.text).toBe('TEST: ')
    expect(await ui.find({ type: 'Text', text: /trykk ctrl\+x tab og så n/ })).toBeDefined()
    await ui.unmount()
  })

  test('Enter under selvtesten sendes ikke inn', async ($, on) => {
    const rec = rig(on)
    await kjor($, 'selvtest')
    const r = await $.prompt.submit({ text: 'TEST: hei', wait: false, origin: { kind: 'composer' } })
    expect(r.drop).toContain('Selvtesten pågår')
    expect(rec.submits).toEqual([])
  })

  test('starter ikke når promptboksen har tekst', async ($, on) => {
    const rec = rig(on, 'Et utkast jeg ikke vil miste')
    const r = await kjor($, 'selvtest')
    expect(r.text).toContain('Tøm promptboksen')
    expect(rec.boks.text).toBe('Et utkast jeg ikke vil miste')
  })

  test('avbryt (x) tømmer boksen og lagrer delresultat', async ($, on) => {
    const rec = rig(on)
    await kjor($, 'selvtest')
    const ui = await $.ui.mount({ plugin: 'norsk-tale', surface: 'terminal', ...BAND })
    expect((await ui.find({ key: 'avbryt' }))?.props.hotkey).toBe('x')
    await ui.press({ key: 'norsk' }); await vent()
    await ui.press({ key: 'avbryt' }); await vent()
    expect(rec.boks.text).toBe('')
    const rapport = JSON.parse(rec.skrevet.find(w => w.path.endsWith('.json'))?.text ?? '{}')
    expect(rapport.avbrutt).toBe(true)
    expect(rapport.innsetting.ok).toBe(true)
    expect(rapport.angre).toBe(null)
    expect(rec.submits).toEqual([])
  })

  test('umontert opptaksvolum: ingenting skrives, og det sies tydelig', async ($, on) => {
    const rec = rig(on, '', false)
    await kjor($, 'selvtest')
    const r = await kjor($, 'selvtest avbryt')
    expect(r.text).toContain('IKKE lagret')
    expect(r.text).toContain('ikke montert')
    expect(rec.skrevet.filter(w => w.path.endsWith('.json'))).toEqual([])
    expect(rec.boks.text).toBe('')
  })
})
