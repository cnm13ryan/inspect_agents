# Vending-Bench: Long-Horizon Agent Benchmark

A reproducible long-horizon benchmark where an Inspect agent operates a vending-machine business for hundreds of simulated days, tracking net worth, units sold, and tool efficiency over episodes spanning tens of millions of tokens.

## Overview

Vending-Bench provides a deterministic simulator paired with Inspect-compliant tooling and a supervisor plus sub-agent hierarchy to sustain coherent control over multi-day business operations. The benchmark challenges agents to maintain stable long-run profitability while operating within Inspect guardrails (limits, logging, validation) across 2000-message episodes.

## Key Features

- **Deterministic Simulation**: Explicit seeds control demand noise, supplier timings, and stochastic components
- **Multi-Agent Architecture**: Supervisor agent for strategy/planning, physical sub-agent for operational tasks
- **Memory Management**: Scratchpad, key-value store, and vector database tools to handle long-term context
- **Financial Complexity**: Cash flow management, supplier negotiations, inventory optimization, demand elasticity
- **Observability**: Comprehensive logging of tool usage, metrics, and decision patterns

## Quick Start

### Prerequisites

- Python 3.12+
- UV package manager
- Inspect AI framework

### Installation

```bash
# From the repository root
uv sync
```

### Running a Basic Episode

```bash
# Run a short evaluation episode
uv run python -m examples.vending_bench.run --episodes 1 --max-messages 100

# Run full benchmark episode
uv run python -m examples.vending_bench.run --episodes 1 --max-messages 2000
```

### Running Tests

```bash
# Unit tests
uv run pytest -q tests/unit/vending_bench/

# Integration tests
uv run pytest -q tests/integration/vending_bench/

# Mirror sync tests
uv run pytest -q tests/unit/vending_bench -k mirror_sync
```

## Architecture

### Environment Simulation
- **State Management**: Time (day, minute), cash balances, inventories, orders, email, demand parameters
- **Daily Cycle**: Morning updates, agent interactions, order processing, demand simulation
- **Financial Model**: Machine cash vs liquid balance, daily fees, buffer management
- **Supplier System**: Web search integration, deterministic quote generation, lead time tracking

### Agent Stack
- **Supervisor Agent**: Strategic planning, supplier negotiations, financial decisions
- **Physical Sub-Agent**: Mechanical operations (restocking, pricing, cash collection)
- **Tool Separation**: Supervisor tools (email, search, ordering) vs physical tools (restock, price, cash)

### Memory Strategy
- **Scratchpad**: Daily summaries and operational notes
- **Key-Value Store**: Structured supplier and order registries
- **Vector Database**: Email embeddings and searchable history
- **Context Management**: Periodic summarization to maintain working memory budget

## Configuration

Key configuration options in `examples/vending_bench/config.py`:

- `seed`: Deterministic seed for reproducible runs
- `max_days`: Episode length limit
- `starting_cash`: Initial capital
- `daily_fee`: Operating cost per day
- `memory_budget`: Context window management

## Evaluation Metrics

The benchmark tracks several key performance indicators:

- **Net Worth**: Final cash + inventory value - outstanding orders
- **Units Sold**: Total products sold across episode
- **Tool Efficiency**: Calls per category, time utilization
- **Cash Runway**: Days of operation before bankruptcy
- **Profitability**: Revenue vs costs over time

## Mirror Repository

This benchmark is mirrored to an external repository for public access and versioned releases. Use the mirror sync tool to package and deploy updates:

```bash
# Package artifacts for mirror deployment
uv run python tools/mirror_sync.py --source examples/vending_bench --target mirror-prep

# The CI pipeline will handle the actual mirror synchronization
```

See `mirror-repo/README.md` for details on the mirror repository structure and release process.

## Development

### Adding New Tools
1. Implement tool functions in `examples/vending_bench/tools.py`
2. Add Pydantic request/response models
3. Include tool in appropriate collection (supervisor_tools/physical_agent_tools)
4. Add unit tests in `tests/unit/vending_bench/test_tools.py`

### Modifying Environment
1. Update state model in `examples/vending_bench/env.py`
2. Adjust daily cycle logic as needed
3. Update demand model parameters
4. Add corresponding tests in `tests/unit/vending_bench/test_env.py`

### Memory Integration
1. Extend memory interfaces in `examples/vending_bench/memory.py`
2. Add new memory tools following existing patterns
3. Update memory_tools() collection
4. Test memory functionality in `tests/unit/vending_bench/test_tools.py`

## Troubleshooting

### Common Issues

**Agent runs out of cash**: Check daily fee settings, demand elasticity parameters, or starting capital
**Memory context overflow**: Adjust summarization frequency or memory budget limits
**Non-deterministic results**: Verify seed propagation across all random components
**Tool validation errors**: Check Pydantic model schemas match expected parameters

### Debug Mode

Run with debug logging enabled:

```bash
uv run python -m examples.vending_bench.run --debug --episodes 1
```

### Limits and Guardrails

The benchmark enforces several protective limits:
- 2000 message ceiling per episode
- Sub-agent handoff limits (8-24 messages)
- Memory context budgets
- Financial solvency checks

## Contributing

This benchmark is part of the larger `inspect_agents` framework. Follow the project's contribution guidelines and ensure:

1. All tests pass: `uv run pytest tests/unit/vending_bench/`
2. Code follows existing patterns and conventions
3. Changes maintain deterministic behavior
4. Documentation is updated appropriately

## License

See the main repository license for details.
