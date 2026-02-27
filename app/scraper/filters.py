"""Filters to exclude public/enterprise companies and keep only mid-market B2B leads."""

# Major public company domains to always skip
PUBLIC_COMPANY_DOMAINS = {
    # Aerospace & Defense
    "boeing.com", "lockheedmartin.com", "rtx.com", "raytheon.com",
    "northropgrumman.com", "generaldynamics.com", "l3harris.com",
    "bae.com", "baesystems.com", "textron.com", "leidos.com",
    "geaerospace.com", "ge.com", "rolls-royce.com",
    "honeywell.com", "aerospace.honeywell.com", "safran-group.com",
    "airbus.com", "thalesgroup.com", "leonardocompany.com",
    "gulfstream.com", "bombardier.com", "embraer.com",
    "howmet.com", "transdigm.com", "hexcel.com", "spirit.com",
    # Industrial / General Conglomerates
    "3m.com", "siemens.com", "caterpillar.com", "deere.com",
    "cummins.com", "parker.com", "emerson.com", "rockwellautomation.com",
    "danaher.com", "dover.com", "illinois-tool-works.com", "itw.com",
    "eaton.com", "roper.com", "fortive.com", "ametek.com",
    "abb.com", "schneider-electric.com",
    # Chemicals
    "basf.com", "dow.com", "dupont.com", "3m.com", "ppg.com",
    "sherwin-williams.com", "lyondellbasell.com", "eastman.com",
    "celanese.com", "huntsman.com", "ashland.com", "rpm.com",
    # Medical / Scientific
    "medtronic.com", "abbott.com", "bd.com", "stryker.com",
    "bostonscientific.com", "edwardslifesciences.com",
    "thermofisher.com", "danaher.com", "agilent.com",
    "waters.com", "bio-rad.com", "perkinelmer.com",
    "johnsonandjohnson.com", "jnj.com", "baxter.com",
    "ge.com", "gehealthcare.com", "philips.com",
    # Building Materials
    "holcim.com", "cemex.com", "vulcanmat.com", "martinmarietta.com",
    "jameshardie.com", "owenscorning.com", "masco.com",
    "sherwin-williams.com", "rpm.com", "boise-cascade.com",
    # Electrical / Electronics
    "te.com", "amphenol.com", "molex.com", "vishay.com",
    "keysight.com", "hubbell.com", "nvent.com", "regal-rexnord.com",
    "intel.com", "ti.com", "analog.com", "microchip.com",
    "samsung.com", "sony.com", "panasonic.com", "toshiba.com",
    # Commodity / Trading
    "glencore.com", "cargill.com", "adm.com", "bunge.com",
    "trafigura.com", "vitol.com", "mercuria.com",
    # General mega-corps
    "apple.com", "microsoft.com", "google.com", "amazon.com",
    "meta.com", "tesla.com", "nvidia.com", "ibm.com", "oracle.com",
    "cisco.com", "dell.com", "hp.com", "hpe.com",
}

# Page text indicators that suggest a public/enterprise company
PUBLIC_INDICATORS = [
    "NYSE:", "NASDAQ:", "stock ticker", "investor relations",
    "annual report", "SEC filing", "10-K", "10-Q",
    "Fortune 500", "Fortune 100", "S&P 500",
]


def is_public_company_domain(domain: str) -> bool:
    """Check if domain belongs to a known public/enterprise company."""
    domain = domain.lower().removeprefix("www.")
    return domain in PUBLIC_COMPANY_DOMAINS


def has_public_company_indicators(html: str) -> bool:
    """Check if page HTML suggests this is a public company."""
    html_lower = html.lower()
    matches = sum(1 for indicator in PUBLIC_INDICATORS if indicator.lower() in html_lower)
    # Need at least 2 indicators to flag — one might be coincidental
    return matches >= 2
