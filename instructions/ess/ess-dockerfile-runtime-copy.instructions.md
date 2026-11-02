---
description: Copy runtime image files as root-owned and not writable, so the process cannot modify its own code (SonarQube docker:S6504)
applyTo: "**/Dockerfile,**/Dockerfile.*,**/*.dockerfile"
---

# Runtime image copies stay root-owned

A container should not be able to rewrite its own application code. If the runtime user owns the files it runs, a compromised process can change them, which breaks least privilege and container immutability. SonarQube reports this as **docker:S6504**, on any `COPY` or `ADD` whose `--chown` user is not `root`.

In the final stage, copy application files as root and drop the write bit. The runtime user can read and traverse them and cannot modify them.

```dockerfile
# Bad — node owns the app and can rewrite it
COPY --from=build --chown=node:node /app/dist ./dist
USER node

# Good
COPY --from=build --chown=root:root --chmod=555 /app/dist ./dist
USER node
```

`--chmod=555` is read and execute for everyone, so directories stay traversable and files stay readable. The same flags apply whether the runtime user is `node`, `nextjs`, or any other non-root account.

## Rules

- On every runtime-stage `COPY` or `ADD` of application files, set `--chown=root:root --chmod=555`.
- Do not `--chown` to a non-root user or a uid other than `0`.
- A path the process must write (cache, uploads, temp) is a separate empty directory. Do not loosen the application copy to make that path writable.
- Build-stage copies that the builder then writes, such as `package.json` before `npm ci`, stay default root and omit `--chmod=555`. Still do not `--chown` them to a non-root user.
