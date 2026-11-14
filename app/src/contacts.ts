/** A provincial disaster authority and its official web page. */
export interface Authority {
  id: "NDMA" | "PDMA-KP";
  /** The button label. */
  label: "Contact NDMA" | "Contact PDMA";
  name: string;
  /**
   * The authority's own official web page; never a phone number or email. Null means no URL has been
   * verified on the authority's own domain, and the UI hides the button.
   */
  url: string | null;
  /** The authority's own domain. */
  domain: string;
  /** Small print shown under the button, when set. */
  note?: string;
  /** The date the URL was checked, YYYY-MM-DD. */
  checked: string;
}

/** GBDMA's own website could not be verified (gbdma.gog.pk and variants did not resolve on 2026-11-14); swap GB to it when a URL is given. */
export const GBDMA: null = null;

export const AUTHORITIES: Record<"GB" | "KP", Authority> = {
  // Fetched 2026-11-14: title "Contact | National Disaster Management Authority Pakistan", footer "(c) 2026 NDMA Pakistan".
  GB: { id: "NDMA", label: "Contact NDMA", name: "NDMA", url: "https://ndma.gov.pk/contact", domain: "ndma.gov.pk", checked: "2026-11-14", note: "GBDMA has no verified website; NDMA coordinates the provincial authorities." },
  // Fetched 2026-11-14: page title "Provincial Disaster Management Authority - PDMA", Khyber Pakhtunkhwa.
  KP: { id: "PDMA-KP", label: "Contact PDMA", name: "Provincial Disaster Management Authority, Khyber Pakhtunkhwa", url: "https://pdma.gov.pk/contacts", domain: "pdma.gov.pk", checked: "2026-11-14" },
};

/** The authority for a lake's province (GB: GBDMA, KP: PDMA Khyber Pakhtunkhwa), or null. */
export function authorityFor(province: string | null | undefined): Authority | null {
  return province === "GB" || province === "KP" ? AUTHORITIES[province] : null;
}
