"""Smoke tests for meok-imo-marpol-marine-mcp."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import (
    check_marpol_annex_compliance, check_eu_ets_maritime,
    check_imo_ccc_carbon_intensity, check_eexi_efficiency,
    check_imdg_code_dangerous_goods, check_bunker_compliance,
    check_ballast_water_management, prepare_psc_inspection_pack,
    ECA_ZONES, EU_ETS_PHASE_IN, EU_ETS_SCOPE, IMDG_CLASSES,
    LITHIUM_UN_NUMBERS, PSC_MOUS, MARPOL_SULFUR_CAP_GLOBAL,
    MARPOL_SULFUR_CAP_ECA, _sign, _grade_cii,
)


def _call(t, **kw):
    fn = t.fn if hasattr(t, "fn") else t
    return fn(**kw)


# ----------------------------------------------------------------------
# MARPOL Annex VI
# ----------------------------------------------------------------------

def test_marpol_global_compliant_vlsfo():
    r = _call(check_marpol_annex_compliance,
              vessel_imo="9876543", fuel_type="vlsfo",
              fuel_sulfur_pct=0.45, route_zone="global")
    assert r["compliant"] is True
    assert r["applicable_cap_pct"] == MARPOL_SULFUR_CAP_GLOBAL


def test_marpol_eca_breach_when_above_0p1():
    r = _call(check_marpol_annex_compliance,
              vessel_imo="9876543", fuel_type="vlsfo",
              fuel_sulfur_pct=0.45, route_zone="north_sea")
    assert r["is_eca"] is True
    assert r["compliant"] is False
    assert any("BREACH" in i for i in r["issues"])


def test_marpol_scrubber_credit_allows_hfo():
    r = _call(check_marpol_annex_compliance,
              vessel_imo="9876543", fuel_type="hfo",
              fuel_sulfur_pct=3.5, route_zone="global",
              has_scrubber=True)
    # 3.5% * 0.05 = 0.175% effective — under 0.5% global cap
    assert r["compliant"] is True
    assert r["scrubber_credit"] is True


def test_marpol_hfo_no_scrubber_flagged():
    r = _call(check_marpol_annex_compliance,
              vessel_imo="9876543", fuel_type="hfo",
              fuel_sulfur_pct=3.0, route_zone="global",
              has_scrubber=False)
    assert r["compliant"] is False
    assert any("HFO" in i for i in r["issues"])


# ----------------------------------------------------------------------
# EU ETS Maritime
# ----------------------------------------------------------------------

def test_eu_ets_intra_eu_2026_full_phase_in():
    r = _call(check_eu_ets_maritime,
              vessel_imo="9876543", voyage_type="intra_eu",
              co2_tonnes=1000, voyage_year=2026,
              ets_price_eur_per_tco2=80.0)
    # 1000 * 1.0 scope * 1.0 phase * 80 = 80,000
    assert r["chargeable_tco2"] == 1000.0
    assert r["ets_cost_eur"] == 80000.0
    assert r["covered_by_eu_ets"] is True


def test_eu_ets_third_to_eu_half_scope():
    r = _call(check_eu_ets_maritime,
              vessel_imo="9876543", voyage_type="third_to_eu",
              co2_tonnes=1000, voyage_year=2026,
              ets_price_eur_per_tco2=80.0)
    assert r["scope_factor"] == 0.5
    assert r["chargeable_tco2"] == 500.0


def test_eu_ets_non_eu_voyage_not_covered():
    r = _call(check_eu_ets_maritime,
              vessel_imo="9876543", voyage_type="non_eu",
              co2_tonnes=2000, voyage_year=2026)
    assert r["covered_by_eu_ets"] is False
    assert r["ets_cost_eur"] == 0.0


def test_eu_ets_2024_only_40_percent_phase_in():
    r = _call(check_eu_ets_maritime,
              vessel_imo="9876543", voyage_type="intra_eu",
              co2_tonnes=1000, voyage_year=2024,
              ets_price_eur_per_tco2=80.0)
    assert r["phase_in_factor"] == 0.40
    assert r["chargeable_tco2"] == 400.0


# ----------------------------------------------------------------------
# CII
# ----------------------------------------------------------------------

def test_cii_rating_returns_letter():
    r = _call(check_imo_ccc_carbon_intensity,
              vessel_imo="9876543", vessel_type="container",
              dwt=80000, annual_distance_nm=120000,
              annual_fuel_tonnes=20000)
    assert r["cii_rating"] in ("A", "B", "C", "D", "E")
    assert "attained_cii" in r


def test_cii_e_rating_triggers_cap():
    # Use explicit required_cii to force E rating
    r = _call(check_imo_ccc_carbon_intensity,
              vessel_imo="9876543", vessel_type="bulk_carrier",
              dwt=50000, annual_distance_nm=80000,
              annual_fuel_tonnes=15000, required_cii=1.0)
    assert r["cii_rating"] in ("D", "E")
    assert r["corrective_action_plan_required"] is True


def test_grade_cii_helper_boundaries():
    assert _grade_cii(0.5) == "A"
    assert _grade_cii(0.90) == "B"
    assert _grade_cii(1.0) == "C"
    assert _grade_cii(1.10) == "D"
    assert _grade_cii(1.50) == "E"


# ----------------------------------------------------------------------
# EEXI
# ----------------------------------------------------------------------

def test_eexi_compliant_when_below_required():
    r = _call(check_eexi_efficiency,
              vessel_imo="9876543", vessel_type="bulk_carrier",
              attained_eexi=6.0, reference_eedi=10.0)
    # required = 10 * (1 - 0.20) = 8.0; attained 6.0 < 8.0 -> compliant
    assert r["compliant"] is True
    assert abs(r["required_eexi"] - 8.0) < 0.0001


def test_eexi_non_compliant_when_above_required():
    r = _call(check_eexi_efficiency,
              vessel_imo="9876543", vessel_type="container",
              attained_eexi=8.0, reference_eedi=10.0)
    # required = 10 * (1 - 0.30) = 7.0; attained 8.0 > 7.0 -> NON-compliant
    assert r["compliant"] is False
    assert "EPL" in r["advisory"] or "Engine Power" in r["advisory"]


# ----------------------------------------------------------------------
# IMDG
# ----------------------------------------------------------------------

def test_imdg_un3480_recognised_as_lithium_class9():
    r = _call(check_imdg_code_dangerous_goods, un_number="UN3480",
              quantity_kg=500, on_deck_only=False)
    assert r["is_lithium_class9"] is True
    assert r["imdg_class"] == "9"
    assert any("Felicity" in n for n in r["stowage_notes"])


def test_imdg_un3171_ev_battery_vehicle():
    r = _call(check_imdg_code_dangerous_goods, un_number="UN3171",
              quantity_kg=2000, on_deck_only=True)
    assert r["is_lithium_class9"] is True
    assert "vehicle" in r["lithium_description"].lower()


def test_imdg_packing_group_i_flagged():
    r = _call(check_imdg_code_dangerous_goods, un_number="UN3480",
              quantity_kg=10, packing_group="I")
    assert any("Packing Group I" in n for n in r["stowage_notes"])


# ----------------------------------------------------------------------
# Bunker compliance
# ----------------------------------------------------------------------

def test_bunker_sulfur_compliant_outside_eca():
    r = _call(check_bunker_compliance,
              bdn_reference="BDN-2026-001",
              sample_sulfur_pct=0.45,
              flashpoint_c=65.0, is_eca_route=False)
    assert r["compliant"] is True


def test_bunker_sulfur_breach_in_eca():
    r = _call(check_bunker_compliance,
              bdn_reference="BDN-2026-002",
              sample_sulfur_pct=0.45,
              flashpoint_c=65.0, is_eca_route=True)
    assert r["sulfur_breach"] is True
    assert r["compliant"] is False


def test_bunker_low_flashpoint_flagged():
    r = _call(check_bunker_compliance,
              bdn_reference="BDN-2026-003",
              sample_sulfur_pct=0.05,
              flashpoint_c=55.0, is_eca_route=False)
    assert r["flashpoint_breach"] is True
    assert any("Flashpoint" in i for i in r["issues"])


# ----------------------------------------------------------------------
# Ballast Water
# ----------------------------------------------------------------------

def test_bwm_no_bwms_installed_non_compliant():
    r = _call(check_ballast_water_management,
              vessel_imo="9876543", bwms_installed=False)
    assert r["compliant"] is False
    assert any("BWMS" in i for i in r["issues"])


def test_bwm_full_compliance_ok():
    r = _call(check_ballast_water_management,
              vessel_imo="9876543",
              bwms_installed=True, bwms_imo_type_approved=True,
              d2_standard_met=True,
              last_iopp_survey_date="2025-01-15",
              bwm_plan_on_board=True,
              bwm_record_book_current=True)
    assert r["compliant"] is True
    assert r["issues"] == []


# ----------------------------------------------------------------------
# PSC inspection prep
# ----------------------------------------------------------------------

def test_psc_high_risk_when_last_detention():
    r = _call(prepare_psc_inspection_pack,
              vessel_imo="9876543", flag_state="PA",
              next_port="Rotterdam", psc_region="paris",
              last_detention=True)
    assert r["risk_profile"] == "HIGH"
    assert "HIGH-RISK" in r["advisory"]


def test_psc_pack_lists_documents():
    r = _call(prepare_psc_inspection_pack,
              vessel_imo="9876543", flag_state="UK",
              next_port="London Gateway", psc_region="paris")
    assert r["documents_count"] >= 18
    assert any("IOPP" in d for d in r["documents_required"])
    assert any("IBWMC" in d for d in r["documents_required"])


def test_psc_returns_mou_name():
    r = _call(prepare_psc_inspection_pack,
              vessel_imo="9876543", flag_state="JP",
              next_port="Yokohama", psc_region="tokyo")
    assert r["psc_mou_name"] == "Tokyo MoU"


# ----------------------------------------------------------------------
# Tables + signing
# ----------------------------------------------------------------------

def test_eca_zones_includes_med_2025():
    assert "mediterranean" in ECA_ZONES


def test_eu_ets_2026_full_phase_in():
    assert EU_ETS_PHASE_IN[2026] == 1.00


def test_imdg_class9_in_table():
    assert "9" in IMDG_CLASSES
    assert "lithium" in IMDG_CLASSES["9"].lower()


def test_psc_mous_includes_paris_and_tokyo():
    assert "paris" in PSC_MOUS
    assert "tokyo" in PSC_MOUS


def test_attestation_signed_when_key_set(monkeypatch):
    monkeypatch.setenv("MEOK_HMAC_SECRET", "test-secret")
    import server
    server._HMAC_SECRET = "test-secret"
    payload = {"foo": "bar"}
    sig = server._sign(payload)
    assert sig != "unsigned-no-key-configured"
    assert len(sig) == 64  # sha256 hex


def test_attestation_unsigned_when_no_key():
    import server
    server._HMAC_SECRET = ""
    payload = {"foo": "bar"}
    sig = server._sign(payload)
    assert sig == "unsigned-no-key-configured"


def test_attestation_issuer_name():
    r = _call(check_marpol_annex_compliance,
              vessel_imo="9876543", fuel_type="mgo",
              fuel_sulfur_pct=0.05, route_zone="global")
    assert r["issuer"] == "meok-imo-marpol-marine-mcp"
    assert r["version"] == "1.0.0"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
