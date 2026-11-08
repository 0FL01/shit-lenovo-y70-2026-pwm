// OpenCode V2.2.6 Promise plugin.
// No dependencies. No compaction hooks.

import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

const ID = "horizon-pwm"
const EVERY = 7
const MAX_RESUMES = 6400
const GOAL_PATH = ".opencode/horizon-goal.md"
const DONE = "[[PWM_VERIFIED]]"
const BLOCKED = "[[OWNER_REQUIRED]]"

const fresh = () => ({
  active: false,
  steps: 0,
  resumes: 0,
  stalls: 0,
})

const key = (id) => `session:${id}`

const txt = (message) =>
  (message?.content ?? [])
    .filter((part) => part.type === "text")
    .map((part) => part.text ?? "")
    .join("\n")

export default {
  id: ID,

  async setup(ctx) {
    const jobs = new Map()
    const hooks = []

    // Serialize operations within the same session.
    const run = (id, action) => {
      const job = (jobs.get(id) ?? Promise.resolve())
        .catch(() => {})
        .then(action)

      jobs.set(id, job)

      void job
        .finally(() => {
          if (jobs.get(id) === job) jobs.delete(id)
        })
        .catch(() => {})

      return job
    }

    const load = async (id) => ({
      ...fresh(),
      ...(await ctx.storage.get(key(id)) ?? {}),
    })

    const save = (id, state) =>
      ctx.storage.set(key(id), state)

    const root = async (id) =>
      !(await ctx.session.get({ sessionID: id })).parentID

    const goal = async () => {
      const value = (
        await readFile(
          resolve(ctx.location.directory, GOAL_PATH),
          "utf8",
        )
      ).trim()

      if (!value || value.length > 60000) {
        throw new Error(
          `${GOAL_PATH}: goal must be 1-60000 characters`,
        )
      }

      return value
    }

    const nudge = (objective, stalled = false) => [
      "[HORIZON: PWM RESEARCH]",
      `Цель: ${objective}`,
      "Неудача гипотезы НЕ доказывает невозможность цели.",
      "Не закрывай исследование отчётом о тупике.",
      "Новая гипотеза -> проверка -> инструмент -> факт -> следующий шаг.",
      stalled
        ? "СТАГНАЦИЯ: смени метод (DDIC/DSI/драйвер/оптика/дампы)."
        : "",
      "Факт != гипотеза. Никаких фиктивных 2000 Hz.",
      "Соблюдай согласованные границы аппаратных операций.",
    ].filter(Boolean).join("\n")

    // Every 7th primary request: ephemeral tail injection.
    // Nothing is written into the persistent conversation.
    hooks.push(
      await ctx.session.hook("context", (event) =>
        run(event.sessionID, async () => {
          try {
            if (!(await root(event.sessionID))) return

            const s = await load(event.sessionID)
            if (!s.active) return

            s.steps++
            await save(event.sessionID, s)

            if (s.steps % EVERY !== 0) return

            event.messages.push({
              role: "user",
              content: [{
                type: "text",
                text: nudge(await goal(), s.stalls >= 2),
              }],
            })
          } catch (error) {
            console.warn("[horizon] nudge:", error)
          }
        }),
      ),
    )

    // When the agent finishes normally, continue if needed.
    hooks.push(
      await ctx.session.hook("experimental.idle", (event) =>
        run(event.sessionID, async () => {
          try {
            if (!(await root(event.sessionID))) return

            const s = await load(event.sessionID)
            if (!s.active) return

            // Do not interfere with running parent-owned jobs.
            if (event.background.some(
              (item) => item.sessionID === event.sessionID
            )) return

            const history = await ctx.session.context({
              sessionID: event.sessionID,
            })

            const pulse = history.findLastIndex(
              (m) =>
                m.type === "synthetic" &&
                m.metadata?.source === ID,
            )

            const user = history.findLastIndex(
              (m) => m.type === "user",
            )

            const lastUser = user > pulse
              ? history[user]?.text?.trim() ?? ""
              : ""

            if (/^(стоп|хватит|остановись|stop|pause|cancel)[.!\s]*$/iu.test(lastUser)) {
              s.active = false
              await save(event.sessionID, s)
              return
            }

            const answer = history.findLast(
              (m) => m.type === "assistant",
            )

            const lines = txt(answer)
              .split(/\r?\n/)
              .map((line) => line.trim())

            if (
              lines.includes(DONE) ||
              lines.includes(BLOCKED)
            ) {
              s.active = false
              await save(event.sessionID, s)
              return
            }

            if (s.resumes >= MAX_RESUMES) {
              s.active = false
              await save(event.sessionID, s)
              console.warn(
                "[horizon] auto-resume budget exhausted",
              )
              return
            }

            const usedTool = pulse < 0 ||
              history.slice(pulse + 1).some(
                (m) =>
                  m.type === "assistant" &&
                  m.content?.some(
                    (part) => part.type === "tool",
                  ),
              )

            s.stalls = usedTool ? 0 : s.stalls + 1
            s.resumes++

            await save(event.sessionID, s)

            const message = s.stalls >= 2
              ? [
                  "HORIZON: цель не доказана.",
                  "Два цикла без инструментов.",
                  "СМЕНИ исследовательскую ось.",
                  "Используй инструменты, проверь новую гипотезу.",
                  "Не пиши очередной финальный отчёт.",
                ].join(" ")
              : [
                  "HORIZON: цель не доказана.",
                  "Продолжай конкретным экспериментом",
                  "или офлайн-реверсом.",
                  "Отрицательный результат закрывает",
                  "гипотезу, не задачу.",
                ].join(" ")

            await ctx.session.synthetic({
              sessionID: event.sessionID,
              text: message,
              metadata: { source: ID },
            })
          } catch (error) {
            console.warn(
              "[horizon] idle disabled after error:",
              error,
            )

            try {
              await save(event.sessionID, {
                ...(await load(event.sessionID)),
                active: false,
              })
            } catch {
              // Preserve the original error.
            }
          }
        }),
      ),
    )

    hooks.push(
      await ctx.command.transform((editor) => {
        editor.add({
          name: "horizon-on",
          description: "Start long-horizon PWM research",

          execute: (input) =>
            run(input.sessionID, async () => {
              if (!(await root(input.sessionID))) {
                throw new Error(
                  "Use horizon-on in a root session",
                )
              }

              const objective = await goal()

              await save(input.sessionID, {
                active: true,
                steps: 0,
                resumes: 0,
                stalls: 0,
              })

              await ctx.session.synthetic({
                sessionID: input.sessionID,
                text:
                  nudge(objective) +
                  "\nСейчас сделай первый проверяемый шаг.",
                metadata: { source: ID },
                delivery: input.delivery,
              })
            }),
        })

        editor.add({
          name: "horizon-off",
          description: "Stop automatic continuation",

          execute: (input) =>
            run(input.sessionID, async () =>
              save(input.sessionID, {
                ...(await load(input.sessionID)),
                active: false,
              }),
            ),
        })
      }),
    )

    return async () => {
      await Promise.all(
        hooks.map((registration) =>
          registration.dispose(),
        ),
      )

      jobs.clear()
    }
  },
}

