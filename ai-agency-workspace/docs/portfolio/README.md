# TheOffice Portfolio

Curated reusable components, patterns, and architectures harvested from completed projects.

## Structure

- `_index.json` — fast lookup registry of all entries (slug, tags)
- `{slug}/manifest.yaml` — metadata for each artifact (summary, language, files, originating_project)
- `{slug}/assets/` — copied code files (preserved directory structure relative to source)

## Adding Entries

Grace (DevOps + Portfolio Curator) populates the portfolio at the end of each project's `prod` stage (portfolio_contribute task).

Each entry gets a `manifest.yaml` with:
- `slug`: kebab-case unique identifier
- `summary`: one-line description
- `tags`: structured tags (pattern:*, domain:*, stack:*, feature:*)
- `language`: primary language
- `originating_project`: source project id
- `files`: list of relative paths in assets/
- `added_at`: ISO 8601 timestamp

## Querying the Portfolio

Linus (CTO) queries the portfolio before writing any spec. Fast lookup via `_index.json`, then reads manifest.yaml for detailed matching.

Tags enable structured filtering:
- `pattern:pub_sub` — architectural pattern for message-driven systems
- `domain:agent_orchestration` — multi-agent coordination
- `stack:python` — Python implementation
- `stack:mqtt` — MQTT messaging broker

## Example Entry

See `mqtt_trinity_template/` for the HQ/Broker/Branch trinity pattern that powers TheOffice V1.
