import { createInterface } from "node:readline/promises";

export type ConfirmOutcome = "dry-run" | "confirmed" | "declined" | "needs-yes";

export interface ConfirmInputs {
  dryRun: boolean;
  yes: boolean;
  isInteractive: boolean;
  question: string;
  ask?: (question: string) => Promise<string>;
}

// The write gate. --dry-run wins over --yes and writes nothing, so it needs
// no consent; --yes is consent; otherwise ask, and without a terminal to ask
// on, refuse.
export async function confirmWrite({
  dryRun,
  yes,
  isInteractive,
  question,
  ask = askOnStderr,
}: ConfirmInputs): Promise<ConfirmOutcome> {
  if (dryRun) return "dry-run";
  if (yes) return "confirmed";
  if (!isInteractive) return "needs-yes";
  const answer = (await ask(`${question} [y/N] `)).trim().toLowerCase();
  return answer === "y" || answer === "yes" ? "confirmed" : "declined";
}

// Prompts on stderr so stdout can still be piped.
async function askOnStderr(question: string): Promise<string> {
  const readline = createInterface({ input: process.stdin, output: process.stderr });
  try {
    return await readline.question(question);
  } finally {
    readline.close();
  }
}
