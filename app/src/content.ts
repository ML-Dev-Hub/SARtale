import storyJson from "./content/story.json";

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

/** The lake story's actions: buttons that take the person on from a beat. */
export type LakeBeatAction = "lake-watch" | "lake" | "evidence";

/** One beat of the lake story. Text may hold {tokens}, filled from lakes.json when the story is shown. */
export interface LakeBeat {
  id: string;
  /** The beat, from 1. */
  beat: number;
  label: string;
  title: string;
  /** Used in place of the title when the beat's data is missing. */
  noDataTitle?: string;
  body: string[];
  quote?: { text: string; cite: string };
  /** Shown instead of the body when lakes.json is not in this build. */
  noData?: string[];
  actions?: LakeBeatAction[];
}

export interface LakeHeroCopy {
  audience: string;
  title: string;
  lede: string;
  screening: string;
  headlineSource: string;
}

const copy = storyJson as unknown as { lakeHero: LakeHeroCopy; lakeStory: { beats: LakeBeat[] } };

/** The start screen's words. */
export const lakeHero: LakeHeroCopy = copy.lakeHero;
/** The beats of the lake story, in order. */
export const lakeStoryBeats: LakeBeat[] = copy.lakeStory.beats;
