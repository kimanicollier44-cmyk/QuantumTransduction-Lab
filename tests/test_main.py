"""Tests for QuantumTransduction-Lab: conversion, noise, scan, gates."""
import math

import pytest

import main as m


# ---- cooperativity conversion
def test_eta_int_zero_and_unity_point():
    assert m.eta_internal(0.0, 5.0) == 0.0
    assert m.eta_internal(1.0, 1.0) == 4.0 / 9.0


def test_eta_int_symmetric():
    assert m.eta_internal(3.0, 7.0) == m.eta_internal(7.0, 3.0)


def test_eta_int_matched_values():
    assert m.eta_internal(10.0, 10.0) == pytest.approx(400.0 / 441.0, abs=1e-15)
    assert m.eta_internal(100.0, 100.0) == pytest.approx(
        40000.0 / 40401.0, abs=1e-15)
    assert m.eta_internal(100.0, 100.0) > 0.99


def test_eta_int_matched_monotone_below_unity():
    assert m.eta_internal(1.0, 1.0) < m.eta_internal(10.0, 10.0) \
        < m.eta_internal(100.0, 100.0) < 1.0


def test_eta_int_mismatch_cliff():
    assert m.eta_internal(100.0, 1.0) < 0.04
    assert m.eta_internal(100.0, 100.0) > m.eta_internal(150.0, 50.0) \
        > m.eta_internal(199.0, 1.0)


def test_eta_int_rejects_negative():
    with pytest.raises(ValueError):
        m.eta_internal(-1.0, 5.0)


def test_eta_total_extraction():
    assert m.eta_total(10.0, 10.0) == pytest.approx(0.7346938775510204, abs=1e-12)
    assert m.eta_total(10.0, 10.0, 1.0, 1.0) == m.eta_internal(10.0, 10.0)
    assert m.eta_total(3.0, 7.0) <= m.eta_internal(3.0, 7.0)
    with pytest.raises(ValueError):
        m.eta_total(1.0, 1.0, 1.5, 0.9)


# ---- thermal noise + added noise
def test_nth_values():
    assert m.thermal_occupation(m.MW_FREQ_HZ, 4.0) == pytest.approx(
        16.17429421036441, abs=1e-9)
    assert m.thermal_occupation(m.MW_FREQ_HZ, 0.1) == pytest.approx(
        0.09981030749537737, abs=1e-12)
    assert 0.0 < m.thermal_occupation(m.MW_FREQ_HZ, 0.01) < 1e-9


def test_nth_monotone_and_limits():
    assert m.thermal_occupation(m.MW_FREQ_HZ, 4.0) \
        > m.thermal_occupation(m.MW_FREQ_HZ, 0.1) \
        > m.thermal_occupation(m.MW_FREQ_HZ, 0.01)
    assert m.thermal_occupation(m.MW_FREQ_HZ, 0.001) < 1e-100
    high_t = m.K_B * 4.0 / (m.H_PLANCK * m.MW_FREQ_HZ) - 0.5
    assert abs(m.thermal_occupation(m.MW_FREQ_HZ, 4.0) - high_t) < 0.01


def test_nth_rejects_bad_inputs():
    with pytest.raises(ValueError):
        m.thermal_occupation(0.0, 1.0)
    with pytest.raises(ValueError):
        m.thermal_occupation(m.MW_FREQ_HZ, 0.0)


def test_harmonic_cooperativity():
    assert m.harmonic_cooperativity(10.0, 10.0) == 10.0
    assert m.harmonic_cooperativity(100.0, 1.0) == pytest.approx(
        200.0 / 101.0, abs=1e-12)
    assert m.harmonic_cooperativity(0.0, 5.0) == 0.0


def test_added_noise_and_quantum_enabled():
    assert m.added_noise(10.0, 10.0, 0.1) < 0.01
    assert m.added_noise(10.0, 10.0, 4.0) > 1.0
    assert m.operating_point(10.0, 10.0, 0.1)["quantum_enabled"] is True
    assert m.operating_point(10.0, 10.0, 4.0)["quantum_enabled"] is False
    assert m.operating_point(1.0, 1.0, 0.1)["quantum_enabled"] is False


# ---- bandwidth + extraction tradeoff
def test_conversion_bandwidth():
    assert m.conversion_bandwidth_hz() == pytest.approx(20.0e6 / 3.0, abs=1.0)
    assert m.time_bandwidth_product() == pytest.approx(1.0, abs=1e-12)


def test_extraction_tradeoff():
    assert m.extraction_point(0.99)["eta_total"] \
        > m.extraction_point(0.9)["eta_total"] \
        > m.extraction_point(0.5)["eta_total"]
    assert m.extraction_point(0.999)["eta_total"] \
        < m.extraction_point(0.99)["eta_total"]
    assert m.extraction_point(0.999)["bandwidth_hz"] \
        > m.extraction_point(0.99)["bandwidth_hz"] \
        > m.extraction_point(0.9)["bandwidth_hz"]
    with pytest.raises(ValueError):
        m.extraction_point(1.0)


# ---- operating-point scan
def test_scan_best_point():
    scan = m.scan_operating_points()
    assert scan["best"]["c1"] == 100.0 and scan["best"]["c2"] == 100.0
    assert scan["best"]["eta_internal"] == pytest.approx(
        40000.0 / 40401.0, abs=1e-15)
    assert scan["best"]["eta_total"] == pytest.approx(
        0.8019603475161506, abs=1e-12)


def test_scan_cap_and_contrast():
    scan = m.scan_operating_points()
    assert scan["points_evaluated"] == 81
    assert scan["best"]["c1"] + scan["best"]["c2"] <= scan["cap_sum"]
    con = scan["fixed_sum_contrast"]
    assert con["matched_100_100"]["eta_internal"] \
        > con["lopsided_150_50"]["eta_internal"] \
        > con["extreme_199_1"]["eta_internal"]
    assert m.scan_operating_points() == scan


# ---- classifier
def test_classifier_report():
    rep = m.classifier_report()
    assert rep["matched_C10_100mK"] == "quantum-enabled"
    assert rep["matched_C10_4K"] == "efficient-but-noisy"
    assert rep["matched_C1_100mK"] == "quiet-but-lossy"
    assert rep["weak_C0.1_4K"] == "unusable"


def test_classifier_matches_policy():
    for p in m._scenario_points().values():
        assert m.classify_operating(p["eta_total"], p["n_add"]) \
            == m.verdict_policy(p["eta_total"], p["n_add"])


def test_policy_thresholds():
    assert m.verdict_policy(0.5, 0.5) == "quantum-enabled"
    assert m.verdict_policy(0.5, 1.0) == "efficient-but-noisy"
    assert m.verdict_policy(0.49, 0.5) == "quiet-but-lossy"
    assert m.verdict_policy(0.49, 1.0) == "unusable"


# ---- gates + seats
def test_hold_gates_14():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())


def test_gate_specifics():
    assert m.gate("hardware_efficiency_claim") == "HOLD"
    assert m.gate("quantum_network_deployment") == "HOLD"
    assert m.gate("measurement_fabrication") == "HOLD"
    assert m.gate("qkd_security_claim") == "HOLD"
    assert m.gate("run_simulation") == "PROCEED"


def test_seats_cannot_override():
    b = m.brains_report()
    assert b["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert b["decider"]["can_override_hold"] is False
    assert b["advisor"]["can_override_hold"] is False
    assert b["flow"]["rendered"] is False and b["flow"]["live"] == 0


def test_checks_all_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_hold_demo_exit_code():
    assert m.main(["hold-demo", "hardware_efficiency_claim"]) == 2
    assert m.main(["hold-demo", "run_simulation"]) == 0
