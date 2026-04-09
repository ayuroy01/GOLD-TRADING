# Gold V1 Execution Workbench

This project wraps the original strategy assets in a runnable React application without rewriting the authored source material.

## Included source of truth

- `gold_v1_system_rules.json`
- `v1_system_and_math_foundation.md`
- `gold_v1_journal.jsx`

## What was added

- Vite + React execution scaffold
- responsive strategy dashboard and reading views
- rendered Markdown foundation panel
- rendered rules panel from the JSON system definition
- embedded journal workspace using the original JSX component
- test and build pipeline

## Commands

```bash
npm install
npm run dev
npm run verify
```

## Notes

The journal component is kept as its own authored file and embedded directly into the app shell.
