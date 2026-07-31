export type Severity = "critical" | "warning";

export type FindingType =
  | "secret"
  | "pii"
  | "jargon"
  | "internal-url"
  | "internal-reference"
  | "other";

export type FindingSource = "trufflehog" | "secretlint" | "jargon" | "pii" | "reviewer";

export interface Finding {
  file: string;
  line: number;
  type: FindingType;
  severity: Severity;
  source: FindingSource;
  message: string;
  term?: string;
}

export interface ScanReport {
  findings: Finding[];
  scannedPaths: string[];
  durationMs: number;
}

export type SyncMode = "COPY" | "SYNC";

export interface SyncPlan {
  mode: SyncMode;
  // sourceAbs is the directory that Phase B copies INTO essentials. When extract
  // is enabled, it points at the path where Phase A will materialize the
  // extracted package -- that path will not exist on disk at plan time.
  sourceAbs: string;
  targetRepoAbs: string;
  targetPathRel: string;
  targetAbs: string;
  phaseAEnabled: boolean;
  extractedPkgAbs?: string;
  wrapperPkgAbs?: string;
  sourceRepoRoot?: string;
  originalToolName?: string;
  packageName?: string;
  importableName?: string;
}

export type ModelSpec =
  | { kind: "id"; id: string }
  | { kind: "family"; family: string }
  | { kind: "auto" };

export interface ResolvedModels {
  primary: string;
  review: string;
  primarySource: "explicit" | "sentinel" | "fallback";
  reviewSource: "explicit" | "sentinel" | "fallback";
  available: string[];
  collapsed: boolean;
}

export interface CliOptions {
  source: string;
  targetRepo: string;
  targetPath?: string;
  sourceRepo?: string;
  packageName?: string;
  model: string;
  reviewModel: string;
  maxRevisions: number;
  dryRun: boolean;
  noSourceScan: boolean;
  noAdversarialReview: boolean;
  noExtract: boolean;
  noFastCopy: boolean;
}
