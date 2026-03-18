/**
 * Pure formatting utilities. No server-only APIs — safe to import anywhere.
 */

// ---------------------------------------------------------------------------
// Class name merging (inline substitute for clsx)
// ---------------------------------------------------------------------------

export function cn(
  ...classes: (string | undefined | null | false | 0)[]
): string {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------------------
// Date formatting
// ---------------------------------------------------------------------------

const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

/**
 * Format an ISO date string to "1 Jan 2023". Returns null if input is nullish.
 */
export function formatDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
  try {
    // Parse YYYY-MM-DD safely without timezone shift
    const [y, m, d] = dateStr.split("-").map(Number);
    return DATE_FMT.format(new Date(y, m - 1, d));
  } catch {
    return dateStr;
  }
}

/**
 * Relative time from an ISO datetime string, e.g. "3 days ago".
 */
export function formatRelativeTime(
  dateStr: string | null | undefined,
): string | null {
  if (!dateStr) return null;
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffDays = Math.floor(diffMs / 86_400_000);
    if (diffDays < 1) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 30) return `${diffDays} days ago`;
    const months = Math.floor(diffDays / 30);
    if (months === 1) return "1 month ago";
    if (months < 12) return `${months} months ago`;
    const years = Math.floor(diffDays / 365);
    return years === 1 ? "1 year ago" : `${years} years ago`;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Currency formatting
// ---------------------------------------------------------------------------

const _currencyFormatters: Map<string, Intl.NumberFormat> = new Map();

function getCurrencyFmt(currency: string): Intl.NumberFormat {
  let fmt = _currencyFormatters.get(currency);
  if (!fmt) {
    fmt = new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    });
    _currencyFormatters.set(currency, fmt);
  }
  return fmt;
}

/**
 * Format a Decimal-as-string value with currency symbol, e.g. "£1,000,000".
 * Returns null when either value or currency is missing.
 */
export function formatCurrency(
  value: string | null | undefined,
  currency: string | null | undefined,
): string | null {
  if (!value || !currency) return null;
  try {
    const num = parseFloat(value);
    if (!isFinite(num)) return null;
    return getCurrencyFmt(currency).format(num);
  } catch {
    return null;
  }
}

/**
 * Format a plain number string with thousand separators.
 */
export function formatNumber(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  try {
    const num = parseFloat(value);
    if (!isFinite(num)) return null;
    return new Intl.NumberFormat("en-GB").format(num);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Company type labels
// ---------------------------------------------------------------------------

const COMPANY_TYPE_LABELS: Record<string, string> = {
  ltd: "Private limited company",
  plc: "Public limited company",
  llp: "Limited liability partnership",
  "private-limited-guarant-nsc": "Private limited by guarantee",
  "private-limited-guarant-nsc-limited-exemption": "Private limited by guarantee",
  "private-unlimited": "Private unlimited company",
  "private-unlimited-nsc": "Private unlimited company",
  "public-limited-company": "Public limited company",
  "limited-partnership": "Limited partnership",
  "royal-charter": "Royal charter",
  "community-interest-company": "Community interest company",
  "charitable-incorporated-organisation": "Charitable incorporated organisation",
  "scottish-charitable-incorporated-organisation":
    "Scottish charitable incorporated organisation",
  "uk-establishment": "UK establishment",
  "overseas-company": "Overseas company",
  "other": "Other",
};

export function formatCompanyType(
  type: string | null | undefined,
): string | null {
  if (!type) return null;
  return COMPANY_TYPE_LABELS[type.toLowerCase()] ?? type;
}

// ---------------------------------------------------------------------------
// Company status labels
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  dissolved: "Dissolved",
  liquidation: "In liquidation",
  receivership: "In receivership",
  administration: "In administration",
  "voluntary-arrangement": "Voluntary arrangement",
  "converted-closed": "Converted / closed",
  "insolvency-proceedings": "Insolvency proceedings",
};

export function formatCompanyStatus(
  status: string | null | undefined,
): string {
  if (!status) return "Unknown";
  return STATUS_LABELS[status.toLowerCase()] ?? status;
}

// ---------------------------------------------------------------------------
// Address formatting
// ---------------------------------------------------------------------------

/**
 * Format a registered_office_address dict into a readable one-liner.
 * Returns null when the address object is empty or missing.
 */
export function formatAddress(
  addr: Record<string, string> | null | undefined,
): string | null {
  if (!addr) return null;
  const parts = [
    addr.premises,
    addr.address_line_1,
    addr.address_line_2,
    addr.locality,
    addr.region,
    addr.postal_code,
    addr.country,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

// ---------------------------------------------------------------------------
// Accounts type labels
// ---------------------------------------------------------------------------

const ACCOUNTS_TYPE_LABELS: Record<string, string> = {
  full: "Full accounts",
  small: "Small company accounts",
  "micro-entity": "Micro-entity accounts",
  "abridged": "Abridged accounts",
  "dormant": "Dormant company accounts",
  "group": "Group accounts",
  "interim": "Interim accounts",
  "total-exemption-full": "Total exemption – full",
  "total-exemption-small": "Total exemption – small",
};

export function formatAccountsType(
  type: string | null | undefined,
): string | null {
  if (!type) return null;
  return ACCOUNTS_TYPE_LABELS[type.toLowerCase()] ?? type;
}
