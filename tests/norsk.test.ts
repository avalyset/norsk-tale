import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, ProcessSpawnChunk, ProcessSpawnResult } from 'claude-code'

// Lytterens stdout: én JSON-linje per hendelse.
const linje = (h: object): ProcessSpawnChunk => ({ stream: 'stdout', text: `${JSON.stringify(h)}\n` })

const RESULTAT = {
  verbatim: 'Vi trenger tre eksemplarer,\nikke fire.',
  korrigert: 'Vi trenger tre eksemplarer,\nikke fire.',
  substitusjonslogg: [],
  modell_sha256: '0f2f66f22e11a7c7da3c582d8e5c89cb2c0011753ba9c7c9731e320a4ba33e76',
  versjon: '0.2.0',
}

const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 80, scroll: { offset: 0, bodyRows: 3 }, view: {} },
} as const

// Stubber under modden: lytterprosessen (som venter på kommandofilene modden
// skriver), promptboksen, innsending og toasts — alt registrert.
const rig = (on: On, svar: (ord: string) => ProcessSpawnChunk[], utkast = { text: '', cursor: 0 }) => {
  const spawns: string[][] = []
  const kommandoer: string[] = []
  const fills: { text: string; mode: string }[] = []
  const submits: string[] = []
  const toasts: string[] = []
  const ko: ProcessSpawnChunk[][] = []
  let vekk: (() => void) | undefined

  mock.env(on, { TMPDIR: '/tmp/test/' })
  on('session.id', () => ({ value: 'okt-1' }))
  on('fs.write', ($, e) => {
    kommandoer.push(`${e.path}=${e.text}`)
    ko.push(svar(e.text))
    vekk?.()
    return { value: undefined }
  })
  on('process.spawn', async function* ($, e) {
    spawns.push([...e.argv])
    yield linje({ type: 'oppe', feil: null })
    for (;;) {
      while (ko.length === 0) await new Promise<void>(r => { vekk = r })
      const neste = ko.shift() ?? []
      for (const c of neste) yield c
      if (neste.some(c => c.text.includes('"avslutt"'))) break
    }
    return { value: { code: 0, signal: null } as ProcessSpawnResult }
  })
  on('prompt.read', () => ({ value: utkast }))
  on('prompt.fill', ($, e) => {
    fills.push({ text: e.text, mode: e.mode })
    return { isFilled: true }
  })
  on('prompt.submit', ($, e) => {
    submits.push(e.text)
    return { drop: 'norsk-tale sender aldri inn' }
  })
  on('ui.toast', ($, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.render', ($, e) => $.ui.resolve(e).Box({}))
  return { spawns, kommandoer, fills, submits, toasts }
}

// Testmiljøet har en tidtaker, men typene uten DOM/Node nevner den ikke.
declare const setTimeout: (f: () => void, ms: number) => unknown
const vent = () => new Promise<void>(r => setTimeout(r, 20))
const band = ($: Engine, surface: 'terminal' | 'desktop') => $.ui.mount({ plugin: 'norsk-tale', surface, ...BAND })

describe('norsk-tale: diktering inn i promptboksen', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`${surface}: trykk → tekst settes inn ved markøren, ingenting sendes inn`, async ($, on) => {
      const rec = rig(on, ord => (ord === 'start'
        ? [linje({ type: 'lytter' }), linje({ type: 'tale' }), linje({ type: 'behandler', slutt: 'stillhet' }),
            linje({ type: 'tekst', slutt: 'stillhet', resultat: RESULTAT })]
        : []), { text: 'Oppsummer:', cursor: 10 })

      const ui = await band($, surface)
      expect((await ui.find({ key: 'norsk' }))?.text).toBe('🎙 Norsk')
      await ui.press({ key: 'norsk' })
      await vent()

      expect(rec.spawns.length).toBe(1)
      expect(rec.spawns[0]).toContain('-I')
      expect(rec.spawns[0]?.at(-1)).toBe('~/norskriber')
      expect(rec.kommandoer).toEqual(['/tmp/test/norsk-tale-okt-1/1.cmd=start'])
      // segmentlinjene blir løpende tekst, og et mellomrom skiller fra utkastet
      expect(rec.fills).toEqual([{ text: ' Vi trenger tre eksemplarer, ikke fire.', mode: 'insert' }])
      expect(rec.submits).toEqual([])
      await ui.unmount()
    })
  }

  test('angre setter tilbake utkastet slik det var før dikteringen', async ($, on) => {
    const rec = rig(on, ord => (ord === 'start' ? [linje({ type: 'tekst', slutt: 'trykk', resultat: RESULTAT })] : []),
      { text: 'Hei', cursor: 3 })
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await vent()
    expect(await ui.find({ key: 'angre' })).toBeDefined()
    await ui.press({ key: 'angre' })
    expect(rec.fills.at(-1)).toEqual({ text: 'Hei', mode: 'replace' })
    expect(await ui.find({ key: 'angre' })).toBeUndefined()
    expect(rec.submits).toEqual([])
  })

  test('andre trykk mens den lytter sender stopp', async ($, on) => {
    const rec = rig(on, ord => (ord === 'start' ? [linje({ type: 'lytter' })] : []))
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await vent()
    expect((await ui.find({ key: 'norsk' }))?.text).toBe('■ Stopp')
    await ui.press({ key: 'norsk' })
    expect(rec.kommandoer.map(k => k.split('=')[1])).toEqual(['start', 'stopp'])
  })

  test('manglende modell gir én tydelig feilmelding og ingen innsetting', async ($, on) => {
    const melding = 'Fant ikke modellen: /Users/x/whisper.cpp/models/nb-large.bin'
    const rec = rig(on, ord => (ord === 'start' ? [linje({ type: 'feil', melding })] : []))
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await vent()
    expect(rec.toasts).toEqual([`norsk-tale: ${melding}`])
    expect(await ui.find({ type: 'Text', text: melding })).toBeDefined()
    expect(rec.fills).toEqual([])
  })

  test('stillhet uten tale setter ingenting inn', async ($, on) => {
    const rec = rig(on, ord => (ord === 'start' ? [linje({ type: 'lytter' }), linje({ type: 'tom', slutt: 'tak' })] : []))
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await vent()
    expect(rec.fills).toEqual([])
    expect(rec.toasts).toEqual(['norsk-tale: hørte ingen tale.'])
  })

  test('/norsk veksler, /norsk angre uten noe å angre sier det', async ($, on) => {
    const rec = rig(on, () => [])
    const r1 = await $.command.run({ command: 'norsk', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(r1.text).toContain('Lytter på norsk')
    const r2 = await $.command.run({ command: 'norsk', args: 'angre', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(r2.text).toBe('Ingenting å angre.')
    expect(rec.submits).toEqual([])
  })
})
