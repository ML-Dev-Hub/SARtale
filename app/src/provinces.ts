/** The one place province display names live. */
export const PROVINCE_NAMES: Record<"GB" | "KP", string> = { GB: "Gilgit-Baltistan", KP: "Khyber Pakhtunkhwa" };

/** The display name of a province code, or null for a missing or unknown one. */
export function provinceName(p: string | null | undefined): string | null {
  return p === "GB" || p === "KP" ? PROVINCE_NAMES[p] : null;
}
