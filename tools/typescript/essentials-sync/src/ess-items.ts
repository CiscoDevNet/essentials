import { execa } from "execa";

// The ess-* item that contains repoRelPath (a repo-relative, "/"-separated
// path). An item is either a directory named ess-* (packages/python/ess-auth)
// or a file named ess-* directly inside a directory named ess
// (instructions/ess/ess-okf-docs.instructions.md). Other files that merely
// start with ess- (src/ess-scan.ts) are not items. Returns null when
// nothing matches, or when a dot-directory comes first (.agents/skills/ess-*,
// .cursor/rules/ess-*): those are installed copies of an item.
export function findEssItemRoot(repoRelPath: string): string | null {
  const parts = repoRelPath.split("/");
  const lastIndex = parts.length - 1;
  for (let index = 0; index <= lastIndex; index += 1) {
    const part = parts[index] ?? "";
    if (part.startsWith(".")) return null;
    if (!part.startsWith("ess-")) continue;
    const isDirectory = index < lastIndex;
    if (isDirectory || parts[index - 1] === "ess") {
      return parts.slice(0, index + 1).join("/");
    }
  }
  return null;
}

// Root of the git work tree containing directory, or null outside one.
export async function findGitRoot(directory: string): Promise<string | null> {
  const result = await execa("git", ["rev-parse", "--show-toplevel"], {
    cwd: directory,
    reject: false,
  });
  return result.exitCode === 0 ? result.stdout.trim() : null;
}
