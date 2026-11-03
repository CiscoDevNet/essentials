---
description: In .npmrc, reference environment variables as ${VAR}. A trailing ? is not portable.
applyTo: "**/.npmrc,**/.npmrc.*,**/npmrc"
---

# npmrc environment variables

npm replaces `${VARIABLE_NAME}` in `.npmrc` values. The text inside the braces is the environment variable name, exactly.

```ini
//registry.example.com/:_authToken=${NPM_TOKEN}
```

Do not append `?`.

npm 10, bundled with Node 20 and Node 22, has no optional form. It looks up a variable named `NPM_TOKEN?`, so exporting `NPM_TOKEN` leaves `${NPM_TOKEN?}` unexpanded and authenticated installs fail.

```ini
//registry.example.com/:_authToken=${NPM_TOKEN?}
```

npm 11 and later document `?` as "substitute an empty string when unset." That is still the wrong form for a required value such as an auth token: an unset variable becomes an empty token instead of a visible unreplaced placeholder. Write `${VARIABLE_NAME}` so the same file works on npm 10 and later.

Keep the `${...}` reference. Never paste a token into a committed `.npmrc`. Export the variable before `npm ci`.
