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
  "detected change",
  "detected changes",
  "change detected",
  "changes detected",
  "change detection",
  "breach warning",
  "predict",
  "safe",
  "no risk",
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

export interface SiteCard {
  /** ISO dates the card is about. Empty until the copy is written. */
  dates: string[];
  observation: string;
  /** One hypothesis, worded with "may indicate". */
  hypothesis: string;
  /** What observation would test the hypothesis. */
  test: string;
  limits: string;
  /** How to read this site's change scores, where they could mislead. */
  changeNote?: string;
  /**
   * What the map's own test says around the site, from DATA_SOURCES.md: the share of 90 m map pixels flagged within
   * 450 m, and how many pixels that is. Absent where the map flags nothing near the site.
   */
  mapCheck?: { radius_m: number; flagged_pct: number; pixels: number };
  evidence: Evidence;
  /** The curve values the observation quotes. A test checks each against sites.json, so copy cannot drift from a rebuild. */
  quotes?: { date: string; pol: "HH" | "HV"; db: string }[];
}

export interface SiteStory {
  title: string;
  summary: string;
}

/** One quoted curve value in the hero or a story step. A test checks each against sites.json. */
export interface StoryQuote {
  site: string;
  date: string;
  pol: "HH" | "HV";
  db: string;
}

/** What the map shows at a story step. Dates are ISO dates of built frames. */
export interface StoryMapState {
  date: string;
  pol: "HH" | "HV";
  /** Show the step map (the main Change view). */
  change?: boolean;
  /** Show before and after, with this date on the left. */
  swipeBefore?: string;
}

export interface StoryStep {
  id: string;
  /** The beat, 1 to 6. Several steps may share one beat. */
  beat: number;
  /** The beat's name. */
  label: string;
  /** A short name for the step inside a beat that has several. */
  stop?: string;
  title: string;
  body: string[];
  source?: string;
  /** Background that explains the setting. It is general knowledge or context, not a finding. */
  background?: boolean;
  /** A site whose card the step can open. */
  site?: string;
  /** Show the observation timeline inside the step. */
  strip?: boolean;
  /** Dated marks on that timeline, for events that are not passes. */
  marks?: { date: string; label: string }[];
  /** "play" adds a button that plays the season. */
  action?: "play";
  camera: { fit: true } | { center: [number, number]; zoom: number };
  map: StoryMapState;
  quotes?: StoryQuote[];
}

export interface HeroCopy {
  title: string;
  lede: string;
  /** One finding, in words that keep it a hypothesis. */
  finding: string;
  findingSource: string;
  quotes: StoryQuote[];
}

const { beats, hero, ...siteStories } = storyJson as unknown as {
  beats: StoryStep[];
  hero: HeroCopy;
} & Record<string, SiteStory>;

/** The six-beat guided story, in order. Every step moves the map. */
export const storyBeats: StoryStep[] = beats;
export const heroCopy: HeroCopy = hero;
/** Copy for single views, by id. */
export const story: Record<string, SiteStory> = siteStories;
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
