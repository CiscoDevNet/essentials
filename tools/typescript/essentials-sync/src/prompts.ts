import type { Finding, ScanReport, SyncPlan } from "./types.js";

// === Sync system prompt (Phase B: write into the open-source target repo) ===
export const SYNC_SYSTEM_PROMPT = `You are the essentials-sync primary agent. Your job is to move a package from a private, company-owned repository into the public open-source essentials repository, generalizing all company-specific content along the way.

HARD RULES that must hold for every file you write into the target:
1. No secrets of any kind (API keys, tokens, passwords, certificates, private keys).
2. No personally identifiable information (employee names, employee IDs, emails, phone numbers).
3. No internal hostnames or URLs (anything under company-owned domains like cisco.com, webex.com, or other internal infra).
4. No company-specific identifiers or jargon left verbatim. Examples: 'cisco', 'webex', 'myid', 'cec', internal product codenames, internal org names. These must be either removed or generalized.

NAMING CONVENTION:
- When you create or rename a package destined for the essentials repo, the package name must begin with the prefix 'ess-'. For example, an internal package 'cisco-auth' should become 'ess-auth'.
- The target layout is 'packages/python/ess-*' for Python and 'packages/javascript/ess-*' for JavaScript/TypeScript.

STRUCTURE PRESERVATION:
- Preserve pyproject.toml and package.json structure. Update only the fields that carry company-specific data (name, authors, urls, keywords, descriptions).
- Preserve or add an Apache 2.0 license header to newly created source files. Do not strip pre-existing license headers unless they reference the company name verbatim.
- Preserve directory structure unless the source layout violates the essentials convention; if it does, reorganize and note the changes.

When you are uncertain whether a term is internal or generic, treat it as internal and generalize it.
`;

// === Extract system prompt (Phase A: refactor in place inside honeycomb) ===
export const EXTRACT_SYSTEM_PROMPT = `You are the essentials-sync primary agent operating in EXTRACT mode. Your job is to refactor a team- or account-specific tool inside the private honeycomb repository into two sibling packages:

1. A jargon-free shared library at 'packages/python/ess-<name>/' containing all the reusable logic, parameterized so it has NO hard-coded company-specific defaults.
2. A thin wrapper at 'tools/python/<name>/' (the original tool's location, rewritten in place) that imports the shared library and supplies the company-specific defaults.

REFERENCE PATTERN: this matches the langsmith-hosting / sales-ai-langsmith-hosting split that already exists in honeycomb. Concretely:
- 'packages/python/langsmith-hosting/' is a generic, reusable library with its own CLI, tests, and parameterized configuration.
- 'tools/python/sales-ai-langsmith-hosting/__main__.py' is two non-blank lines that import 'deploy_stack' from the library and call it with the team-specific 'aws_profile'.
- The wrapper depends on the library via '[tool.uv.sources] langsmith-hosting = { workspace = true }'.
Replicate that shape.

HARD RULES for the EXTRACTED package (the new 'packages/python/ess-<name>/'):
1. No secrets, no PII.
2. No internal hostnames, URLs, or account IDs.
3. No company-specific identifiers or jargon left verbatim ('cisco', 'webex', 'myid', 'cec', internal product codenames, internal org names).
4. No company-specific defaults baked into function signatures, CLI flags, or constants. Defaults that used to be hard-coded must become required parameters, env-var-driven, or removed entirely.
5. Every file written under 'packages/python/ess-<name>/' will be scanned. Any leftover company data here is a failure.

PERMISSIONS for the WRAPPER (the rewritten 'tools/python/<name>/'):
- The wrapper is allowed -- expected, even -- to contain the company-specific values that used to live in the source tool. Hostnames, default account names, internal SSO domains, team-specific AWS profiles, etc. belong here.
- Keep it minimal: import from the shared library, supply the defaults, expose the same CLI entry point name so existing callers do not break.
- The wrapper will NOT be scanned.

NAMING:
- The extracted package name is given to you in the user prompt; it always starts with 'ess-'.
- The importable module name is the package name with hyphens replaced by underscores (e.g. 'ess-service-now-incident' -> 'ess_service_now_incident').

When you are uncertain whether a term is internal or generic, treat it as internal and generalize it.
`;

export interface PhaseAInputs {
  plan: SyncPlan;
  sourceScan: ScanReport | null;
  jargonHeavy: boolean;
}

// Sync-phase initial prompt (was buildPhaseAPrompt).
export function buildSyncInitialPrompt({
  plan,
  sourceScan,
  jargonHeavy,
}: PhaseAInputs): string {
  const mode = plan.mode;
  const sourceScanSection = sourceScan
    ? formatSourceScanSummary(sourceScan)
    : "No source pre-scan was performed (--no-source-scan).";

  const generalizationNote = jargonHeavy
    ? `The source contains substantial company-specific jargon. Also write a file named RECOMMENDATIONS.md inside the target directory that:
  - proposes a new ess-* package name and rationale
  - lists identifiers and strings that were renamed
  - calls out any modules or behaviors that could not be cleanly generalized and should be left behind in the private repo`
    : "Source pre-scan looks light on company jargon; no RECOMMENDATIONS.md needed unless you find more during the rewrite.";

  return `MODE: ${mode}
SOURCE (read-only, absolute path): ${plan.sourceAbs}
TARGET REPO (your cwd): ${plan.targetRepoAbs}
TARGET PATH (relative to target repo): ${plan.targetPathRel}
TARGET ABSOLUTE PATH: ${plan.targetAbs}

TASK:
1. Read every file in the SOURCE directory. You have full read access to it.
2. Write the generalized equivalent into TARGET ABSOLUTE PATH.
   - In COPY mode, the target path does not exist yet. Create it.
   - In SYNC mode, the target path already exists; reconcile by updating files that have meaningfully diverged. Do not blindly overwrite the target.
3. Apply the HARD RULES from your system prompt to every file you write. The target tree will be scanned after you finish; any leftover company data is a failure.
4. ${generalizationNote}

SOURCE SCAN SUMMARY (informational only, never a blocker on the source side):
${sourceScanSection}

When you are done, return a short summary of what you wrote, the chosen ess-* name if applicable, and any caveats.
`;
}

export interface PhaseBInputs {
  plan: SyncPlan;
  iteration: number;
  maxRevisions: number;
  combinedFindings: Finding[];
}

// Sync-phase revision prompt (was buildPhaseBPrompt).
export function buildSyncRevisionPrompt({
  plan,
  iteration,
  maxRevisions,
  combinedFindings,
}: PhaseBInputs): string {
  const formatted = formatFindingsForPrompt(combinedFindings);

  return `REVISION REQUIRED (iteration ${iteration} of ${maxRevisions}).

The target tree at ${plan.targetAbs} was scanned by deterministic scanners and an adversarial reviewer (running on a different model from yours). The following findings must be resolved before this package can ship:

${formatted}

For each finding:
  - Open the offending file in the target.
  - Apply the minimal change that removes the company-specific content while preserving behavior.
  - Do NOT introduce new files unless strictly necessary.
  - Do NOT touch files that have no findings.

The HARD RULES from your system prompt still apply. Once you have addressed every finding, return a short summary of which files you changed.
`;
}

export interface ExtractInitialInputs {
  plan: SyncPlan;
  sourceScan: ScanReport | null;
}

export function buildExtractInitialPrompt({
  plan,
  sourceScan,
}: ExtractInitialInputs): string {
  if (
    !plan.extractedPkgAbs
    || !plan.wrapperPkgAbs
    || !plan.sourceRepoRoot
    || !plan.packageName
    || !plan.importableName
  ) {
    throw new Error(
      "buildExtractInitialPrompt called on a plan that is missing extract metadata.",
    );
  }
  const sourceScanSection = sourceScan
    ? formatSourceScanSummary(sourceScan)
    : "No source pre-scan was performed (--no-source-scan).";

  return `MODE: EXTRACT
SOURCE REPO ROOT (your cwd): ${plan.sourceRepoRoot}
ORIGINAL TOOL (read for behavior, then rewrite in place as a wrapper): ${plan.wrapperPkgAbs}
EXTRACTED PACKAGE PATH (create here, jargon-free): ${plan.extractedPkgAbs}
PACKAGE NAME: ${plan.packageName}
IMPORTABLE MODULE: ${plan.importableName}

TASK:
1. Read every file under ORIGINAL TOOL to understand its current behavior.
2. Create the EXTRACTED PACKAGE at the path above. It must include:
   - Its own pyproject.toml with name '${plan.packageName}', a short generic description, hatchling build backend, and the right [tool.hatch.build.targets.wheel] packages entry pointing at 'src/${plan.importableName}'.
   - A 'src/${plan.importableName}/' directory with the generalized core logic. All company-specific defaults must become required parameters, env-var-driven overrides, or be removed.
   - Tests under 'tests/' that pass without any honeycomb-specific setup.
   - A README.md focused on the generic library (what it does, how to use it, no company references).
3. Rewrite ORIGINAL TOOL in place as a thin wrapper:
   - Its pyproject.toml should declare a dependency on '${plan.packageName}' via '[tool.uv.sources] ${plan.packageName} = { workspace = true }'.
   - Its source code becomes a small wrapper module that imports from '${plan.importableName}' and supplies the company-specific defaults. Follow the 'sales-ai-langsmith-hosting' shape.
   - Keep the same CLI entry point name (so existing callers do not break).
   - The wrapper is allowed to contain company-specific defaults (hostnames, AWS profiles, internal SSO domains, etc.). That is its purpose.
4. Update the root pyproject.toml at ${plan.sourceRepoRoot}/pyproject.toml to add '${plan.packageName}' to '[tool.uv.workspace] members' if it is not already listed. Do not modify any other workspace entries.
5. Do NOT delete anything outside ORIGINAL TOOL and EXTRACTED PACKAGE PATH. Do NOT modify other tools or packages.

SCAN COVERAGE: Only the EXTRACTED PACKAGE will be scanned. The wrapper is excluded from the scan, so company-specific defaults belong there.

SOURCE SCAN SUMMARY (informational only):
${sourceScanSection}

When you are done, return a short summary of: the extracted package layout, the wrapper before/after, and any behavior changes worth flagging to reviewers.
`;
}

export interface ExtractRevisionInputs {
  plan: SyncPlan;
  iteration: number;
  maxRevisions: number;
  combinedFindings: Finding[];
}

export function buildExtractRevisionPrompt({
  plan,
  iteration,
  maxRevisions,
  combinedFindings,
}: ExtractRevisionInputs): string {
  if (!plan.extractedPkgAbs) {
    throw new Error(
      "buildExtractRevisionPrompt called on a plan that is missing extractedPkgAbs.",
    );
  }
  const formatted = formatFindingsForPrompt(combinedFindings);

  return `REVISION REQUIRED for the EXTRACTED package (iteration ${iteration} of ${maxRevisions}).

The extracted package at ${plan.extractedPkgAbs} was scanned by deterministic scanners and an adversarial reviewer. The findings below must be resolved before Phase B (sync to essentials) can run:

${formatted}

For each finding:
  - Open the offending file inside the extracted package.
  - Apply the minimal change that removes the company-specific content while preserving behavior.
  - If a default needs to live somewhere, move it into the wrapper at ${plan.wrapperPkgAbs ?? "the original tool location"} instead of keeping it in the extracted package.
  - Do NOT modify files outside the extracted package and the wrapper.

The HARD RULES from your system prompt still apply. Once you have addressed every finding, return a short summary of which files you changed.
`;
}

export interface ReviewerPromptInputs {
  plan: SyncPlan;
  // The path the reviewer should treat as the package to inspect. Defaults to
  // plan.targetAbs but during Phase A we point it at the extracted package.
  reviewRootAbs?: string;
}

export function buildReviewerPrompt({
  plan,
  reviewRootAbs,
}: ReviewerPromptInputs): string {
  const root = reviewRootAbs ?? plan.targetAbs;
  return `You are a strict open-source release reviewer. The package at ${root} is about to be published to a public, open-source repository.

Read every file under that path. Flag anything that would embarrass the team or leak company information if released. Be paranoid. Pay particular attention to:
  - Internal hostnames, URLs, account IDs, project codenames.
  - Personally identifiable information (employee names, IDs, emails, phone numbers).
  - Subtle references in docstrings, comments, naming, error messages, or example data that imply an internal audience.
  - Implied workflows or assumptions that only make sense inside the company.
  - Anything that looks like a secret (API key, token, password, certificate).

DO NOT flag the following -- they are public, open-source conventions, not internal jargon:
  - Package names that start with the 'ess-' prefix (e.g. 'ess-browser', 'ess-auth', 'ess-service-now-incident'). 'ess' is short for 'essentials', the public open-source repo this package belongs to. References to other 'ess-*' packages as dependencies, workspace siblings, or import targets ('from ess_browser import ...', '[tool.uv.sources] ess-browser = { workspace = true }') are expected and correct.
  - Generic uv/Python workspace conventions ('[tool.uv.workspace]', 'uv sync --all-packages', the 'packages/python/' and 'tools/python/' directory layout). These are upstream uv patterns, not company-specific.

Output ONLY a single JSON object, with no surrounding prose, no markdown code fences, and no commentary. Schema:

{
  "findings": [
    {
      "file": "<absolute or repo-relative path>",
      "line": <integer line number, 1-indexed>,
      "type": "secret" | "pii" | "jargon" | "internal-url" | "internal-reference" | "other",
      "severity": "critical" | "warning",
      "message": "<short human-readable explanation of why this is flagged>"
    }
  ]
}

If the package is clean, return exactly:
{ "findings": [] }
`;
}

function formatFindingsForPrompt(findings: Finding[]): string {
  return findings
    .map(
      (finding) =>
        `- [${finding.severity}] ${finding.source}: ${finding.file}:${finding.line} - ${finding.message}`
          + (finding.term ? ` (term=${finding.term})` : ""),
    )
    .join("\n");
}

function formatSourceScanSummary(report: ScanReport): string {
  if (report.findings.length === 0) {
    return "Source scan: no findings.";
  }
  const counts: Record<string, number> = {};
  for (const finding of report.findings) {
    const key = `${finding.source}/${finding.type}`;
    counts[key] = (counts[key] ?? 0) + 1;
  }
  const summary = Object.entries(counts)
    .map(([key, count]) => `  ${key}: ${count}`)
    .join("\n");
  const examples = report.findings
    .slice(0, 8)
    .map(
      (finding) =>
        `  - ${finding.source}: ${finding.file}:${finding.line} (${finding.term ?? finding.type})`,
    )
    .join("\n");
  return `Source scan totals:\n${summary}\n\nFirst few:\n${examples}`;
}

// Backwards-compat aliases for any external import sites that still reference
// the old names. Safe to remove once nothing imports them.
export const PRIMARY_SYSTEM_PROMPT = SYNC_SYSTEM_PROMPT;
export const buildPhaseAPrompt = buildSyncInitialPrompt;
export const buildPhaseBPrompt = buildSyncRevisionPrompt;
