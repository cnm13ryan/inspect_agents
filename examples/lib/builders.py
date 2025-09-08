from __future__ import annotations

from typing import Any

"""Shared agent builders for examples.

Purpose
- Centralize composition of built-ins + standard tools + sub-agents to avoid
  drift between runners/tasks.

Functions
- build_research_supervisor(model, attempts, prompts_override=None,
  include_planner=False)
- build_exploration_supervisor(model, attempts, planner_cfg=None,
  prompts_override=None)

Notes
- Prompts and tool lists are kept verbatim from existing scripts.
  Callers may override prompts via `prompts_override` dict keys:
  {"supervisor", "research", "critique"}.
"""


def _builtins_and_standard_tools():
    # Local import to keep module import light
    from inspect_agents.tools import (
        edit_file,
        ls,
        read_file,
        standard_tools,
        update_todo_status,
        write_file,
        write_todos,
    )

    builtins = [write_todos(), update_todo_status(), write_file(), read_file(), ls(), edit_file()]
    return builtins + standard_tools()


def _build_subagents(model: Any, sub_configs: list[dict[str, Any]]):
    from inspect_agents.agents import build_subagents

    return build_subagents(configs=sub_configs, base_tools=_builtins_and_standard_tools(), default_model=model)


def _planner_tool_optional():
    """Return planner_tool() when available; else None.

    Import is local to avoid heavy imports when unused.
    """
    try:
        from .exploration.planner_tool import planner_tool  # type: ignore

        return planner_tool()
    except Exception:
        return None


def build_research_supervisor(
    model: Any,
    attempts: int,
    *,
    prompts_override: dict[str, str] | None = None,
    include_planner: bool = False,
):
    """Build the research composition supervisor.

    Prompts/tool lists preserved from examples/tasks/research_task.py.
    """
    from inspect_agents.agents import build_supervisor

    research_prompt = (prompts_override or {}).get("research") or (
        "You are a dedicated researcher. Your job is to conduct research based on the user's question.\n\n"
        "Conduct thorough research and then reply with a detailed answer."
    )
    critique_prompt = (prompts_override or {}).get("critique") or (
        "You are a dedicated editor tasked to critique a report.\n\n"
        "The report is in `final_report.md`; the question is in `question.txt`.\n"
        "Respond with a detailed critique and concrete improvements."
    )

    sub_configs = [
        {
            "name": "research-agent",
            "description": ("Used to research more in-depth questions. Only give this researcher one topic at a time."),
            "prompt": research_prompt,
            # Task variant: both sub-agents expose web_search
            "tools": ["web_search", "read_file", "write_file", "ls"],
            "mode": "handoff",
        },
        {
            "name": "critique-agent",
            "description": "Used to critique the final report.",
            "prompt": critique_prompt,
            "tools": ["web_search", "read_file", "write_file", "ls"],
            "mode": "handoff",
        },
    ]

    tools = _build_subagents(model, sub_configs)
    if include_planner:
        pt = _planner_tool_optional()
        if pt is not None:
            tools = [pt] + tools

    sup = build_supervisor(
        prompt=(prompts_override or {}).get("supervisor", "You are a helpful researcher."),
        tools=tools,
        attempts=attempts,
        model=model,
    )
    return sup


def build_exploration_supervisor(
    model: Any,
    attempts: int,
    *,
    planner_cfg: dict[str, Any] | None = None,
    prompts_override: dict[str, str] | None = None,
):
    """Build the exploration composition supervisor (planner → research → critique).

    Prompts/tool lists preserved from examples/inspect/exploration/runner.py.
    """
    import json as _json

    from inspect_agents.agents import build_supervisor

    def _supervisor_prompt() -> str:
        cfg_text = "\nPlanner config (JSON):\n" + _json.dumps(planner_cfg, ensure_ascii=False) if planner_cfg else ""
        preface = (
            ((prompts_override or {}).get("supervisor", "") + "\n\n")
            if (prompts_override or {}).get("supervisor")
            else ""
        )
        return (
            preface + "You are the orchestrator of a small research workflow.\n\n"
            "Goal\n"
            "- Generate a plan via planner_tool, write it to plan.json.\n"
            "- Write the user's question verbatim to question.txt.\n"
            "- Handoff to research-agent to execute the plan and write final_report.md.\n"
            "- After that, handoff to critique-agent for an editorial pass; then return.\n\n"
            "Instructions\n"
            "1) Call planner_tool with prompt=<user input>. If a planner config is provided below, pass it as the 'config' argument.\n"
            "   - If planner_tool errors or returns invalid output, immediately write a minimal fallback plan to plan.json:\n"
            '     {"queries": [{"query": <user input>, "depth": 1, "tags": ["seed"]}], "breadth": 1, "depth": 1}.\n'
            "2) Save the plan JSON to plan.json using write_file (even for fallback).\n"
            "3) Save the input question to question.txt using write_file.\n"
            "4) Handoff to research-agent (transfer_to_research-agent).\n"
            "5) After it finishes, handoff to critique-agent (transfer_to_critique-agent).\n"
            "Important: Use one tool call at a time; avoid parallel tool invocations.\n" + cfg_text
        )

    def _research_prompt() -> str:
        override = (prompts_override or {}).get("research")
        if override:
            return override
        return (
            "You are the research-agent.\n\n"
            "- Read plan.json and question.txt.\n"
            "- Execute the planned queries serially (top items first). Prefer web_search when available;\n"
            "  if unavailable, synthesize from context and still write a report.\n"
            "- If plan.json is missing or has no queries, synthesize a minimal plan with the user's question as the only query and proceed.\n"
            "- Capture findings with concise evidence and include inline citations like [1], [2], etc.,\n"
            "  followed by a References section mapping numbers to sources (title + URL when web_search is used).\n"
            "- Write a single markdown report to final_report.md using write_file.\n"
            "- Keep outputs grounded, structured, and complete.\n"
        )

    def _critique_prompt() -> str:
        override = (prompts_override or {}).get("critique")
        if override:
            return override
        return (
            "You are the critique-agent.\n\n"
            "- Read final_report.md and question.txt.\n"
            "- Improve structure, clarity, completeness, and citation hygiene.\n"
            "- Make edits directly and overwrite final_report.md using write_file.\n"
            "- Keep the original research question and scope unchanged.\n"
        )

    sub_configs = [
        {
            "name": "research-agent",
            "description": ("Used to research more in-depth questions. Only give this researcher one topic at a time."),
            "prompt": _research_prompt(),
            "tools": ["web_search", "read_file", "write_file", "ls"],
            "mode": "handoff",
        },
        {
            "name": "critique-agent",
            "description": "Used to critique the final report.",
            "prompt": _critique_prompt(),
            # Runner variant: critique-agent does not include web_search
            "tools": ["read_file", "write_file", "ls"],
            "mode": "handoff",
        },
    ]

    tools = _build_subagents(model, sub_configs)
    pt = _planner_tool_optional()
    if pt is not None:
        tools = [pt] + tools

    sup = build_supervisor(
        prompt=_supervisor_prompt(),
        tools=tools,
        attempts=attempts,
        model=model,
    )
    return sup
