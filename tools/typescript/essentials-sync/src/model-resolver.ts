import { Cursor } from "@cursor/sdk";
import type { ModelSpec, ResolvedModels } from "./types.js";

const KNOWN_FAMILIES = ["opus", "codex", "claude", "gpt", "gemini", "composer"] as const;

const PRIMARY_FALLBACKS: readonly string[] = ["opus", "claude", "auto"];
const REVIEW_FALLBACKS: readonly string[] = ["codex", "gpt", "auto"];

export function parseModelSpec(value: string): ModelSpec {
  const normalized = value.trim().toLowerCase();
  if (normalized === "auto" || normalized === "") {
    return { kind: "auto" };
  }
  if (KNOWN_FAMILIES.includes(normalized as (typeof KNOWN_FAMILIES)[number])) {
    return { kind: "family", family: normalized };
  }
  return { kind: "id", id: value.trim() };
}

function pickHighestInFamily(family: string, catalog: string[]): string | null {
  const candidates = catalog
    .map((id) => {
      const lower = id.toLowerCase();
      const familyIdx = lower.indexOf(family);
      if (familyIdx < 0) return null;
      const before = familyIdx === 0 ? "" : lower[familyIdx - 1];
      const hasCleanBoundary = familyIdx === 0 || before === "-";
      if (!hasCleanBoundary) return null;
      const after = lower.slice(familyIdx + family.length);
      const suffixSegments = after.split("-").filter((seg) => seg.length > 0).length;
      return { id, lower, suffixSegments };
    })
    .filter(
      (entry): entry is { id: string; lower: string; suffixSegments: number } => entry !== null,
    );

  if (candidates.length === 0) return null;

  // For family sentinels we prefer the canonical version (no extra suffix
  // segments past the version tokens). For codex this picks `gpt-5.3-codex`
  // over `gpt-5.3-codex-spark`. We pick the minimum suffix-segment count
  // observed and only sort within that tier.
  const minSuffix = Math.min(...candidates.map((entry) => entry.suffixSegments));
  const topTier = candidates.filter((entry) => entry.suffixSegments === minSuffix);
  topTier.sort((left, right) => right.lower.localeCompare(left.lower));
  return topTier[0]?.id ?? null;
}

interface ResolveSingleInputs {
  spec: ModelSpec;
  catalog: string[];
  fallbacks: readonly string[];
  excludeId?: string;
}

function resolveWithFallbacks({
  spec,
  catalog,
  fallbacks,
  excludeId,
}: ResolveSingleInputs): { id: string; source: "explicit" | "sentinel" | "fallback" } {
  if (spec.kind === "id") {
    return { id: spec.id, source: "explicit" };
  }
  if (spec.kind === "auto") {
    return { id: "auto", source: "explicit" };
  }

  const requested = spec.family;
  const primaryAttempt = pickHighestInFamily(requested, catalog);
  if (primaryAttempt && primaryAttempt !== excludeId) {
    return { id: primaryAttempt, source: "sentinel" };
  }

  for (const candidate of fallbacks) {
    if (candidate === requested) continue;
    if (candidate === "auto") {
      return { id: "auto", source: "fallback" };
    }
    const picked = pickHighestInFamily(candidate, catalog);
    if (picked && picked !== excludeId) {
      return { id: picked, source: "fallback" };
    }
  }
  return { id: "auto", source: "fallback" };
}

export interface ResolveInputs {
  apiKey: string;
  primarySpec: ModelSpec;
  reviewSpec: ModelSpec;
}

export async function resolveModels({
  apiKey,
  primarySpec,
  reviewSpec,
}: ResolveInputs): Promise<ResolvedModels> {
  const catalog = await fetchCatalog(apiKey);

  const primaryResolved = resolveWithFallbacks({
    spec: primarySpec,
    catalog,
    fallbacks: PRIMARY_FALLBACKS,
  });

  const reviewResolved = resolveWithFallbacks({
    spec: reviewSpec,
    catalog,
    fallbacks: REVIEW_FALLBACKS,
    excludeId: primaryResolved.id,
  });

  return {
    primary: primaryResolved.id,
    review: reviewResolved.id,
    primarySource: primaryResolved.source,
    reviewSource: reviewResolved.source,
    available: catalog,
    collapsed: primaryResolved.id === reviewResolved.id,
  };
}

async function fetchCatalog(apiKey: string): Promise<string[]> {
  const response = (await Cursor.models.list({ apiKey })) as unknown;
  return normalizeCatalog(response);
}

function normalizeCatalog(response: unknown): string[] {
  if (Array.isArray(response)) {
    return response.map(extractId).filter((id): id is string => Boolean(id));
  }
  if (response && typeof response === "object") {
    const maybeArray =
      (response as { models?: unknown; data?: unknown }).models
      ?? (response as { data?: unknown }).data;
    if (Array.isArray(maybeArray)) {
      return maybeArray.map(extractId).filter((id): id is string => Boolean(id));
    }
  }
  return [];
}

function extractId(item: unknown): string | null {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    const id = (item as { id?: unknown }).id;
    if (typeof id === "string") return id;
    const name = (item as { name?: unknown }).name;
    if (typeof name === "string") return name;
  }
  return null;
}

export async function listAvailableModels(apiKey: string): Promise<string[]> {
  return fetchCatalog(apiKey);
}
