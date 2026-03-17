"""
Canonical fact name mapper.

Two public functions:
    map_tag(local_name)  — for iXBRL XBRL tag local names
    map_label(text)      — for HTML table row labels

Both return one of the 12 approved canonical fact names, or None if no
mapping is found.  None means the fact will not be persisted.

Canonical names (docs/05-parser-design.md §Canonical fact schema):
    revenue
    gross_profit
    operating_profit_loss
    profit_loss_after_tax
    current_assets
    fixed_assets
    total_assets_less_current_liabilities
    creditors_due_within_one_year
    creditors_due_after_one_year
    net_assets_liabilities
    cash_bank_on_hand
    average_number_of_employees

Tag coverage:
    UK GAAP (uk-gaap:), FRS 102 equivalent tags, Companies House core
    taxonomy (bus:, core:, uk-bus:).  The namespace prefix is stripped
    before lookup so all namespaces sharing the same local name resolve
    identically.

    When the same local name could plausibly mean two different concepts
    (which is rare in UK accounts taxonomy), the more common interpretation
    is used.  Ambiguous tags are excluded from the map rather than guessed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# XBRL tag local-name → canonical fact name
# ---------------------------------------------------------------------------
# Keys are lowercase local names (namespace prefix stripped and lowercased).
# Values are canonical fact names from docs/05-parser-design.md.
#
# Compiled from:
#   - UK GAAP 2009 taxonomy (uk-gaap)
#   - FRS 102 / HMRC taxonomy (uk-bus, bus, core)
#   - Companies House inline XBRL guidance

_TAG_TO_CANONICAL: dict[str, str] = {
    # --- Revenue / Turnover ---
    "turnover": "revenue",
    "turnoverrevenue": "revenue",
    "totalrevenues": "revenue",
    "revenue": "revenue",
    "netrevenue": "revenue",
    "netsales": "revenue",
    "sales": "revenue",

    # --- Gross Profit ---
    "grossprofit": "gross_profit",
    "grossprofitloss": "gross_profit",

    # --- Operating Profit/Loss ---
    "operatingprofit": "operating_profit_loss",
    "operatingprofitloss": "operating_profit_loss",
    "profitlossfromoperations": "operating_profit_loss",
    "profitbeforeinterestandtaxation": "operating_profit_loss",
    "operatingresult": "operating_profit_loss",

    # --- Profit/Loss After Tax ---
    "profitlossforperiod": "profit_loss_after_tax",
    "profitloss": "profit_loss_after_tax",
    "profitlossaftertax": "profit_loss_after_tax",
    "profitlossonordinaryactivitiesaftertax": "profit_loss_after_tax",
    "profitforthefinancialyear": "profit_loss_after_tax",
    "profitforfinancialyear": "profit_loss_after_tax",
    "netincome": "profit_loss_after_tax",
    "netprofit": "profit_loss_after_tax",

    # --- Current Assets ---
    "currentassets": "current_assets",
    "totalcurrentassets": "current_assets",

    # --- Fixed Assets ---
    "fixedassets": "fixed_assets",
    "totalfixedassets": "fixed_assets",
    "tangibleassets": "fixed_assets",
    "tangiblefixedassets": "fixed_assets",
    "propertyplantequipment": "fixed_assets",
    "propertyplantandequipment": "fixed_assets",

    # --- Total Assets Less Current Liabilities ---
    "totalassetslesscurrentliabilities": "total_assets_less_current_liabilities",
    "netcurrentassets": "total_assets_less_current_liabilities",
    "netcurrentassetsliabilities": "total_assets_less_current_liabilities",

    # --- Creditors Due Within One Year ---
    "creditorsduewithoneyear": "creditors_due_within_one_year",
    "creditorsfallingduewithinoneyear": "creditors_due_within_one_year",
    "creditorsamountsfallingduewithinoneyear": "creditors_due_within_one_year",
    "tradecreditors": "creditors_due_within_one_year",
    "tradeandotherpayables": "creditors_due_within_one_year",
    "currentliabilities": "creditors_due_within_one_year",
    "totalcurrentliabilities": "creditors_due_within_one_year",

    # --- Creditors Due After One Year ---
    "creditorsdueafteroneyear": "creditors_due_after_one_year",
    "creditorsfallingdueaftermorethanoneyear": "creditors_due_after_one_year",
    "creditorsamountsfallingdueaftermorethanoneyear": "creditors_due_after_one_year",
    "noncurrentliabilities": "creditors_due_after_one_year",
    "totalnoncurrentliabilities": "creditors_due_after_one_year",
    "longtermborrowing": "creditors_due_after_one_year",

    # --- Net Assets / Liabilities ---
    "netassetsliabilities": "net_assets_liabilities",
    "totalnetassetsliabilities": "net_assets_liabilities",
    "capitalandreserves": "net_assets_liabilities",
    "totalequity": "net_assets_liabilities",
    "shareholdersfunds": "net_assets_liabilities",
    "equityattributabletoownersofparent": "net_assets_liabilities",

    # --- Cash and Cash Equivalents ---
    "cashbankonhand": "cash_bank_on_hand",
    "cashandcashequivalents": "cash_bank_on_hand",
    "cashatbank": "cash_bank_on_hand",
    "cash": "cash_bank_on_hand",
    "cashandbankinhand": "cash_bank_on_hand",

    # --- Average Number of Employees ---
    "averagenumberemployeesduringperiod": "average_number_of_employees",
    "averagenumberofemployees": "average_number_of_employees",
    "averagenumberofemployeesduringtheyear": "average_number_of_employees",
    "numberofemployees": "average_number_of_employees",
}


# ---------------------------------------------------------------------------
# HTML label synonym → canonical fact name
# ---------------------------------------------------------------------------
# Keys are normalized text: lowercased, stripped, punctuation variants collapsed.
# Values are canonical fact names.

_LABEL_TO_CANONICAL: dict[str, str] = {
    # Revenue
    "turnover": "revenue",
    "turnover/revenue": "revenue",
    "revenue": "revenue",
    "net revenue": "revenue",
    "net sales": "revenue",
    "sales": "revenue",
    "total revenue": "revenue",
    "total turnover": "revenue",
    "income": "revenue",
    "gross income": "revenue",

    # Gross Profit
    "gross profit": "gross_profit",
    "gross profit/(loss)": "gross_profit",
    "gross profit / (loss)": "gross_profit",

    # Operating Profit
    "operating profit": "operating_profit_loss",
    "operating profit/(loss)": "operating_profit_loss",
    "operating profit / (loss)": "operating_profit_loss",
    "operating loss": "operating_profit_loss",
    "profit/(loss) from operations": "operating_profit_loss",
    "profit / (loss) from operations": "operating_profit_loss",
    "profit before interest and taxation": "operating_profit_loss",
    "profit before interest": "operating_profit_loss",

    # Profit After Tax
    "profit after tax": "profit_loss_after_tax",
    "profit/(loss) after tax": "profit_loss_after_tax",
    "profit for the year": "profit_loss_after_tax",
    "profit/(loss) for the year": "profit_loss_after_tax",
    "profit for the financial year": "profit_loss_after_tax",
    "profit/(loss) for the financial year": "profit_loss_after_tax",
    "profit on ordinary activities after taxation": "profit_loss_after_tax",
    "net profit": "profit_loss_after_tax",
    "net income": "profit_loss_after_tax",

    # Current Assets
    "current assets": "current_assets",
    "total current assets": "current_assets",

    # Fixed Assets
    "fixed assets": "fixed_assets",
    "tangible fixed assets": "fixed_assets",
    "tangible assets": "fixed_assets",
    "total fixed assets": "fixed_assets",

    # Total Assets Less Current Liabilities
    "total assets less current liabilities": "total_assets_less_current_liabilities",
    "net current assets": "total_assets_less_current_liabilities",
    "net current assets/(liabilities)": "total_assets_less_current_liabilities",
    "net current liabilities": "total_assets_less_current_liabilities",

    # Creditors Within One Year
    "creditors: amounts falling due within one year": "creditors_due_within_one_year",
    "creditors due within one year": "creditors_due_within_one_year",
    "creditors falling due within one year": "creditors_due_within_one_year",
    "trade creditors": "creditors_due_within_one_year",
    "current liabilities": "creditors_due_within_one_year",
    "total current liabilities": "creditors_due_within_one_year",

    # Creditors After One Year
    "creditors: amounts falling due after more than one year": "creditors_due_after_one_year",
    "creditors due after one year": "creditors_due_after_one_year",
    "creditors falling due after more than one year": "creditors_due_after_one_year",
    "non-current liabilities": "creditors_due_after_one_year",
    "total non-current liabilities": "creditors_due_after_one_year",

    # Net Assets
    "net assets": "net_assets_liabilities",
    "net assets/(liabilities)": "net_assets_liabilities",
    "net liabilities": "net_assets_liabilities",
    "total equity": "net_assets_liabilities",
    "shareholders' funds": "net_assets_liabilities",
    "shareholders funds": "net_assets_liabilities",
    "capital and reserves": "net_assets_liabilities",

    # Cash
    "cash and cash equivalents": "cash_bank_on_hand",
    "cash at bank and in hand": "cash_bank_on_hand",
    "cash at bank": "cash_bank_on_hand",
    "cash and bank balances": "cash_bank_on_hand",

    # Employees
    "average number of employees": "average_number_of_employees",
    "average number of employees during the year": "average_number_of_employees",
    "average number of employees during the period": "average_number_of_employees",
    "number of employees": "average_number_of_employees",
}


def map_tag(local_name: str) -> str | None:
    """
    Map an XBRL tag local name to a canonical fact name.

    The namespace prefix must already be stripped (pass the part after ':').
    Performs case-insensitive lookup after lowercasing and removing underscores
    and hyphens so minor taxonomy naming variants resolve correctly.

    Returns a canonical fact name or None if no mapping exists.
    """
    normalized = local_name.lower().replace("_", "").replace("-", "")
    return _TAG_TO_CANONICAL.get(normalized)


def map_label(text: str) -> str | None:
    """
    Map an HTML label text to a canonical fact name.

    Normalises the input: lowercase, strip whitespace, collapse runs of
    whitespace to single spaces.  Matches exact normalized forms only;
    partial substring matching is not used to avoid false positives.

    Returns a canonical fact name or None if no mapping exists.
    """
    normalized = " ".join(text.lower().strip().split())
    return _LABEL_TO_CANONICAL.get(normalized)
