# Somewhere — city exploration RPG prototype

A showcase prototype for **wireframe-lofi**: a city exploration app that turns wandering into quests and memories.

## Flow

`home → quest → exploring → discovered → memory → journal`

Secondary tabs: `collection`, `profile`.

## Render

```bash
cd examples/somewhere
../../../render.sh --kit kit/components.yaml --mockup theme.yaml --bundle *.wf.yaml
```

For pure low-fi review, omit `--mockup theme.yaml`.

The prototype intentionally exercises project kit components, canvas, shared layouts, routes/links, semantic states, scrollable phone layout, and theme bindings.
