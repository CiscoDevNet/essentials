import { promises as fs } from "node:fs";
import path from "node:path";
import { globby } from "globby";
import { HARD_SKIP_DIRECTORIES, isUnscannableTextFile } from "./scanners/text-files.js";

export interface CopyTreeResult {
  filesCopied: string[];
  // Copied files the text scanners never read (binary extension or over the
  // size cap). They are still copied so the package stays complete, but the
  // caller surfaces them so a human knows what went out unscanned.
  unscannedFiles: string[];
  symlinksSkipped: string[];
}

// Copies sourceAbs into targetAbs without deleting anything already in the
// target, so target-only files (LICENSE, NOTICE) survive a re-sync.
//
// Traversal deliberately mirrors the scanners: .gitignore is honored and the
// same cache/build directories are skipped. That invariant is what makes the
// fast path safe -- every file this copies is a file the scanners inspected, so
// a clean scan really does cover the whole payload. Copying gitignored files
// would break it, since those are exactly the paths (.env, local credentials)
// the scanners never see.
export async function copyTreeVerbatim(
  sourceAbs: string,
  targetAbs: string,
): Promise<CopyTreeResult> {
  // onlyFiles is off so symlinks come back as entries we can classify and
  // report; with it on, globby drops them silently and the copy would be
  // quietly incomplete.
  const relPaths = await globby("**/*", {
    cwd: sourceAbs,
    dot: true,
    gitignore: true,
    onlyFiles: false,
    followSymbolicLinks: false,
    ignore: HARD_SKIP_DIRECTORIES.map((dir) => `**/${dir}/**`),
  });
  relPaths.sort();

  const filesCopied: string[] = [];
  const unscannedFiles: string[] = [];
  const symlinksSkipped: string[] = [];

  for (const relPath of relPaths) {
    const from = path.join(sourceAbs, relPath);
    const to = path.join(targetAbs, relPath);

    const stat = await fs.lstat(from);
    if (stat.isSymbolicLink()) {
      symlinksSkipped.push(relPath);
      continue;
    }
    if (stat.isDirectory()) {
      continue;
    }
    if (!stat.isFile()) {
      continue;
    }

    await fs.mkdir(path.dirname(to), { recursive: true });
    // copyFile carries the source mode across, which keeps the executable bit
    // on shipped scripts.
    await fs.copyFile(from, to);
    filesCopied.push(relPath);

    if (await isUnscannableTextFile(from)) {
      unscannedFiles.push(relPath);
    }
  }

  return { filesCopied, unscannedFiles, symlinksSkipped };
}
