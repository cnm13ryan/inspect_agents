"""Simple Agent Architecture Demo (examples only).

This example demonstrates the conceptual simple architecture by composing
Inspect Agents public surfaces:

- Agent builders: `build_supervisor`, `build_iterative_agent`
- Approvals presets: `approval_preset`, `activate_approval_policies`
- Tools: file + optional standard tools (enabled via env), plus two demo tools
  defined here (environment + key/value memory).

Run examples:

  uv run python -m examples.demos.simple_arch_demo "Research topic ..."

Options:
  --mode supervisor|iterative   Choose agent style (default: supervisor)
  --dev-approvals               Enable dev approval preset (handoff exclusivity,
                                parallel kill-switch, and dev gating)

Note: This is an examples-only scaffold. Library code lives under
`src/inspect_agents/` and should be used directly in projects/tests.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from inspect_agents.agents import build_iterative_agent, build_supervisor
from inspect_agents.approval import activate_approval_policies, approval_preset
from inspect_agents.run import run_agent

# --- Demo Environment & Memory Tools (example-local) -------------------------

try:
    # Import lazily to avoid heavy import during docs builds
    from inspect_ai.tool import Tool, ToolResult, tool  # type: ignore
except Exception:  # pragma: no cover - only used when running the example
    Tool = object  # type: ignore
    ToolResult = object  # type: ignore


@dataclass
class InMemoryTextEnv:
    description: str
    stop_on: str = "exit"
    max_steps: int = 10
    steps: int = 0
    log: list[str] = field(default_factory=list)

    def reset(self) -> str:
        self.steps = 0
        self.log.clear()
        return f"Env: {self.description} (max_steps={self.max_steps}, stop='{self.stop_on}')"

    def step(self, action: str) -> tuple[str, bool]:
        self.steps += 1
        self.log.append(action)
        done = action.strip().lower() == self.stop_on.lower() or self.steps >= self.max_steps
        obs = f"Observed action[{self.steps}]: {action} | done={done}"
        return obs, done


def environment_tools(env: InMemoryTextEnv) -> list[Tool]:
    last_obs = {"text": env.reset()}

    @tool(name="env_observe", parallel=False)
    def env_observe() -> Tool:  # type: ignore[valid-type]
        async def execute() -> ToolResult:
            return last_obs["text"]

        return execute

    @tool(name="env_act", parallel=False)
    def env_act() -> Tool:  # type: ignore[valid-type]
        async def execute(action: str) -> ToolResult:
            obs, done = env.step(action)
            last_obs["text"] = obs
            return f"{obs}"

        return execute

    return [env_observe(), env_act()]


@dataclass
class KVMemory:
    capacity: int = 256
    data: dict[str, str] = field(default_factory=dict)

    def put(self, key: str, value: str) -> None:
        if len(self.data) >= self.capacity and key not in self.data:
            first = next(iter(self.data))
            self.data.pop(first, None)
        self.data[key] = value

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def items(self) -> list[tuple[str, str]]:
        return list(self.data.items())


def memory_tools(mem: KVMemory) -> list[Tool]:
    @tool(name="write_memory", parallel=False)
    def write_memory() -> Tool:  # type: ignore[valid-type]
        async def execute(key: str, value: str) -> ToolResult:
            mem.put(key, value)
            return f"OK: wrote key='{key}'"

        return execute

    @tool(name="read_memory", parallel=False)
    def read_memory() -> Tool:  # type: ignore[valid-type]
        async def execute(key: str) -> ToolResult:
            val = mem.get(key)
            return val if val is not None else ""

        return execute

    @tool(name="list_memory", parallel=False)
    def list_memory() -> Tool:  # type: ignore[valid-type]
        async def execute() -> ToolResult:
            pairs = mem.items()
            if not pairs:
                return "[]"
            return "\n".join([f"{k}: {v}" for k, v in pairs])

        return execute

    return [write_memory(), read_memory(), list_memory()]


# --- Runner ------------------------------------------------------------------


async def _build_agent(mode: str, extra_tools: list[object]):
    prompt = (
        "You are the main orchestrator. Use tools (env_*, *_memory) to gather "
        "information and act. Call submit with a final answer when done."
    )
    if mode == "iterative":
        return build_iterative_agent(prompt=prompt, tools=extra_tools)
    return build_supervisor(prompt=prompt, tools=extra_tools)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", help="User task to solve")
    ap.add_argument("--mode", choices=["supervisor", "iterative"], default="supervisor")
    ap.add_argument("--dev-approvals", action="store_true", help="Enable dev approval preset")
    args = ap.parse_args()

    if args.dev_approvals:
        activate_approval_policies(approval_preset("dev"))

    env = InMemoryTextEnv(description="Toy environment with textual actions")
    mem = KVMemory()
    tools = environment_tools(env) + memory_tools(mem)

    agent = await _build_agent(args.mode, tools)
    state = await run_agent(agent, args.task)
    print("\n=== Final Output ===\n")
    try:
        print(state.output.completion)
    except Exception:
        print("[no output]")


if __name__ == "__main__":
    asyncio.run(main())
