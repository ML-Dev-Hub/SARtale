import { findBannedClaims } from "./content";
import copyJson from "./content/storyPage.json";
import type { Lake } from "./lakes";

const form = copyJson.add.form;

export type RequestState = "searched" | "too_few_passes" | "check_failed" | "invalid" | "accepted" | "rejected";

export type LakeRequest = {
  issue: number;
  name: string;
  lat: number;
  lon: number;
  state: RequestState;
  passes: number | null;
  tracks: string[];
  first: string | null;
  last: string | null;
  reason: string | null;
  lake_id: string | null;
  created: string;
};

export type RequestFields = { name: string; lat: string; lon: string; source: string };

export const REPO = "saeedahmadicp/SARtale";
const BOUNDS = { latMin: 34.4, latMax: 37.6, lonMin: 70.8, lonMax: 76.6 };
const NEAR_KM = 1;
const STATES: RequestState[] = ["searched", "too_few_passes", "check_failed", "invalid", "accepted", "rejected"];
/** States that hold a place on the map: a new request near one of these is a duplicate, and the story page shows them. */
const LIVE: RequestState[] = ["searched", "too_few_passes", "check_failed", "accepted"];

/** True for requests shown as requested lakes (not invalid or rejected). */
export function isShown(r: LakeRequest): boolean {
  return LIVE.includes(r.state);
}

/** The new-issue URL with the form's fields pre-filled (GitHub fills issue-form fields from query parameters). */
export function issueUrl(f: RequestFields): string {
  const q = (k: string, v: string): string => `${k}=${encodeURIComponent(v)}`;
  return `https://github.com/${REPO}/issues/new?${[
    q("template", "add-lake.yml"),
    q("title", `Add a lake: ${f.name}`),
    q("name", f.name),
    q("lat", f.lat),
    q("lon", f.lon),
    q("source", f.source),
  ].join("&")}`;
}

function isRequest(x: unknown): x is LakeRequest {
  if (!x || typeof x !== "object") return false;
  const r = x as Record<string, unknown>;
  return (
    typeof r.issue === "number" &&
    typeof r.name === "string" &&
    typeof r.lat === "number" &&
    typeof r.lon === "number" &&
    STATES.includes(r.state as RequestState) &&
    Array.isArray(r.tracks)
  );
}

/** Reads requests.json; any failure or unexpected shape is an empty list. */
export async function loadRequests(url = "data/requests.json", fetchFn: typeof fetch = (...a) => fetch(...a)): Promise<LakeRequest[]> {
  try {
    const res = await fetchFn(url);
    if (!res.ok) return [];
    const json: unknown = await res.json();
    const list = json && typeof json === "object" ? (json as { requests?: unknown }).requests : null;
    return Array.isArray(list) ? list.filter(isRequest) : [];
  } catch {
    return [];
  }
}

function km(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(a));
}

/**
 * The coordinate forms the issue reader accepts (lake_issues.py _COORD): "36.2", "36.2°", "36.2°N", "74.0 °E".
 * ASCII digits and ASCII spaces only, as Python's re.ASCII \s.
 */
const COORD = /^([+-]?[0-9]+(?:\.[0-9]+)?)[ \t\n\v\f\r]*°?[ \t\n\v\f\r]*[NnEe]?$/;
const MAX_OPEN = 200;
const OPEN_STATES: RequestState[] = ["searched", "too_few_passes", "check_failed"];

function numberField(key: string, value: string): number | string {
  const m = COORD.exec(value.trim());
  const n = m ? Number(m[1]) : NaN;
  return Number.isFinite(n) ? n : `${key} must be a number.`;
}

function textError(key: string, value: string, low: number, high: number): string | null {
  const t = value.trim();
  if (/[\p{Cc}\p{Cf}]/u.test(t)) return `${key} must not contain control or invisible formatting characters.`;
  return [...t].length >= low && [...t].length <= high ? null : `${key} must be ${low}–${high} characters.`;
}

/** The refusal for a name that uses wording SARtale never uses (lake_requests.banned_name_message); null when fine. */
export function bannedNameError(name: string): string | null {
  const found = findBannedClaims(name.trim());
  return found.length ? `The name uses a phrase SARtale does not use ("${found[0]}"); please use the lake's usual name.` : null;
}

/** The first problem with a request, in the same order and words as the Python validate; null when it is fine. */
export function checkRequest(f: RequestFields, watched: Lake[], requests: LakeRequest[]): string | null {
  const lat = numberField("lat", f.lat);
  if (typeof lat === "string") return lat;
  const lon = numberField("lon", f.lon);
  if (typeof lon === "string") return lon;
  const b = BOUNDS;
  if (lat < b.latMin || lat > b.latMax || lon < b.lonMin || lon > b.lonMax)
    return `The point must be in Gilgit-Baltistan or upper KP: ${b.latMin}–${b.latMax} °N, ${b.lonMin}–${b.lonMax} °E.`;
  const bad = textError("name", f.name, 2, 80) ?? bannedNameError(f.name) ?? textError("source", f.source, 3, 200);
  if (bad) return bad;
  for (const l of watched) if (km(lat, lon, l.lat, l.lon) <= NEAR_KM) return `Already watched: ${l.name}.`;
  const near = requests.filter((r) => LIVE.includes(r.state) && km(lat, lon, r.lat, r.lon) <= NEAR_KM).map((r) => r.issue);
  if (near.length) return `Already requested: issue #${Math.min(...near)}.`;
  if (requests.filter((r) => OPEN_STATES.includes(r.state)).length >= MAX_OPEN) return "The request list is full; try again later.";
  return null;
}

const passes = (n: number): string => `${n} NISAR ${n === 1 ? "pass" : "passes"}`;

/** The status line of a request card. Requests never carry a lake status. */
export function requestLine(r: LakeRequest): string {
  switch (r.state) {
    case "searched":
      return `Searched: ${passes(r.passes ?? 0)}${r.tracks.length ? ` on tracks ${r.tracks.join(", ")}` : ""}`;
    case "too_few_passes":
      return `Searched: ${passes(r.passes ?? 0)}, fewer than 3`;
    case "check_failed":
      return r.reason ? `Search failed: ${r.reason}` : "Search failed";
    case "accepted":
      return "Accepted";
    case "rejected":
      return r.reason ? `Not added: ${r.reason}` : "Not added";
    case "invalid":
      return r.reason ? `Not valid: ${r.reason}` : "Not valid";
  }
}

function text<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string | undefined, t: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  e.textContent = t;
  return e;
}

export interface AddLakeDeps {
  watched: Lake[];
  requests: LakeRequest[];
  open?: (url: string) => void;
}

const ALL_REQUESTS_URL = `https://github.com/${REPO}/issues?q=label%3Alake-request`;

/** The form in section 06. A valid submit opens a pre-filled GitHub issue; the visitor presses Submit there. */
export function mountAddLake(root: HTMLElement, deps: AddLakeDeps): { destroy(): void } {
  const open = deps.open ?? ((url: string) => void window.open(url, "_blank", "noopener"));

  const inputs: Record<keyof RequestFields, HTMLInputElement> = {
    name: document.createElement("input"),
    lat: document.createElement("input"),
    lon: document.createElement("input"),
    source: document.createElement("input"),
  };
  const field = (label: string, key: keyof RequestFields, placeholder: string, decimal = false): HTMLLabelElement => {
    const input = inputs[key];
    input.type = "text";
    input.name = key;
    input.placeholder = placeholder;
    input.autocomplete = "off";
    if (decimal) input.inputMode = "decimal";
    const l = document.createElement("label");
    l.className = "sp-field";
    l.append(label, input);
    return l;
  };
  const error = text("p", "sp-add-error", "");
  error.setAttribute("role", "alert");
  const card = document.createElement("div");
  card.className = "sp-add-card";
  card.setAttribute("role", "status");
  card.hidden = true;
  const link = text("a", "sp-add-link", form.seeAll);
  link.href = ALL_REQUESTS_URL;
  link.target = "_blank";
  link.rel = "noopener";
  const line = document.createElement("div");
  line.className = "sp-add-card-line";
  const strong = text("strong", undefined, form.finishStrong);
  line.append(form.finishBefore, strong, form.finishAfter);
  const again = text("a", "sp-add-link", form.openAgain);
  again.target = "_blank";
  again.rel = "noopener";
  card.append(line, again, " ", link);
  const button = text("button", "sp-btn sp-btn-primary", form.submitLabel);
  button.type = "submit";
  const f = document.createElement("form");
  f.noValidate = true;
  const coords = document.createElement("div");
  coords.className = "sp-field-pair";
  coords.append(field(form.latLabel, "lat", form.latPlaceholder, true), field(form.lonLabel, "lon", form.lonPlaceholder, true));
  const actions = document.createElement("div");
  actions.className = "sp-add-actions";
  actions.append(button, text("span", "sp-add-hint", form.hint));
  f.append(field(form.nameLabel, "name", form.namePlaceholder), coords, field(form.sourceLabel, "source", form.sourcePlaceholder), card, actions);
  root.replaceChildren(f);

  const onSubmit = (e: Event): void => {
    e.preventDefault();
    error.remove();
    card.hidden = true;
    const values: RequestFields = { name: inputs.name.value.trim(), lat: inputs.lat.value.trim(), lon: inputs.lon.value.trim(), source: inputs.source.value.trim() };
    const problem = checkRequest(values, deps.watched, deps.requests);
    if (problem) {
      error.textContent = problem;
      card.before(error);
      return;
    }
    const url = issueUrl(values);
    open(url);
    again.href = url;
    card.hidden = false;
  };
  f.addEventListener("submit", onSubmit);

  return {
    destroy() {
      f.removeEventListener("submit", onSubmit);
      root.replaceChildren();
    },
  };
}
