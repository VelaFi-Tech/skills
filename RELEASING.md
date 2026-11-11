# Releasing

Claude Code and the Claude plugin directory decide whether a plugin has an update from the `version` in `plugins/velafi/.claude-plugin/plugin.json`. If a change is merged without a new version, users who already installed the plugin never receive it.

For every pull request that changes anything under `plugins/velafi/`:

1. Raise `version` in `plugins/velafi/.claude-plugin/plugin.json` in the same pull request:
   - patch (`1.1.0` → `1.1.1`): wording fixes and small corrections;
   - minor (`1.1.0` → `1.2.0`): new or changed skill behaviour, references, scripts or templates;
   - major (`1.1.0` → `2.0.0`): a skill is removed or renamed, or the plugin name changes.
2. Run `claude plugin validate --strict ./plugins/velafi` and fix anything it reports.
3. After merging, the plugin directory listing picks up the new version for review.

Set `version` only in `plugin.json`, never in `.claude-plugin/marketplace.json`.
