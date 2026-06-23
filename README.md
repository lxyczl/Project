# SKILLS

Academic paper writing assistant skills for Claude Code.

## Skills

| Skill | Branch | Description |
|-------|--------|-------------|
| [paper-rewriter](.claude/skills/paper-rewriter/) | `paper-rewriter` | English paper rewriting to reduce AIGC detection |
| [paper-rewriter-zh](.claude/skills/paper-rewriter-zh/) | `paper-rewriter-zh` | Chinese paper rewriting to reduce AIGC detection |
| [AIGC-rewriter-zh](.claude/skills/AIGC-rewriter-zh/) | `AIGC-rewriter-zh` | Chinese AIGC detection rate reducer (知网/维普) |
| [AIGC-rewriter](.claude/skills/AIGC-rewriter/) | `AIGC-rewriter` | English AIGC detection rate reducer (WIP) |

## Branch Structure

Each skill has its own branch for independent development:

```
master              ← this branch (skill index)
paper-rewriter      ← English paper rewriter
paper-rewriter-zh   ← Chinese paper rewriter
AIGC-rewriter-zh    ← Chinese AIGC reducer
AIGC-rewriter       ← English AIGC reducer (placeholder)
```

## Quick Start

Switch to the skill branch you need:

```bash
git checkout paper-rewriter-zh
```

Each skill branch is self-contained with its own README, scripts, tests, and references.
