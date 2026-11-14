/** A provincial disaster authority and its official web page. */
export interface Authority {
  id: "GBDMA" | "PDMA-KP";
  /** The button label. */
  label: "Contact GBDMA" | "Contact PDMA";
  name: string;
  /**
   * The authority's own official web page; never a phone number or email. Null means no URL has been
   * verified on the authority's own domain, and the UI hides the button.
   */
  url: string | null;
  /** The date the URL was checked, YYYY-MM-DD. */
  checked: string;
}

export const AUTHORITIES: Record<"GB" | "KP", Authority> = {
  // Not verified: gbdma.gog.pk (the address Wikipedia lists), www.gbdma.gog.pk, gbdma.gov.pk and gbdma.gbit.gov.pk
  // did not resolve on 2026-11-14, and gilgitbaltistan.gov.pk does not link to the authority. Left null on purpose.
  GB: { id: "GBDMA", label: "Contact GBDMA", name: "Gilgit-Baltistan Disaster Management Authority", url: null, checked: "2026-11-14" },
  // Fetched 2026-11-14: page title "Provincial Disaster Management Authority - PDMA", Khyber Pakhtunkhwa, domain pdma.gov.pk.
  KP: { id: "PDMA-KP", label: "Contact PDMA", name: "Provincial Disaster Management Authority, Khyber Pakhtunkhwa", url: "https://pdma.gov.pk/contacts", checked: "2026-11-14" },
};

/** The authority for a lake's province (GB: GBDMA, KP: PDMA Khyber Pakhtunkhwa), or null. */
export function authorityFor(province: string | null | undefined): Authority | null {
  return province === "GB" || province === "KP" ? AUTHORITIES[province] : null;
}
