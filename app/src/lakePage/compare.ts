import type { Lake, LakesFile } from "../lakes";

/** Decodes a 1-bit mask PNG into one flag per pixel (Task 22). */
export type MaskDecoder = (url: string) => Promise<{ width: number; height: number; data: Uint8Array }>;

export interface CompareOptions {
  file: LakesFile;
  lake: Lake;
  pass: [string, string];
  decodeMask?: MaskDecoder;
  onRoute(hash: string): void;
}

/** The compare view (Task 22 fills it). */
export function renderCompare(root: HTMLElement, _opts: CompareOptions): void {
  const p = document.createElement("p");
  p.textContent = "Compare is not available yet.";
  root.replaceChildren(p);
}
