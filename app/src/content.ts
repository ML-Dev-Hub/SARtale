import storyJson from "./content/story.json";
import sitesJson from "./content/sites.json";

/** Wording the app must never use. Matched as whole words, case-insensitively, so "damage" and "damaged" are separate entries. */
export const BANNED_CLAIMS = [
  "detected flood",
  "flood detected",
  "damage",
  "damaged",
  "isolated",
  "risk score",
  "early warning",
] as const;

const BANNED_PATTERNS = BANNED_CLAIMS.map((phrase) => ({
  phrase,
  re: new RegExp(String.raw`\b${phrase.replace(/ /g, String.raw`\s+`)}\b`, "i"),
}));

/** The banned phrases found in the text, lowercase, once each, in the order of BANNED_CLAIMS. */
export function findBannedClaims(text: string): string[] {
  return BANNED_PATTERNS.filter(({ re }) => re.test(text)).map(({ phrase }) => phrase);
}

/** The four real evidence classes. */
export type EvidenceClass = "observed" | "reference-agrees" | "hypothesis" | "not-observed";
/** A card that has no written copy yet shows a neutral "Placeholder" badge instead of an evidence class. */
export type Evidence = EvidenceClass | "placeholder";

export const EVIDENCE_LABELS: Record<EvidenceClass, string> = {
  observed: "Observed",
  "reference-agrees": "Reference agrees",
  hypothesis: "Hypothesis",
  "not-observed": "Not observed",
};

/** Badge text for every value a card can carry. */
export const BADGE_LABELS: Record<Evidence, string> = { ...EVIDENCE_LABELS, placeholder: "Placeholder" };

/** Marks copy that has not been written from real curves yet. */
export const PLACEHOLDER = "Placeholder text: replace after real curves are reviewed.";

/** Marks event copy that waits for the event-timing check against PDMA reports and FFD bulletins. */
export const EVENT_PLACEHOLDER = "Placeholder text: replace after event timing is checked.";

export interface SiteCard {
  /** ISO dates the card is about. Empty until the copy is written. */
  dates: string[];
  observation: string;
  /** One hypothesis, worded with "may indicate". */
  hypothesis: string;
  /** What observation would test the hypothesis. */
  test: string;
  limits: string;
  evidence: Evidence;
}

export interface SiteStory {
  title: string;
  summary: string;
}

export const story = storyJson as Record<string, SiteStory>;
export const siteCards = sitesJson as Record<string, SiteCard>;

/** The card for a site, or a placeholder card if no copy has been written for it. */
export function cardFor(siteId: string): SiteCard {
  return (
    siteCards[siteId] ?? {
      dates: [],
      observation: PLACEHOLDER,
      hypothesis: PLACEHOLDER,
      test: PLACEHOLDER,
      limits: PLACEHOLDER,
      evidence: "placeholder",
    }
  );
}
