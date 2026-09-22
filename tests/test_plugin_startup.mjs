/** MIT. Startup failures must never terminate the opencode host process. */
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { readFileSync } from 'node:fs'
import { posix } from 'node:path'
import test from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'

const source = readFileSync(new URL('../src/mochi/plugin/mochi-pet.js', import.meta.url), 'utf8')

async function start({ failures = 0, alive = false, storedPid = '4242' } = {}) {
  const commands = []
  const writes = []
  const live = new Set(alive ? [4242] : [])
  const context = createContext({
    process: {
      platform: 'linux', env: { XDG_CACHE_HOME: '/virtual' },
      kill(pid, signal) {
        assert.ok(pid > 0, 'never probe an entire process group')
        assert.equal(signal, 0)
        if (!live.has(pid)) throw new Error('ESRCH')
      },
    },
  })
  const adapters = {
    'node:child_process': {
      spawn(command, args, options) {
        commands.push(command)
        assert.equal(options.detached, true)
        const child = new EventEmitter()
        child.pid = 5000 + commands.length
        child.unref = () => {}
        queueMicrotask(() => {
          if (commands.length <= failures) child.emit('error', new Error('ENOENT'))
          else { live.add(child.pid); child.emit('spawn') }
        })
        return child
      },
    },
    'node:fs': {
      readFileSync() { return storedPid },
      mkdirSync() {}, appendFileSync() {},
      writeFileSync(path) { writes.push(path) },
    },
    'node:os': { homedir: () => '/home/test' },
    'node:path': { join: posix.join },
  }
  const module = new SourceTextModule(source, { context })
  await module.link((name) => {
    const values = adapters[name]
    assert.ok(values)
    return new SyntheticModule(Object.keys(values), function () {
      for (const [key, value] of Object.entries(values)) this.setExport(key, value)
    }, { context })
  })
  await module.evaluate()
  const hooks = await module.namespace.MochiPlugin()
  return { hooks, commands, writes, live }
}

test('existing live process is reused', async () => {
  const { commands } = await start({ alive: true })
  assert.deepEqual(commands, [])
})

test('asynchronous ENOENT falls back and PID ownership stays with Python', async () => {
  const { commands, writes } = await start({ failures: 2 })
  assert.deepEqual(commands, ['mochi', 'python3', 'python'])
  assert.ok(writes.every(path => !path.endsWith('pet.pid')))
})

test('all missing executables are best-effort, not a rejected plugin', async () => {
  const { commands, hooks } = await start({ failures: 99 })
  assert.equal(commands.length, 3)
  assert.equal(typeof hooks.event, 'function')
})

test('repeated hooks do not launch duplicates before the PID file appears', async () => {
  const { hooks, commands } = await start()
  await Promise.all([hooks['chat.message'](), hooks['chat.message'](), hooks['chat.message']()])
  assert.deepEqual(commands, ['mochi'])
})

test('dead child is relaunched once across concurrent hooks', async () => {
  const { hooks, commands, live } = await start()
  live.clear()
  await Promise.all([hooks['chat.message'](), hooks['chat.message']()])
  assert.deepEqual(commands, ['mochi', 'mochi'])
})

test('PID zero is ignored', async () => {
  const { commands } = await start({ storedPid: '0' })
  assert.deepEqual(commands, ['mochi'])
})
