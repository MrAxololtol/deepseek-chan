/**
 * DeepSeek-chan — opencode plugin bridge.
 *
 * Translates opencode events into a line-oriented event log that the Python
 * overlay tails, and makes sure the overlay is running.
 *
 * Install with:  deepseek-chan install-plugin
 * or drop this file in  ~/.config/opencode/plugins/
 */

import { spawn } from "node:child_process"
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const THINK_THROTTLE_MS = 800

const TEST_HINTS = [
  "test",
  "pytest",
  "jest",
  "vitest",
  "cargo test",
  "go test",
  "build",
  "make",
  "tsc",
  "lint",
  "ruff",
  "eslint",
]
const FAIL_HINTS = ["fail", "error", "traceback", "exception", "not ok", "assert"]

function looksLikeTest(cmd) {
  const c = String(cmd || "").toLowerCase()
  return TEST_HINTS.some((h) => c.includes(h))
}

function classify(cmd, out) {
  const text = String(out || "").toLowerCase()
  const failed = FAIL_HINTS.some((h) => text.includes(h))
  return failed ? "fail" : "ok"
}

function cacheDir() {
  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local")
    return join(base, "deepseek-chan", "Cache")
  }
  if (process.platform === "darwin") {
    return join(homedir(), "Library", "Caches", "deepseek-chan")
  }
  const base = process.env.XDG_CACHE_HOME || join(homedir(), ".cache")
  return join(base, "deepseek-chan")
}

const DIR = cacheDir()
const EVENTS = join(DIR, "events.ndjson")
const STATE = join(DIR, "state.json")
const PID = join(DIR, "pet.pid")

function emit(kind, detail = "") {
  try {
    mkdirSync(DIR, { recursive: true })
    const record = { kind, detail, ts: Date.now() / 1000 }
    appendFileSync(EVENTS, JSON.stringify(record) + "\n")
    writeFileSync(STATE, JSON.stringify(record))
  } catch {
    /* the pet is best-effort; never break the session */
  }
}

function isRunning(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

function ensureRunning() {
  try {
    const pid = parseInt(readFileSync(PID, "utf8").trim(), 10)
    if (Number.isFinite(pid) && isRunning(pid)) return
  } catch {
    /* no pid file yet */
  }
  const attempts = [
    ["deepseek-chan", ["run"]],
    ["python3", ["-m", "deepseek_chan"]],
    ["python", ["-m", "deepseek_chan"]],
  ]
  for (const [cmd, args] of attempts) {
    try {
      const child = spawn(cmd, args, { detached: true, stdio: "ignore" })
      child.unref()
      if (child.pid) {
        mkdirSync(DIR, { recursive: true })
        writeFileSync(PID, String(child.pid))
        return
      }
    } catch {
      /* try the next interpreter */
    }
  }
}

let lastThink = 0
function think() {
  const now = Date.now()
  if (now - lastThink < THINK_THROTTLE_MS) return
  lastThink = now
  emit("thinking")
}

export const DeepSeekChanPlugin = async () => {
  ensureRunning()
  emit("activity")

  const pending = new Map()

  return {
    event: async ({ event }) => {
      switch (event?.type) {
        case "session.idle":
          emit("finished")
          break
        case "session.error":
          emit("error", event?.properties?.error?.name || "")
          break
        case "message.part.updated":
          think()
          break
        case "permission.asked":
        case "session.created":
        case "session.updated":
          emit("activity")
          break
        default:
          break
      }
    },
    "tool.execute.before": async (input, output) => {
      ensureRunning()
      const tool = input?.tool || ""
      if (tool === "bash" && input?.callID) {
        pending.set(input.callID, output?.args?.command || "")
      }
      emit("working", tool)
    },
    "tool.execute.after": async (input, output) => {
      const cmd = pending.get(input?.callID)
      pending.delete(input?.callID)
      if (cmd && looksLikeTest(cmd)) {
        const result = output?.output ?? output?.result ?? output?.metadata?.output ?? ""
        emit("tool_result", `test:${classify(cmd, result)}`)
      }
      emit("activity")
    },
    "chat.message": async () => {
      ensureRunning()
    },
  }
}

export default DeepSeekChanPlugin
