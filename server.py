#!/usr/bin/env python3
"""
MEOK IMO MARPOL Marine Compliance MCP
=====================================

By MEOK AI Labs - https://haulage.app - MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-imo-marpol-marine-mcp -->

WHAT THIS DOES
--------------
MEOK started with road. This MCP extends the umbrella into sea — the next
vertical for short-sea operators (RoRo car carriers, Channel freight),
container shipping, and the marine fuel cliff for net-zero.

Eight callable compliance tools covering the live cliffs of 2026:

  MARPOL Annex VI    Air pollution + sulfur cap (0.5% global / 0.1% ECA)
  EU ETS Maritime    Extended to shipping Jan 2024, 50% intra-EU
  IMO CII            Annual A-E rating since Jan 2023
  IMO EEXI           Energy Efficiency Existing Ship Index ratings
  IMDG Code          Class 9 lithium batteries + other DG sea-borne
  Bunker fuel        Sulfur/NOx/PM test vs BDN
  IMO BWM            Ballast Water Management D-2 standard
  Port State Control Paris MoU + Tokyo MoU inspection pack prep

REAL EVENTS THAT MOTIVATE THIS MCP
----------------------------------
- Felicity Ace (Feb 2022) - 4,000 vehicles + lithium-ion fire sank ship,
  USD 401m insurance loss. Class 9 DG documentation gap.
- Fremantle Highway (Jul 2023) - 3,783 vehicles, similar Class 9 li-ion
  origin suspected. Detention + investigation cost > USD 100m.
- Paris MoU detentions 2024 = 3.4% of inspections, average delay 24-72h,
  USD 30-100k per detention.
- EU ETS first surrender Sep 2025 - shipping companies surrendered
  EUR ~2.5 billion in allowances across the first reporting period.

TOOLS (8)
---------
- check_marpol_annex_compliance(vessel, fuel_type, route) -> sulfur + ECA
- check_eu_ets_maritime(vessel, voyage) -> EU ETS exposure + cost estimate
- check_imo_ccc_carbon_intensity(vessel) -> CII A/B/C/D/E rating
- check_eexi_efficiency(vessel) -> EEXI rating vs reference line
- check_imdg_code_dangerous_goods(cargo) -> IMDG Class + segregation
- check_bunker_compliance(fuel_sample) -> sulfur/NOx/PM vs BDN
- check_ballast_water_management(vessel) -> BWM Convention D-2 status
- prepare_psc_inspection_pack(vessel, port) -> PSC ready-pack

WHY YOU PAY
-----------
Pro tier GBP 399/mo justified by:
  - One PSC detention avoided = USD 30-100k saved
  - EU ETS misreporting penalty (Article 16 EU ETS Directive) up to EUR 100/tCO2
  - MARPOL Annex VI fines (US) up to USD 250k + vessel detention
  - CII E-rating triggers corrective action plan = lost charter revenue

PRICING
-------
Free MIT self-host - GBP 149/mo Starter - GBP 399/mo Pro - GBP 1,999/mo Fleet.

REGULATORY BASIS
----------------
IMO MARPOL (International Convention for the Prevention of Pollution from Ships)
MARPOL Annex VI (air pollution + GHG)
IMO CII / EEXI Resolutions MEPC.336(76) and MEPC.337(76)
EU ETS Directive 2003/87/EC (extended to maritime, Directive (EU) 2023/959)
IMDG Code (International Maritime Dangerous Goods Code)
IMO Ballast Water Management Convention 2004 (in force 2017)
Paris MoU + Tokyo MoU on Port State Control
"""

from __future__ import annotations
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr
import hashlib, hmac, json, math, os
from datetime import datetime, timezone, date
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("meok-imo-marpol-marine")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ----------------------------------------------------------------------
# Regulatory tables
# ----------------------------------------------------------------------

# MARPOL Annex VI sulfur caps (% m/m)
MARPOL_SULFUR_CAP_GLOBAL = 0.5     # outside ECAs since 1 Jan 2020
MARPOL_SULFUR_CAP_ECA = 0.1        # inside ECAs since 1 Jan 2015

# Emission Control Areas under MARPOL Annex VI
ECA_ZONES = {
    "north_sea": "North Sea ECA (SOx + NOx, since 2007/2021)",
    "baltic": "Baltic Sea ECA (SOx + NOx, since 2006/2021)",
    "north_america": "North American ECA (200 nm off US/CAN coast, since 2012)",
    "us_caribbean": "US Caribbean Sea ECA (since 2014)",
    "mediterranean": "Mediterranean Sea ECA (SOx-only, in force from 1 May 2025)",
}

# EU ETS maritime — phase-in percentages of verified emissions to surrender
EU_ETS_PHASE_IN = {
    2024: 0.40,    # 40% of verified emissions
    2025: 0.70,    # 70%
    2026: 1.00,    # 100% (full coverage)
    2027: 1.00,
}

# EU ETS scope multipliers by voyage type
EU_ETS_SCOPE = {
    "intra_eu": 1.00,       # 100% of emissions covered
    "eu_to_third": 0.50,    # 50% of emissions covered
    "third_to_eu": 0.50,    # 50% of emissions covered
    "non_eu": 0.00,         # not covered
    "at_berth_eu": 1.00,    # 100% at-berth EU emissions
}

# CII rating boundaries vs reference line (lower attained CII = better = A)
# Reference: MEPC.354(78) "2022 Guidelines on the operational carbon intensity rating"
# d-values are the boundaries between A/B/C/D/E (each year tightens by 2%)
CII_BOUNDARIES = {
    # year: (d1_A_B, d2_B_C, d3_C_D, d4_D_E)
    2023: (0.86, 0.94, 1.06, 1.18),
    2024: (0.86, 0.94, 1.06, 1.18),
    2025: (0.86, 0.94, 1.06, 1.18),
    2026: (0.86, 0.94, 1.06, 1.18),
}

# EEXI required reduction vs EEDI reference baseline (% reduction)
EEXI_REQUIRED_REDUCTION = {
    "bulk_carrier":      0.20,
    "tanker":            0.20,
    "container":         0.30,    # 15-50% depending on size class
    "gas_carrier":       0.30,
    "general_cargo":     0.20,
    "ro_ro_cargo":       0.05,
    "ro_ro_passenger":   0.05,
    "lng_carrier":       0.30,
}

# IMDG Code DG classes (sea-borne dangerous goods)
IMDG_CLASSES = {
    "1": "Explosives (sub-divisions 1.1 to 1.6)",
    "2.1": "Flammable gases (LPG, hydrogen)",
    "2.2": "Non-flammable, non-toxic gases (nitrogen, CO2)",
    "2.3": "Toxic gases (chlorine, ammonia)",
    "3":   "Flammable liquids (petrol, diesel)",
    "4.1": "Flammable solids",
    "4.2": "Spontaneously combustible substances",
    "4.3": "Substances dangerous when wet",
    "5.1": "Oxidising substances",
    "5.2": "Organic peroxides",
    "6.1": "Toxic substances",
    "6.2": "Infectious substances",
    "7":   "Radioactive materials",
    "8":   "Corrosive substances",
    "9":   "Miscellaneous dangerous goods (includes lithium batteries UN3480/3481)",
}

# Common Class 9 lithium UN numbers
LITHIUM_UN_NUMBERS = {
    "UN3480": "Lithium-ion batteries (standalone)",
    "UN3481": "Lithium-ion batteries in/with equipment",
    "UN3090": "Lithium metal batteries",
    "UN3091": "Lithium metal batteries in/with equipment",
    "UN3171": "Battery-powered vehicle (electric vehicle)",
    "UN3536": "Lithium batteries installed in cargo transport unit",
}

# Port State Control regional MoUs + 2024 detention rates
PSC_MOUS = {
    "paris":     ("Paris MoU", "EU + Canada + Russia + UK + Norway + Iceland", 0.034),
    "tokyo":     ("Tokyo MoU", "Asia-Pacific", 0.031),
    "uscg":      ("US Coast Guard", "US ports", 0.025),
    "indian":    ("Indian Ocean MoU", "Indian Ocean basin", 0.040),
    "med":       ("Mediterranean MoU", "Med + NAfrica", 0.038),
    "vina_del":  ("Vina del Mar (Latin Am)", "Latin America", 0.050),
    "abuja":     ("Abuja MoU", "West/Central Africa", 0.055),
    "black_sea": ("Black Sea MoU", "Black Sea coast", 0.045),
    "riyadh":    ("Riyadh MoU", "GCC + Yemen", 0.042),
    "caribbean": ("Caribbean MoU", "Caribbean basin", 0.040),
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _sign(payload: dict) -> str:
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(_HMAC_SECRET.encode(),
                    json.dumps(payload, sort_keys=True, default=str).encode(),
                    hashlib.sha256).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {**payload, "ts": _ts(), "sig": _sign(payload),
            "issuer": "meok-imo-marpol-marine-mcp", "version": "1.0.0"}


def _grade_cii(attained_ratio: float, year: int = 2026) -> str:
    """Map attained-CII / required-CII ratio to A/B/C/D/E."""
    d1, d2, d3, d4 = CII_BOUNDARIES.get(year, CII_BOUNDARIES[2026])
    if attained_ratio < d1:
        return "A"
    if attained_ratio < d2:
        return "B"
    if attained_ratio < d3:
        return "C"
    if attained_ratio < d4:
        return "D"
    return "E"


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------


def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Fail-open."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def check_marpol_annex_compliance(
    vessel_imo: str,
    fuel_type: str,
    fuel_sulfur_pct: float,
    route_zone: str = "global",
    has_scrubber: bool = False,
) -> dict:
    """MARPOL Annex VI air-pollution check — sulfur cap + ECA compliance.

    Since 1 Jan 2020 global sulfur cap is 0.5% m/m; inside ECAs it is 0.1%
    since 1 Jan 2015. Vessels with approved exhaust gas cleaning systems
    (scrubbers) may use higher-sulfur fuel provided equivalent SOx removal.

    Args:
      vessel_imo: 7-digit IMO number
      fuel_type: 'hfo' / 'mgo' / 'mdo' / 'vlsfo' / 'ulsfo' / 'lng' / 'methanol' / 'ammonia'
      fuel_sulfur_pct: sulfur content of fuel as % m/m (from BDN)
      route_zone: 'global' or ECA key from ECA_ZONES
      has_scrubber: True if vessel has IMO-approved EGCS
    """
    is_eca = route_zone in ECA_ZONES
    cap = MARPOL_SULFUR_CAP_ECA if is_eca else MARPOL_SULFUR_CAP_GLOBAL

    # Scrubber equivalence per MARPOL VI Reg 4
    effective_sulfur_pct = (fuel_sulfur_pct * 0.05) if has_scrubber else fuel_sulfur_pct
    breach = effective_sulfur_pct > cap + 1e-9

    issues = []
    if breach:
        issues.append(
            f"SULFUR BREACH — fuel {fuel_sulfur_pct}% S exceeds cap {cap}% "
            f"in {'ECA' if is_eca else 'global zone'}"
        )
    if fuel_type.lower() == "hfo" and not has_scrubber:
        issues.append("HFO without scrubber is non-compliant outside legacy permission cases")

    return _attestation({
        "tool": "check_marpol_annex_compliance",
        "vessel_imo": vessel_imo,
        "fuel_type": fuel_type,
        "fuel_sulfur_pct": fuel_sulfur_pct,
        "route_zone": route_zone,
        "is_eca": is_eca,
        "applicable_cap_pct": cap,
        "scrubber_credit": has_scrubber,
        "effective_sulfur_pct": round(effective_sulfur_pct, 4),
        "compliant": not breach,
        "issues": issues,
        "regulator_ref": "MARPOL Annex VI Reg 14",
        "advisory": (
            "DO NOT bunker — non-compliant. Use VLSFO/ULSFO or fit scrubber. "
            "USCG fines up to USD 250k + detention."
            if breach else "Compliant — retain BDN for 3 years per Reg 18."
        ),
    })


@mcp.tool()
def check_eu_ets_maritime(
    vessel_imo: str,
    voyage_type: str,
    co2_tonnes: float,
    voyage_year: int = 2026,
    ets_price_eur_per_tco2: float = 80.0,
) -> dict:
    """EU ETS maritime exposure check (Directive (EU) 2023/959).

    EU ETS extended to shipping >5000 GT since 1 Jan 2024. Phase-in:
    2024 = 40% of verified emissions, 2025 = 70%, 2026 = 100%.

    Args:
      voyage_type: 'intra_eu' / 'eu_to_third' / 'third_to_eu' / 'non_eu' / 'at_berth_eu'
      co2_tonnes: voyage CO2 emissions (tonnes)
      ets_price_eur_per_tco2: EUA market price assumption
    """
    phase_in = EU_ETS_PHASE_IN.get(voyage_year, 1.00)
    scope = EU_ETS_SCOPE.get(voyage_type, 0.00)
    chargeable_tco2 = co2_tonnes * scope * phase_in
    cost_eur = chargeable_tco2 * ets_price_eur_per_tco2

    return _attestation({
        "tool": "check_eu_ets_maritime",
        "vessel_imo": vessel_imo,
        "voyage_type": voyage_type,
        "voyage_year": voyage_year,
        "co2_tonnes_total": co2_tonnes,
        "scope_factor": scope,
        "phase_in_factor": phase_in,
        "chargeable_tco2": round(chargeable_tco2, 2),
        "ets_price_eur_per_tco2": ets_price_eur_per_tco2,
        "ets_cost_eur": round(cost_eur, 2),
        "regulator_ref": "EU ETS Directive 2003/87/EC + Directive (EU) 2023/959",
        "advisory": (
            "Surrender allowances by 30 September following verified year. "
            "Failure penalty EUR 100/tCO2 + obligation to surrender + name + shame."
        ),
        "covered_by_eu_ets": scope > 0.0,
    })


@mcp.tool()
def check_imo_ccc_carbon_intensity(
    vessel_imo: str,
    vessel_type: str,
    dwt: float,
    annual_distance_nm: float,
    annual_fuel_tonnes: float,
    fuel_carbon_factor: float = 3.114,
    rating_year: int = 2026,
    required_cii: Optional[float] = None,
) -> dict:
    """IMO Carbon Intensity Indicator (CII) annual rating A-E since Jan 2023.

    CII (AER variant) = annual_CO2 / (DWT * annual_distance_nm).
    Attained-CII divided by Required-CII gives the boundary ratio for
    A/B/C/D/E rating. Three consecutive D or single E triggers a Corrective
    Action Plan (CAP) under MARPOL Annex VI Reg 28.

    Args:
      vessel_type: bulk_carrier / tanker / container / gas_carrier / etc.
      dwt: deadweight tonnage
      annual_distance_nm: nautical miles travelled
      annual_fuel_tonnes: annual fuel consumption (tonnes)
      fuel_carbon_factor: tCO2 per tonne fuel (3.114 typical for HFO/VLSFO)
      required_cii: if known, supply directly; else heuristic from DWT
    """
    co2_tonnes = annual_fuel_tonnes * fuel_carbon_factor
    denom = max(1.0, dwt * annual_distance_nm)
    attained_cii = co2_tonnes * 1_000_000.0 / denom    # gCO2/(dwt*nm)

    # Heuristic for required-CII if not supplied (rough — real value from
    # MEPC.339(76) lookup tables per ship type/size)
    if required_cii is None:
        if vessel_type == "container":
            required_cii = max(2.0, 30.0 - 0.0003 * dwt)
        elif vessel_type == "bulk_carrier":
            required_cii = max(1.5, 8.0 - 0.00002 * dwt)
        elif vessel_type == "tanker":
            required_cii = max(1.5, 7.0 - 0.00002 * dwt)
        else:
            required_cii = 5.0

    ratio = attained_cii / max(0.01, required_cii)
    rating = _grade_cii(ratio, year=rating_year)
    cap_required = rating in ("D", "E")

    return _attestation({
        "tool": "check_imo_ccc_carbon_intensity",
        "vessel_imo": vessel_imo,
        "vessel_type": vessel_type,
        "dwt": dwt,
        "annual_distance_nm": annual_distance_nm,
        "annual_co2_tonnes": round(co2_tonnes, 1),
        "attained_cii": round(attained_cii, 3),
        "required_cii": round(required_cii, 3),
        "attained_over_required": round(ratio, 3),
        "rating_year": rating_year,
        "cii_rating": rating,
        "corrective_action_plan_required": cap_required,
        "regulator_ref": "IMO MEPC.336(76) + MARPOL Annex VI Reg 28",
        "advisory": (
            "RATING D/E — submit Corrective Action Plan with next annual SEEMP. "
            "Three consecutive D-ratings or one E triggers CAP review by flag state. "
            "Risk: charterer drop, financier covenants, public Poseidon Principles disclosure."
            if cap_required else "Rating compliant — keep SEEMP Part III current."
        ),
    })


@mcp.tool()
def check_eexi_efficiency(
    vessel_imo: str,
    vessel_type: str,
    attained_eexi: float,
    reference_eedi: float,
) -> dict:
    """Energy Efficiency Existing Ship Index (EEXI) compliance check.

    EEXI applies to existing ships >400 GT engaged in international voyages,
    enforced from first annual/intermediate/renewal IAPP survey on or after
    1 Jan 2023. Attained EEXI must be < Required EEXI = Reference * (1 - X).

    Args:
      attained_eexi: vessel's measured EEXI value
      reference_eedi: EEDI reference line value for the ship class
    """
    reduction = EEXI_REQUIRED_REDUCTION.get(vessel_type, 0.20)
    required_eexi = reference_eedi * (1.0 - reduction)
    compliant = attained_eexi <= required_eexi

    return _attestation({
        "tool": "check_eexi_efficiency",
        "vessel_imo": vessel_imo,
        "vessel_type": vessel_type,
        "attained_eexi": attained_eexi,
        "reference_eedi": reference_eedi,
        "required_reduction_pct": reduction * 100.0,
        "required_eexi": round(required_eexi, 4),
        "compliant": compliant,
        "regulator_ref": "IMO MEPC.333(76) + MARPOL Annex VI Reg 23/25",
        "advisory": (
            "EEXI NON-COMPLIANT. Mitigation: Engine Power Limitation (EPL), "
            "Shaft Power Limitation (SHaPoLi), or technical upgrade. Required "
            "before next IAPP survey or vessel certificate withdrawn."
            if not compliant else
            "EEXI compliant. EEXI Technical File must be on board."
        ),
    })


@mcp.tool()
def check_imdg_code_dangerous_goods(
    un_number: str,
    description: str = "",
    quantity_kg: float = 0.0,
    packing_group: str = "",
    on_deck_only: bool = False,
) -> dict:
    """IMDG Code check for sea-borne dangerous goods.

    Special focus on Class 9 lithium batteries — the cause of the Felicity
    Ace (2022) and likely Fremantle Highway (2023) total losses. UN3171
    (battery-powered vehicles) and UN3480/3481 (li-ion) require enhanced
    stowage, segregation, and fire-detection per IMDG Code amendments.

    Args:
      un_number: UN/NA number e.g. 'UN3480'
      packing_group: 'I' / 'II' / 'III' or '' if not applicable
      on_deck_only: True if stowed on weather deck only (li-ion best practice)
    """
    un = un_number.upper().replace(" ", "")
    lithium_match = LITHIUM_UN_NUMBERS.get(un, "")
    is_lithium = bool(lithium_match)

    # Default to Class 9 for lithium; otherwise unknown
    cls = "9" if is_lithium else "unknown"
    cls_label = IMDG_CLASSES.get(cls, "Look up class in IMDG Code volume 2")

    notes = []
    if is_lithium:
        notes.append("Class 9 lithium battery — IMDG Code SP188/SP230/SP310 applies")
        notes.append("Stowage Category A or B preferred; segregation away from heat sources")
        if not on_deck_only and quantity_kg > 100:
            notes.append("Quantity > 100 kg below-deck — review Felicity Ace 2022 lessons")
        notes.append("Fire-detection + CO2 system + thermal runaway protection required")
    if packing_group in ("I", "II"):
        notes.append(f"Packing Group {packing_group} — stricter segregation + reporting")

    return _attestation({
        "tool": "check_imdg_code_dangerous_goods",
        "un_number": un,
        "imdg_class": cls,
        "imdg_class_label": cls_label,
        "is_lithium_class9": is_lithium,
        "lithium_description": lithium_match,
        "description": description,
        "quantity_kg": quantity_kg,
        "packing_group": packing_group,
        "on_deck_only": on_deck_only,
        "stowage_notes": notes,
        "regulator_ref": "IMDG Code 2024 Edition (Amendment 41-22) + MARPOL Annex III",
        "advisory": (
            "Class 9 lithium-ion in container ship cargo — apply enhanced stowage. "
            "Document UN number + state of charge + thermal management in dangerous "
            "goods manifest. Refer to IMO MSC.1/Circ.1638 EV-related guidance."
            if is_lithium else
            "Apply IMDG segregation table + dangerous goods manifest per Ch 5.4."
        ),
    })


@mcp.tool()
def check_bunker_compliance(
    bdn_reference: str,
    sample_sulfur_pct: float,
    sample_nox_g_per_kwh: float = 0.0,
    sample_pm_mg_per_m3: float = 0.0,
    flashpoint_c: float = 60.0,
    density_kg_per_m3: float = 850.0,
    is_eca_route: bool = False,
) -> dict:
    """Bunker fuel quality check vs Bunker Delivery Note (BDN).

    MARPOL Annex VI Reg 18 requires retention of BDN + representative sample
    for 12 months minimum. Sulfur breach is the main detention trigger; PM
    + NOx are tracked for Tier III engines in NOx-ECAs (NECAs).

    Args:
      sample_sulfur_pct: tested sulfur as % m/m
      sample_nox_g_per_kwh: NOx emission (g/kWh) if Tier III tested
      flashpoint_c: ISO 8217 minimum 60 degC for safety
      is_eca_route: True if vessel will burn this fuel inside an ECA
    """
    cap = MARPOL_SULFUR_CAP_ECA if is_eca_route else MARPOL_SULFUR_CAP_GLOBAL
    sulfur_breach = sample_sulfur_pct > cap + 1e-9
    flashpoint_breach = flashpoint_c < 60.0
    nox_breach = sample_nox_g_per_kwh > 3.4  # Tier III NOx-ECA cap (g/kWh)

    issues = []
    if sulfur_breach:
        issues.append(
            f"Sulfur {sample_sulfur_pct}% > cap {cap}% — fuel must NOT be burned"
        )
    if flashpoint_breach:
        issues.append(
            f"Flashpoint {flashpoint_c} degC < 60 degC ISO 8217 — safety risk, "
            "fuel non-acceptance recommended"
        )
    if nox_breach and is_eca_route:
        issues.append(f"NOx {sample_nox_g_per_kwh} g/kWh > 3.4 NECA cap (Tier III)")

    return _attestation({
        "tool": "check_bunker_compliance",
        "bdn_reference": bdn_reference,
        "sample_sulfur_pct": sample_sulfur_pct,
        "sample_nox_g_per_kwh": sample_nox_g_per_kwh,
        "sample_pm_mg_per_m3": sample_pm_mg_per_m3,
        "flashpoint_c": flashpoint_c,
        "density_kg_per_m3": density_kg_per_m3,
        "is_eca_route": is_eca_route,
        "applicable_sulfur_cap_pct": cap,
        "sulfur_breach": sulfur_breach,
        "flashpoint_breach": flashpoint_breach,
        "nox_breach": nox_breach,
        "compliant": not issues,
        "issues": issues,
        "regulator_ref": "MARPOL Annex VI Reg 14 + Reg 18 + ISO 8217:2017",
        "advisory": (
            "Notify the supplier in writing + Flag Administration + next Port "
            "State within 24h of bunkering per Reg 18.10.1. Retain MARPOL sample "
            "for 12 months minimum."
            if issues else
            "Compliant against tested parameters. Retain BDN + sample 12 months."
        ),
    })


@mcp.tool()
def check_ballast_water_management(
    vessel_imo: str,
    bwms_installed: bool = False,
    bwms_imo_type_approved: bool = False,
    d2_standard_met: bool = False,
    last_iopp_survey_date: str = "",
    bwm_plan_on_board: bool = False,
    bwm_record_book_current: bool = False,
) -> dict:
    """IMO Ballast Water Management Convention compliance check.

    BWM Convention entered into force 8 Sep 2017. All ships now subject to
    D-2 performance standard (rollout completed by 8 Sep 2024). Requires:
      - approved BWMS (Ballast Water Management System)
      - IMO type approval certificate
      - Ballast Water Management Plan on board
      - Ballast Water Record Book (updated each ballast operation)
      - International Ballast Water Management Certificate (IBWMC)
    """
    today = date.today()
    try:
        survey = date.fromisoformat(last_iopp_survey_date)
        days_since_survey = (today - survey).days
    except Exception:
        survey = None
        days_since_survey = -1

    issues = []
    if not bwms_installed:
        issues.append("No BWMS installed — required for D-2 standard")
    if bwms_installed and not bwms_imo_type_approved:
        issues.append("BWMS not IMO type approved — re-survey required")
    if not d2_standard_met:
        issues.append("D-2 performance standard NOT met")
    if not bwm_plan_on_board:
        issues.append("Ballast Water Management Plan missing on board")
    if not bwm_record_book_current:
        issues.append("Ballast Water Record Book not current — PSC red flag")
    if days_since_survey > 0 and days_since_survey > 365 * 5:
        issues.append("IOPP survey overdue (>5 years)")

    return _attestation({
        "tool": "check_ballast_water_management",
        "vessel_imo": vessel_imo,
        "bwms_installed": bwms_installed,
        "bwms_imo_type_approved": bwms_imo_type_approved,
        "d2_standard_met": d2_standard_met,
        "last_iopp_survey_date": last_iopp_survey_date,
        "days_since_iopp_survey": days_since_survey,
        "bwm_plan_on_board": bwm_plan_on_board,
        "bwm_record_book_current": bwm_record_book_current,
        "issues": issues,
        "compliant": not issues,
        "regulator_ref": "IMO BWM Convention 2004 (in force 2017) + D-2 standard",
        "advisory": (
            "BWM NON-COMPLIANT — high PSC detention risk. Schedule BWMS retrofit + "
            "type approval + IBWMC issuance. Avoid US, EU, Australia until cleared."
            if issues else
            "BWM compliant. Maintain Record Book per operation + IBWMC on board."
        ),
    })


@mcp.tool()
def prepare_psc_inspection_pack(
    vessel_imo: str,
    flag_state: str,
    next_port: str,
    psc_region: str,
    last_inspection_date: str = "",
    last_inspection_deficiencies: int = 0,
    last_detention: bool = False,
) -> dict:
    """Port State Control inspection prep — Paris/Tokyo/USCG MoU ready-pack.

    PSC targets ships using a risk profile: Standard / High / Low Risk Ship
    (Paris MoU NIR + Tokyo MoU NIR). Vessels with recent detentions or D-rated
    flag states are priority. This tool returns the documentation pack the
    Master should have ready before the boarding party arrives.

    Args:
      psc_region: key from PSC_MOUS, e.g. 'paris' / 'tokyo' / 'uscg'
    """
    today = date.today()
    mou = PSC_MOUS.get(psc_region, ("Unknown MoU", "", 0.05))
    mou_name, mou_scope, mou_rate = mou

    try:
        last = date.fromisoformat(last_inspection_date)
        days_since = (today - last).days
    except Exception:
        last = None
        days_since = -1

    # Risk profile heuristic
    if last_detention:
        risk = "HIGH"
    elif last_inspection_deficiencies >= 5 or (days_since > 0 and days_since > 36 * 30):
        risk = "STANDARD"
    elif last_inspection_deficiencies == 0 and 0 < days_since < 18 * 30:
        risk = "LOW"
    else:
        risk = "STANDARD"

    docs_required = [
        "International Tonnage Certificate",
        "International Load Line Certificate",
        "Minimum Safe Manning Document",
        "International Ship Security Certificate (ISSC)",
        "Continuous Synopsis Record",
        "IOPP Certificate (oil pollution)",
        "IAPP Certificate (air pollution)",
        "IEE Certificate (Energy Efficiency)",
        "IBWMC (Ballast Water Management)",
        "International Sewage Pollution Prevention Certificate",
        "MARPOL Oil Record Book Part I (Machinery)",
        "MARPOL Oil Record Book Part II (Cargo for tankers)",
        "Garbage Record Book + Garbage Management Plan",
        "Ballast Water Record Book",
        "Bunker Delivery Notes (3 yrs) + MARPOL fuel sample",
        "SEEMP Part I/II/III + Ship Fuel Oil Consumption Data",
        "EU MRV verification + EU ETS Monitoring Plan (if EU calls)",
        "Cargo Securing Manual (RoRo + container)",
        "Document of Compliance + Safety Management Certificate (ISM)",
        "STCW certificates for officers + crew (current + endorsements)",
    ]

    return _attestation({
        "tool": "prepare_psc_inspection_pack",
        "vessel_imo": vessel_imo,
        "flag_state": flag_state,
        "next_port": next_port,
        "psc_region": psc_region,
        "psc_mou_name": mou_name,
        "psc_mou_scope": mou_scope,
        "psc_regional_detention_rate": mou_rate,
        "last_inspection_date": last_inspection_date,
        "days_since_last_inspection": days_since,
        "last_inspection_deficiencies": last_inspection_deficiencies,
        "last_detention": last_detention,
        "risk_profile": risk,
        "documents_required": docs_required,
        "documents_count": len(docs_required),
        "regulator_ref": "Paris MoU NIR + Tokyo MoU NIR + IMO Res A.1138(31)",
        "advisory": (
            "HIGH-RISK profile — expect detailed inspection + likely Initial + "
            "More Detailed PSC. Brief Master + Chief Engineer + Chief Officer; "
            "rehearse fire + abandon drill response; check expired certificates "
            "FIRST."
            if risk == "HIGH" else
            f"{risk}-RISK — keep documents above ready at gangway. Typical "
            f"detention rate in {mou_name} = {mou_rate*100:.1f}% per inspection."
        ),
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
