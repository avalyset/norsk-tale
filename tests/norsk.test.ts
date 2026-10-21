import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

// Lytterens hendelser slik MCP-serverens status-verktøy gir dem.
type H = Record<string, unknown> & { type: string }

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

const SERVER = 'plugin:norsk-tale:norsk-tale'
const MODELLNAVN = (verktoy: string) => `mcp__plugin_norsk-tale_norsk-tale__${verktoy}`
const svar = (o: unknown) => ({ value: { content: [{ type: 'text', text: JSON.stringify(o) }], isError: false } })

// En falsk MCP-server under modden: verktøyene registreres, start_opptak legger
// skriptede hendelser i køen som status deler ut etter løpenummer.
const rig = (on: On, hendelser: (n: number) => H[], utkast = { text: '', cursor: 0 }, sjekk = 'Alt er på plass.') => {
  const kall: { verktoy: string; args: Record<string, unknown> }[] = []
  const fills: { text: string; mode: string }[] = []
  const submits: string[] = []
  const toasts: string[] = []
  const nådd: string[] = []
  const ko: (H & { nr: number })[] = []
  let nr = 0
  let starter = 0

  const klokke = mock.clock(on)
  mock.env(on, { TMPDIR: '/tmp/test/' })
  on('session.id', () => ({ value: 'okt-1' }))
  on('mcp.connect', () => ({ value: { isConnected: true as const, server: SERVER } }))
  on('mcp.call', ($, e) => {
    kall.push({ verktoy: e.tool, args: { ...e.args } })
    if (e.tool === 'start_opptak') {
      const etter = nr
      for (const h of hendelser(starter++)) ko.push({ ...h, nr: ++nr })
      return svar({ etter })
    }
    if (e.tool === 'status') {
      const etter = Number(e.args.etter ?? 0)
      return svar({ hendelser: ko.filter(h => h.nr > etter), nr, opptak: false })
    }
    if (e.tool === 'oppsett') return svar({ ok: true, melding: sjekk })
    return svar({ ok: true })
  })
  // Bunnen for modellens verktøykall: nås bare hvis mikrofonvernet slipper kallet gjennom.
  on('tool.check', ($, e) => { nådd.push(`check:${e.tool}`); return { decision: 'allow' as const } })
  on('tool.call', ($, e) => { nådd.push(`call:${e.tool}`); return { result: 'kjørt' } as never })
  on('tool.describe', ($, e) => ({ description: e.description }))
  on('prompt.read', () => ({ value: utkast }))
  on('prompt.fill', ($, e) => { fills.push({ text: e.text, mode: e.mode }); return { isFilled: true } })
  on('prompt.submit', ($, e) => { submits.push(e.text); return { drop: 'norsk-tale sender aldri inn' } })
  on('ui.toast', ($, e) => { toasts.push(e.text); return { value: undefined } })
  on('ui.render', ($, e) => $.ui.resolve(e).Box({}))
  const driv = async (ganger = 6) => { for (let i = 0; i < ganger; i += 1) await klokke.advance(200) }
  return { kall, fills, submits, toasts, nådd, driv, verktoy: () => kall.map(k => k.verktoy) }
}

const band = ($: Engine, surface: 'terminal' | 'desktop') => $.ui.mount({ plugin: 'norsk-tale', surface, ...BAND })
const TEKST: H[] = [{ type: 'lytter' }, { type: 'tale' }, { type: 'behandler', slutt: 'stillhet' },
  { type: 'tekst', slutt: 'stillhet', resultat: RESULTAT }]

describe('norsk-tale: diktering inn i promptboksen', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`${surface}: trykk → tekst settes inn ved markøren, ingenting sendes inn`, async ($, on) => {
      const rec = rig(on, () => TEKST, { text: 'Oppsummer:', cursor: 10 })
      const ui = await band($, surface)
      expect((await ui.find({ key: 'norsk' }))?.text).toBe('🎙 Norsk (ctrl+x tab, n)')
      await ui.press({ key: 'norsk' })
      await rec.driv()
      expect(rec.verktoy()[0]).toBe('start_opptak')
      expect(rec.verktoy()).toContain('status')
      // segmentlinjene blir løpende tekst, og et mellomrom skiller fra utkastet
      expect(rec.fills).toEqual([{ text: ' Vi trenger tre eksemplarer, ikke fire.', mode: 'insert' }])
      expect(rec.submits).toEqual([])
      await ui.unmount()
    })
  }

  test('angre setter tilbake utkastet slik det var før dikteringen', async ($, on) => {
    const rec = rig(on, () => [{ type: 'tekst', slutt: 'trykk', resultat: RESULTAT }], { text: 'Hei', cursor: 3 })
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv()
    expect(await ui.find({ key: 'angre' })).toBeDefined()
    await ui.press({ key: 'angre' })
    expect(rec.fills.at(-1)).toEqual({ text: 'Hei', mode: 'replace' })
    expect(await ui.find({ key: 'angre' })).toBeUndefined()
    expect(rec.submits).toEqual([])
  })

  test('tastatur: hurtigtaster på knappene, snarveien i knappeteksten, også med tekst i boksen', async ($, on) => {
    const rec = rig(on, () => [{ type: 'tekst', slutt: 'trykk', resultat: RESULTAT }], { text: 'Et utkast', cursor: 9 })
    for (const surface of ['terminal', 'desktop'] as const) {
      const ui = await band($, surface)
      const knapp = await ui.find({ key: 'norsk' })
      expect(knapp?.props.hotkey).toBe('n')
      expect(knapp?.text).toContain('ctrl+x tab, n')
      await ui.unmount()
    }
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv()
    expect(rec.fills).toEqual([{ text: ' Vi trenger tre eksemplarer, ikke fire.', mode: 'insert' }])
    const angre = await ui.find({ key: 'angre' })
    expect(angre?.props.hotkey).toBe('a')
    expect(angre?.text).toBe('Angre (a)')
    await ui.press({ key: 'angre' })
    expect(rec.fills.at(-1)).toEqual({ text: 'Et utkast', mode: 'replace' })
    expect(rec.submits).toEqual([])
  })

  test('andre trykk mens den lytter sender stopp_opptak', async ($, on) => {
    const rec = rig(on, () => [{ type: 'lytter' }])
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv(2)
    expect((await ui.find({ key: 'norsk' }))?.text).toBe('■ Stopp (ctrl+x tab, n)')
    await ui.press({ key: 'norsk' })
    expect(rec.verktoy()).toContain('stopp_opptak')
  })

  test('manglende modell gir én tydelig feilmelding og ingen innsetting', async ($, on) => {
    const melding = 'Fant ikke modellen: /modeller/nb-whisper-large.bin'
    const rec = rig(on, () => [{ type: 'feil', melding }])
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv()
    expect(rec.toasts).toEqual([`norsk-tale: ${melding}`])
    expect(await ui.find({ type: 'Text', text: melding })).toBeDefined()
    expect(rec.fills).toEqual([])
  })

  test('stillhet uten tale setter ingenting inn', async ($, on) => {
    const rec = rig(on, () => [{ type: 'lytter' }, { type: 'tom', slutt: 'tak' }])
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv()
    expect(rec.fills).toEqual([])
    expect(rec.toasts).toEqual(['norsk-tale: hørte ingen tale.'])
  })

  test('modden starter ingen opptak ved øktstart, bare ved trykk', async ($, on) => {
    const rec = rig(on, () => [])
    await $.session.start({ source: 'startup' } as never).catch(() => undefined)
    const ui = await band($, 'terminal')
    expect(rec.verktoy()).toEqual([])
    await ui.press({ key: 'norsk' })
    expect(rec.verktoy()).toEqual(['start_opptak'])
  })

  test('/norsk oppsett spør serveren og laster ikke ned noe', async ($, on) => {
    const melding = 'Modellen mangler: /modeller/m.bin\n  NbAiLab/nb-whisper-large, ggml-model.bin, 3.10 GB. Ingenting lastes ned automatisk.'
    const rec = rig(on, () => [], { text: '', cursor: 0 }, melding)
    const r = await $.command.run({ command: 'norsk', args: 'oppsett', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(r.text).toBe(melding)
    expect(rec.verktoy()).toEqual(['oppsett'])
  })

  test('/norsk veksler, /norsk av frigjør, /norsk angre uten noe å angre sier det', async ($, on) => {
    const rec = rig(on, () => [])
    const kjor = (args: string) => $.command.run({ command: 'norsk', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect((await kjor('')).text).toContain('Lytter på norsk')
    expect((await kjor('angre')).text).toBe('Ingenting å angre.')
    expect((await kjor('av')).text).toBe('Lytteren er stoppet og modellen frigjort.')
    expect(rec.verktoy()).toContain('frigjor')
    expect(rec.submits).toEqual([])
  })
})

describe('norsk-tale: svar fra serveren', () => {
  test('structuredContent med innpakket result leses riktig (slik Claude Code leverer det)', async ($, on) => {
    mock.clock(on)
    on('mcp.connect', () => ({ value: { isConnected: true as const, server: SERVER } }))
    on('mcp.call', () => ({ value: { content: [{ type: 'text', text: 'ikke JSON' }], isError: false,
      structuredContent: { result: JSON.stringify({ ok: true, melding: 'Alt er på plass.' }) } } }))
    const r = await $.command.run({ command: 'norsk', args: 'oppsett', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(r.text).toBe('Alt er på plass.')
  })
})

describe('norsk-tale: mikrofonvern', () => {
  test('Claude kan ikke starte mikrofonen; modden kan', async ($, on) => {
    const rec = rig(on, () => TEKST)
    const navn = MODELLNAVN('start_opptak')

    // Modellens eget kall (testens $ er motoren: next.origin.plugin === 'engine').
    const sjekk = await $.tool.check({ tool: navn, input: {}, tool_use_id: 'modell-1' })
    expect(sjekk.decision).toBe('deny')
    expect(sjekk.reason).toContain('Claude kan aldri starte mikrofonen')
    const kallet = await $.tool.call({ tool: navn, tool_use_id: 'modell-2' } as never) as { deny?: string }
    expect(kallet.deny).toContain('Claude kan aldri starte mikrofonen')
    expect(rec.nådd).toEqual([])          // ingenting nådde verktøyet …
    expect(rec.verktoy()).toEqual([])     // … og serveren startet ingen prosess

    // Skjult for Claude: beskrivelsen sier det, og verktøyet ligger bak ToolSearch.
    const tier = 'user' as never
    const skjult = await $.tool.describe({ tool: navn, description: 'Bare for norsk-tale-modden', provider: { plugin: 'norsk-tale', tier } })
    expect(skjult.isDeferred).toBe(true)
    expect(skjult.description).toContain('Ikke tilgjengelig for Claude')
    for (const v of ['stopp_opptak', 'status', 'frigjor', 'oppsett', 'lagre_selvtest', 'start_kalibrering']) {
      expect((await $.tool.check({ tool: MODELLNAVN(v), input: {}, tool_use_id: `m-${v}` })).decision).toBe('deny')
    }
    // Bare transkriber_fil er synlig og kan kalles av Claude.
    const fil = await $.tool.describe({ tool: MODELLNAVN('transkriber_fil'), description: 'Transkriberer en lokal lydfil', provider: { plugin: 'norsk-tale', tier } })
    expect(fil.description).toBe('Transkriberer en lokal lydfil')
    expect((await $.tool.check({ tool: MODELLNAVN('transkriber_fil'), input: { sti: '/a.wav' }, tool_use_id: 'm-fil' })).decision).toBe('allow')

    // Brukerens trykk, via modden, virker.
    const ui = await band($, 'terminal')
    await ui.press({ key: 'norsk' })
    await rec.driv()
    expect(rec.verktoy()[0]).toBe('start_opptak')
    expect(rec.fills.length).toBe(1)
  })
})

describe('norsk-tale: /norsk kalibrer', () => {
  test('starter riggen via serveren og holder tokenet utenfor kommandoteksten', async ($, on) => {
    const url = 'http://127.0.0.1:50123/?token=hemmeligtoken'
    const kall: string[] = []
    mock.clock(on)
    on('mcp.connect', () => ({ value: { isConnected: true as const, server: SERVER } }))
    on('mcp.call', ($, e) => { kall.push(e.tool); return svar({ url, apnet: true, allerede: false }) })
    on('ui.toast', () => ({ value: undefined }))
    on('ui.render', ($, e) => $.ui.resolve(e).Box({}))
    const r = await $.command.run({ command: 'norsk', args: 'kalibrer', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(r.text).toContain('Starter kalibreringsriggen')
    expect(r.text).not.toContain('hemmeligtoken')
    expect(kall).toEqual(['start_kalibrering'])
    const ui = await band($, 'terminal')
    expect(await ui.find({ type: 'Text', text: /Kalibreringsriggen: http:\/\/127\.0\.0\.1:50123\/\?token=hemmeligtoken/ })).toBeDefined()
  })
})
