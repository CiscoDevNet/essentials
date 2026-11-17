import { styleText } from "node:util";

type Format = Parameters<typeof styleText>[0];

// styleText drops the escape codes when stdout is not a terminal or NO_COLOR
// is set.
function paint(format: Format): (text: string) => string {
  return (text) => styleText(format, text);
}

export const style = {
  red: paint("red"),
  green: paint("green"),
  yellow: paint("yellow"),
  cyan: paint("cyan"),
  dim: paint("dim"),
};
