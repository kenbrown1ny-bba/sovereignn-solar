# Sovereign Solar — AI Sales Engine

An AI-powered solar sales engine built with Claude (Anthropic). Uses a recursive agentic loop to manage customer conversations, track workflow stages, and maintain persistent customer memory via the Sovereign Vault.

## Features

- **Recursive Loop Engine** — Each customer interaction runs through a stage-aware AI prompt, advancing the sale automatically based on conversation signals
- **Sovereign Vault** — JSON-based persistent store for customer records, conversation history, and workflow metadata
- **7-Stage Workflow** — Lead → Qualified → Site Assessment → Proposal → Negotiation → Closed Won / Closed Lost
- **Prompt Caching** — Uses Anthropic prompt caching to reduce costs on large customer histories
- **TypeScript** — Fully typed for reliability

## Workflow Stages

| Stage | Description |
|---|---|
| `lead` | First contact, qualify interest and bill size |
| `qualified` | Confirmed homeowner with high bill, schedule assessment |
| `site_assessment` | Roof/shading evaluated, sizing in progress |
| `proposal` | Custom quote delivered, ROI presented |
| `negotiation` | Addressing objections, finalizing financing |
| `closed_won` | Contract signed, installation scheduled |
| `closed_lost` | Customer declined, nurture for referrals |

## Setup

```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Build
npm run build

# Run
npm start
```

## Development

```bash
# Run directly with ts-node
npm run dev

# Run tests
npm test
```

## Architecture

```
sovereign_recursive_loop_v2.ts   # Main agentic loop & stage transitions
sovereign_vault_mcp.ts           # Customer memory store
test_recursive_loop.ts           # Test suite
```

### Loop Flow

```
Incoming Message
      │
      ▼
 Load customer from Vault
      │
      ▼
 Select stage-specific system prompt
      │
      ▼
 Call Claude (with cached history)
      │
      ▼
 Evaluate stage transition signals
      │
      ▼
 Save updated record + message to Vault
      │
      ▼
 Return response + next action
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `VAULT_PATH` | No | Path to vault JSON file (default: `./data/vault.json`) |
| `PORT` | No | Server port (default: 3000) |
| `NODE_ENV` | No | `development` or `production` |

## License

MIT
