/** MIT. Execute the actual plugin in an isolated VM with in-memory OS adapters.
 * Run: node --experimental-vm-modules tests/test_plugin.mjs
 * No overlay process is launched and no user cache is written.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { posix } from 'node:path'
import test from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'

const source = readFileSync(new URL('../src/mochi/plugin/mochi-pet.js', import.meta.url), 'utf8')

async function harness({
  platform = 'linux', env = { XDG_CACHE_HOME: '/virtual/cache' },
  expectedCache = '/virtual/cache/mochi',
} = {}) {
  const records = []
  let now = 10000
  const context = createContext({
    Date: class extends Date { static now() { return now } },
    process: {
      platform, env,
      kill(pid, signal) { assert.equal(pid, 4242); assert.equal(signal, 0) },
    },
  })
  const adapters = {
    'node:child_process': { spawn() { assert.fail('a live pet must not be relaunched') } },
    'node:fs': {
      appendFileSync(path, line) {
        assert.equal(path, expectedCache + '/events.ndjson')
        assert.ok(line.endsWith('\n'))
        records.push(JSON.parse(line))
      },
      mkdirSync() {},
      readFileSync(path) { assert.ok(path.endsWith('/pet.pid')); return '4242' },
      writeFileSync(path, value) {
        assert.ok(path.endsWith('/state.json'))
        assert.deepEqual(JSON.parse(value), records.at(-1))
      },
    },
    'node:os': { homedir: () => '/virtual/home' },
    'node:path': { join: posix.join },
  }
  const module = new SourceTextModule(source, { context })
  await module.link((specifier) => {
    const exports = adapters[specifier]
    assert.ok(exports, `unexpected import: ${specifier}`)
    return new SyntheticModule(Object.keys(exports), function () {
      for (const [name, value] of Object.entries(exports)) this.setExport(name, value)
    }, { context })
  })
  await module.evaluate()
  const hooks = await module.namespace.MochiPlugin()
  assert.deepEqual(records.map(r => r.kind), ['activity'])
  records.length = 0
  return { hooks, records, advance: ms => { now += ms } }
}

test('session events map to stable event kinds and details', async () => {
  const { hooks, records } = await harness()
  for (const type of ['session.created', 'session.updated', 'permission.asked', 'session.idle']) {
    await hooks.event({ event: { type } })
  }
  await hooks.event({ event: { type: 'session.error', properties: { error: { name: 'Timeout' } } } })
  assert.deepEqual(records.map(({ kind, detail }) => [kind, detail]), [
    ['activity', ''], ['activity', ''], ['activity', ''], ['finished', ''], ['error', 'Timeout'],
  ])
  assert.ok(records.every(r => r.ts === 10))
})

test('thinking is throttled and unknown events do not emit', async () => {
  const { hooks, records, advance } = await harness()
  const update = () => hooks.event({ event: { type: 'message.part.updated' } })
  await update()
  advance(799)
  await update()
  advance(1)
  await update()
  await hooks.event({ event: { type: 'unknown' } })
  await hooks.event({ event: undefined })
  assert.deepEqual(records.map(r => r.kind), ['thinking', 'thinking'])
})

test('tool hooks match interleaved call IDs and classify results', async () => {
  const { hooks, records } = await harness()
  await hooks['tool.execute.before']({ tool: 'bash', callID: 'a' }, { args: { command: 'pytest' } })
  await hooks['tool.execute.before']({ tool: 'bash', callID: 'b' }, { args: { command: 'npm run build' } })
  await hooks['tool.execute.after']({ callID: 'b' }, { output: 'build completed' })
  await hooks['tool.execute.after']({ callID: 'a' }, { output: 'AssertionError: failed' })
  assert.deepEqual(records.map(({ kind, detail }) => [kind, detail]), [
    ['working', 'bash'], ['working', 'bash'], ['tool_result', 'test:ok'], ['activity', ''],
    ['tool_result', 'test:fail'], ['activity', ''],
  ])
  records.length = 0
  await hooks['tool.execute.after']({ callID: 'a' }, { output: 'failed' })
  assert.deepEqual(records.map(r => r.kind), ['activity'])
})

test('non-test commands only refresh activity after completion', async () => {
  const { hooks, records } = await harness()
  await hooks['tool.execute.before']({ tool: 'bash', callID: 'a' }, { args: { command: 'pwd' } })
  await hooks['tool.execute.after']({ callID: 'a' }, { output: '/project' })
  assert.deepEqual(records.map(r => r.kind), ['working', 'activity'])
})

test('test result fallbacks and missing error details are supported', async () => {
  const { hooks, records } = await harness()
  for (const output of [{ result: 'ok' }, { metadata: { output: 'error' } }]) {
    await hooks['tool.execute.before']({ tool: 'bash', callID: 'a' }, { args: { command: 'ruff check .' } })
    await hooks['tool.execute.after']({ callID: 'a' }, output)
  }
  await hooks.event({ event: { type: 'session.error' } })
  assert.deepEqual(records.filter(r => r.kind === 'tool_result').map(r => r.detail), ['test:ok', 'test:fail'])
  assert.deepEqual(records.at(-1), { kind: 'error', detail: '', ts: 10 })
})

for (const [platform, env, expectedCache] of [
  ['win32', { LOCALAPPDATA: '/virtual/local' }, '/virtual/local/mochi/mochi/Cache'],
  ['darwin', {}, '/virtual/home/Library/Caches/mochi'],
  ['linux', {}, '/virtual/home/.cache/mochi'],
]) {
  test(`cache location matches platformdirs convention on ${platform}`, async () => {
    const { hooks, records } = await harness({ platform, env, expectedCache })
    await hooks.event({ event: { type: 'session.idle' } })
    assert.equal(records[0].kind, 'finished')
  })
}
