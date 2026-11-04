import copyJson from "./content/storyPage.json";

const form = copyJson.add.form;

export type RequestState = "queued" | "searched" | "search_failed" | "accepted" | "rejected";

export type LakeRequest = {
  id: number;
  name: string;
  lat: number;
  lon: number;
  state: RequestState;
  passes: number | null;
  tracks: string[];
  first: string | null;
  last: string | null;
  reason: string | null;
  created: string;
};

export interface RequestsClient {
  health(): Promise<boolean>;
  list(): Promise<LakeRequest[]>;
  submit(body: { name: string; lat: string; lon: string; source: string }): Promise<LakeRequest>;
}

const OPEN: RequestState[] = ["queued", "searched", "search_failed"];

export function isOpen(r: LakeRequest): boolean {
  return OPEN.includes(r.state);
}

/** The status line of a request card. Requests never carry a lake status. */
export function requestLine(r: LakeRequest): string {
  if (r.state === "searched") {
    const n = r.passes ?? 0;
    const tracks = r.tracks.length ? ` on tracks ${r.tracks.join(", ")}` : "";
    return `Searched: ${n} NISAR ${n === 1 ? "pass" : "passes"}${tracks}`;
  }
  if (r.state === "search_failed") return r.reason ? `Search failed: ${r.reason}` : "Search failed";
  if (r.state === "accepted") return "Accepted";
  if (r.state === "rejected") return r.reason ? `Not added: ${r.reason}` : "Not added";
  return "Queued";
}

/** The request server's base URL: VITE_REQUESTS_API at build time, else "api" (same origin or the dev proxy). */
export function createRequestsClient(
  fetchFn: typeof fetch = (...a) => fetch(...a),
  base: string = import.meta.env.VITE_REQUESTS_API ?? "api",
): RequestsClient {
  async function call(path: string, init?: RequestInit): Promise<unknown> {
    let res: Response;
    try {
      res = await fetchFn(`${base}/${path}`, init);
    } catch {
      throw new Error(form.networkError);
    }
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* not JSON */
    }
    if (!res.ok) {
      // Only a message the server wrote is shown as written; a gateway page or empty body gets the approved wording.
      const msg = body && typeof body === "object" && "error" in body ? String((body as { error: unknown }).error) : form.networkError;
      throw new Error(msg);
    }
    return body;
  }
  return {
    async health() {
      try {
        const b = (await call("health")) as { ok?: unknown } | null;
        return b?.ok === true;
      } catch {
        return false;
      }
    },
    async list() {
      const b = (await call("lake-requests")) as { requests?: LakeRequest[] } | null;
      return b?.requests ?? [];
    },
    async submit(body) {
      return (await call("lake-requests", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      })) as LakeRequest;
    },
  };
}

function text<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string | undefined, t: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  e.textContent = t;
  return e;
}

/**
 * The form in section 06. Disabled with a plain line when the server is not there. After a submit it shows the
 * request and polls the list so the card moves from Queued to Searched. Server strings are only ever textContent.
 */
export function mountAddLake(
  root: HTMLElement,
  client: RequestsClient,
  onChange: (open: LakeRequest[]) => void,
  opts: { pollMs?: number; pollFor?: number } = {},
): { destroy(): void } {
  const pollMs = opts.pollMs ?? 5000;
  const pollFor = opts.pollFor ?? 60000;
  let alive = true;
  let timer: ReturnType<typeof setInterval> | null = null;
  let stopAt = 0;
  let mine: number | null = null;

  const inputs: Record<"name" | "lat" | "lon" | "source", HTMLInputElement> = {
    name: document.createElement("input"),
    lat: document.createElement("input"),
    lon: document.createElement("input"),
    source: document.createElement("input"),
  };
  const field = (label: string, key: keyof typeof inputs, placeholder: string, decimal = false): HTMLLabelElement => {
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
  const closed = text("p", "sp-add-closed", form.closed);
  closed.hidden = true;
  const error = text("p", "sp-add-error", "");
  error.setAttribute("role", "alert");
  const card = document.createElement("div");
  card.className = "sp-add-card";
  card.setAttribute("role", "status");
  card.hidden = true;
  const button = text("button", "sp-btn sp-btn-primary", form.submitLabel);
  button.type = "submit";
  const f = document.createElement("form");
  f.noValidate = true;
  const coords = document.createElement("div");
  coords.className = "sp-field-pair";
  coords.append(field(form.latLabel, "lat", form.latPlaceholder, true), field(form.lonLabel, "lon", form.lonPlaceholder, true));
  f.append(
    field(form.nameLabel, "name", form.namePlaceholder),
    coords,
    field(form.sourceLabel, "source", form.sourcePlaceholder),
    closed,
    card,
    Object.assign(document.createElement("div"), { className: "sp-add-actions" }),
  );
  f.lastElementChild!.append(button, text("span", "sp-add-hint", form.hint));

  const setEnabled = (on: boolean): void => {
    for (const i of Object.values(inputs)) i.disabled = !on;
    button.disabled = !on;
    closed.hidden = on;
  };
  setEnabled(false);
  root.replaceChildren(f);

  const showCard = (r: LakeRequest): void => {
    card.replaceChildren(text("div", "sp-add-card-title", r.name), text("div", "sp-add-card-line", requestLine(r)));
    card.hidden = false;
  };

  const stopPolling = (): void => {
    if (timer !== null) clearInterval(timer);
    timer = null;
  };

  async function refresh(): Promise<void> {
    try {
      const rows = await client.list();
      if (!alive) return;
      onChange(rows.filter(isOpen));
      const m = rows.find((r) => r.id === mine);
      if (m) {
        showCard(m);
        if (!isOpen(m)) stopPolling();
      }
    } catch {
      /* keep the last list; the next poll may succeed */
    }
  }

  const startPolling = (): void => {
    stopPolling();
    stopAt = Date.now() + pollFor;
    timer = setInterval(() => {
      if (Date.now() >= stopAt) return stopPolling();
      void refresh();
    }, pollMs);
  };

  const onSubmit = async (e: Event): Promise<void> => {
    e.preventDefault();
    error.remove();
    button.disabled = true;
    try {
      const r = await client.submit({ name: inputs.name.value, lat: inputs.lat.value, lon: inputs.lon.value, source: inputs.source.value });
      if (!alive) return;
      mine = r.id;
      showCard(r);
      for (const i of Object.values(inputs)) i.value = "";
      void refresh();
      startPolling();
    } catch (err) {
      if (!alive) return;
      error.textContent = err instanceof Error && err.message ? err.message : form.networkError;
      card.before(error);
    } finally {
      if (alive) button.disabled = false;
    }
  };
  const handler = (e: Event): void => void onSubmit(e);
  f.addEventListener("submit", handler);

  void (async () => {
    const ok = await client.health();
    if (!alive) return;
    if (!ok) return;
    setEnabled(true);
    await refresh();
  })();

  return {
    destroy() {
      alive = false;
      stopPolling();
      f.removeEventListener("submit", handler);
      root.replaceChildren();
    },
  };
}
