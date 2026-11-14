/** A provincial disaster authority and its official web page (Task 25 fills the verified URLs). */
export interface Authority {
  id: "GBDMA" | "PDMA";
  /** The button label, "Contact GBDMA". */
  label: string;
  /** The authority's own web page; never a phone number or email. */
  url: string;
  /** The date the URL was checked, YYYY-MM-DD. */
  checked: string;
}

/** The authority for a lake's province (GB: GBDMA, KP: PDMA Khyber Pakhtunkhwa). A stub until the URLs are verified. */
export function authorityFor(_province: string | null | undefined): Authority | null {
  return null;
}
