import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { cacheDirectory } from "./program.ts";
import { style } from "./style.ts";

export type CursorSdk = typeof import("@cursor/sdk");

const SDK_PACKAGE = "@cursor/sdk";
const MANIFEST_DIRECTORY = fileURLToPath(new URL("../sdk/", import.meta.url));
const MANIFEST_FILES = ["package.json", "package-lock.json"];

let loading: Promise<CursorSdk> | undefined;

// Installs the pinned SDK into the user cache on first use, then imports it.
// Nothing is ever installed next to the skill: package managers copy a skill
// directory verbatim, generated files included.
export function loadCursorSdk(): Promise<CursorSdk> {
  loading ??= installAndImport();
  return loading;
}

// One directory per manifest, so bumping the pinned version (or the install
// scripts it allows) installs fresh and never mixes with an older install.
export async function sdkInstallDirectory(): Promise<string> {
  const hash = createHash("sha256");
  for (const name of MANIFEST_FILES) {
    hash.update(await fs.readFile(path.join(MANIFEST_DIRECTORY, name)));
  }
  return path.join(cacheDirectory(), `sdk-${hash.digest("hex").slice(0, 16)}`);
}

export async function isSdkInstalled(): Promise<boolean> {
  return exists(installedManifest(await sdkInstallDirectory()));
}

async function installAndImport(): Promise<CursorSdk> {
  const installDir = await ensureInstalled();
  const packageDir = path.join(installDir, "node_modules", SDK_PACKAGE);
  const entry = await resolveImportEntry(packageDir);
  return (await import(pathToFileURL(entry).href)) as CursorSdk;
}

async function ensureInstalled(): Promise<string> {
  const installDir = await sdkInstallDirectory();
  if (await exists(installedManifest(installDir))) return installDir;

  await fs.mkdir(path.dirname(installDir), { recursive: true });
  // Install beside the final directory and rename into place, so an
  // interrupted install never looks complete.
  const staging = await fs.mkdtemp(`${installDir}.tmp-`);
  try {
    for (const name of MANIFEST_FILES) {
      await fs.copyFile(path.join(MANIFEST_DIRECTORY, name), path.join(staging, name));
    }
    console.error(style.dim(`[sdk] installing ${SDK_PACKAGE} into ${installDir} (first run only)`));
    const exitCode = await npmCi(staging);
    if (exitCode !== 0) {
      throw new Error(
        `npm ci exited ${exitCode} while installing ${SDK_PACKAGE} into the cache. `
          + "See references/install.md in the skill for known install failures.",
      );
    }
    try {
      await fs.rename(staging, installDir);
    } catch (error) {
      // A concurrent run finished first; its install is just as good.
      if (!(await exists(installedManifest(installDir)))) throw error;
    }
  } finally {
    await fs.rm(staging, { recursive: true, force: true });
  }
  return installDir;
}

function npmCi(cwd: string): Promise<number> {
  return new Promise((resolve, reject) => {
    // npm's progress goes to stderr so stdout stays clean for the CLI.
    const child = spawn("npm", ["ci", "--omit=dev", "--no-audit", "--no-fund"], {
      cwd,
      stdio: ["ignore", 2, 2],
      shell: process.platform === "win32",
    });
    child.on("error", reject);
    child.on("close", (code) => resolve(code ?? 1));
  });
}

async function resolveImportEntry(packageDir: string): Promise<string> {
  const manifest = JSON.parse(await fs.readFile(path.join(packageDir, "package.json"), "utf8")) as {
    exports?: unknown;
    module?: string;
    main?: string;
  };
  const rootExport = isRecord(manifest.exports) && "." in manifest.exports
    ? manifest.exports["."]
    : manifest.exports;
  const relative = pickImportTarget(rootExport) ?? manifest.module ?? manifest.main ?? "index.js";
  return path.join(packageDir, relative);
}

function pickImportTarget(target: unknown): string | undefined {
  if (typeof target === "string") return target;
  if (!isRecord(target)) return undefined;
  return pickImportTarget(target.import) ?? pickImportTarget(target.default);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function installedManifest(installDir: string): string {
  return path.join(installDir, "node_modules", SDK_PACKAGE, "package.json");
}

async function exists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}
