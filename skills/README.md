# Reusable Hermes skills

This directory contains profile-independent Hermes skills that can be shared
without a user's memory, preferences, credentials, infrastructure, or private
data.

Included skills:

- planning and concierge: `appointments`, `event-planner`,
  `travel-concierge`, `shopping`, `home-concierge`;
- communication and organization: `communication`, `document-manager`,
  `personal-admin`, `project-manager`, `weekly-review`;
- reasoning: `date-time-reasoning`, `decision-support`, `research-compare`;
- utilities: `cronjob-management`, `expense-tracker`;
- integration guidance: `productivity/vkusvill`.

The public skills already bundled with Hermes are not duplicated here. They
remain available through the pinned `hermes/hermes-agent` submodule.

## Install

For the default Hermes profile:

```bash
mkdir -p ~/.hermes/skills
cp -R skills/. ~/.hermes/skills/
```

For a named profile, replace the destination with
`~/.hermes/profiles/<profile>/skills/`. Reload skills or restart Hermes after
copying them.

Do not add profile memories, personal preferences, credentials, server
addresses, or absolute user paths to this directory.
