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

// ---------------------------------------------------------------------------
// Financial fact / metric labels
// ---------------------------------------------------------------------------

const FACT_LABELS: Record<string, string> = {
  revenue: "Revenue / Turnover",
  gross_profit: "Gross profit",
  operating_profit: "Operating profit",
  profit_loss_after_tax: "Profit / loss after tax",
  current_assets: "Current assets",
  fixed_assets: "Fixed assets",
  total_assets_less_current_liabilities: "Total assets less current liabilities",
  creditors_within_one_year: "Creditors: within 1 year",
  creditors_after_one_year: "Creditors: after 1 year",
  net_assets_liabilities: "Net assets / liabilities",
  cash: "Cash at bank",
  average_number_of_employees: "Average number of employees",
};

export function formatFactName(name: string): string {
  return FACT_LABELS[name] ?? name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const METRIC_LABELS: Record<string, { label: string; description: string }> = {
  revenue_growth: {
    label: "Revenue growth",
    description: "Year-on-year change in revenue / turnover",
  },
  net_assets_growth: {
    label: "Net assets growth",
    description: "Year-on-year change in net assets / liabilities",
  },
  profit_margin: {
    label: "Net profit margin",
    description: "Profit after tax as a proportion of revenue",
  },
  liquidity_proxy: {
    label: "Liquidity proxy",
    description: "Current assets relative to short-term creditors (not an audited ratio)",
  },
  leverage_proxy: {
    label: "Leverage proxy",
    description: "Total creditors relative to net assets (not an audited ratio)",
  },
};

export function formatMetricName(key: string): string {
  return METRIC_LABELS[key]?.label ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatMetricDescription(key: string): string | null {
  return METRIC_LABELS[key]?.description ?? null;
}

/**
 * Format a large number as an abbreviated currency label for chart axes.
 * e.g. 1_200_000 → "£1.2M", 250_000 → "£250K"
 */
export function formatYAxisLabel(value: number, currency?: string | null): string {
  const symbol = currency === "GBP" ? "£" : currency === "USD" ? "$" : currency === "EUR" ? "€" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${symbol}${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${symbol}${(value / 1_000).toFixed(0)}K`;
  return `${symbol}${value.toFixed(0)}`;
}

// ---------------------------------------------------------------------------
// Officer roles
// ---------------------------------------------------------------------------

const ROLE_LABELS: Record<string, string> = {
  director: "Director",
  secretary: "Company secretary",
  "managing-director": "Managing director",
  nominee: "Nominee",
  "nominee-director": "Nominee director",
  "nominee-secretary": "Nominee secretary",
  "corporate-director": "Corporate director",
  "corporate-secretary": "Corporate secretary",
  chairman: "Chairman",
  "chief-executive-officer": "Chief executive officer",
  "llp-member": "LLP member",
  "llp-designated-member": "Designated LLP member",
  "judicial-factor": "Judicial factor",
  "receiver-and-manager": "Receiver and manager",
  "cic-manager": "CIC manager",
};

export function formatRole(role: string | null | undefined): string | null {
  if (!role) return null;
  return ROLE_LABELS[role.toLowerCase()] ?? role;
}

// ---------------------------------------------------------------------------
// PSC kind labels
// ---------------------------------------------------------------------------

const PSC_KIND_LABELS: Record<string, string> = {
  "individual-person-with-significant-control": "Individual",
  "corporate-entity-person-with-significant-control": "Corporate entity",
  "legal-person-with-significant-control": "Legal person",
  "super-secure-person-with-significant-control": "Super-secure (restricted)",
  "persons-with-significant-control-statement": "PSC statement",
  exemptions: "Exemption",
};

export function formatPscKind(kind: string | null | undefined): string | null {
  if (!kind) return null;
  return PSC_KIND_LABELS[kind.toLowerCase()] ?? kind;
}

// ---------------------------------------------------------------------------
// Nature of control labels
// ---------------------------------------------------------------------------

const NATURE_LABELS: Record<string, string> = {
  "ownership-of-shares-25-to-50-percent": "Ownership of shares (25–50%)",
  "ownership-of-shares-50-to-75-percent": "Ownership of shares (50–75%)",
  "ownership-of-shares-75-to-100-percent": "Ownership of shares (75–100%)",
  "ownership-of-shares-25-to-50-percent-as-trust": "Ownership of shares as trust (25–50%)",
  "ownership-of-shares-50-to-75-percent-as-trust": "Ownership of shares as trust (50–75%)",
  "ownership-of-shares-75-to-100-percent-as-trust": "Ownership of shares as trust (75–100%)",
  "voting-rights-25-to-50-percent": "Voting rights (25–50%)",
  "voting-rights-50-to-75-percent": "Voting rights (50–75%)",
  "voting-rights-75-to-100-percent": "Voting rights (75–100%)",
  "voting-rights-25-to-50-percent-as-trust": "Voting rights as trust (25–50%)",
  "voting-rights-50-to-75-percent-as-trust": "Voting rights as trust (50–75%)",
  "voting-rights-75-to-100-percent-as-trust": "Voting rights as trust (75–100%)",
  "right-to-appoint-and-remove-directors": "Right to appoint / remove directors",
  "right-to-appoint-and-remove-directors-as-trust": "Right to appoint / remove directors (as trust)",
  "right-to-appoint-and-remove-members": "Right to appoint / remove members",
  "significant-influence-or-control": "Significant influence or control",
  "significant-influence-or-control-as-trust": "Significant influence or control (as trust)",
};

export function formatNatureOfControl(nature: string): string {
  return (
    NATURE_LABELS[nature] ??
    nature.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

// ---------------------------------------------------------------------------
// Charge status labels
// ---------------------------------------------------------------------------

const CHARGE_STATUS_LABELS: Record<string, string> = {
  outstanding: "Outstanding",
  "fully-satisfied": "Satisfied",
  "part-satisfied": "Partially satisfied",
  satisfied: "Satisfied",
};

export function formatChargeStatus(status: string | null | undefined): string | null {
  if (!status) return null;
  return CHARGE_STATUS_LABELS[status.toLowerCase()] ?? status;
}
