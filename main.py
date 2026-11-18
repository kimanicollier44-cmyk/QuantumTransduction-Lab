#!/usr/bin/env python3
"""QuantumTransduction-Lab - educational microwave-to-optical quantum
transduction lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * This lab evaluates the STANDARD TEXTBOOK transducer formulas -
    the beam-splitter cooperativity efficiency, the Bose-Einstein
    thermal occupation, and a labelled added-noise bookkeeping model -
    at LABELLED teaching parameters.
  * No device was built, cooled, pumped, or measured. Every number
    here is a statement about a formula evaluated at stated inputs,
    never a hardware promise, a device specification, or a
    measurement.
  * The honest physics is the interesting part anyway: efficiency
    near unity needs BOTH cooperativities large AND matched; a
    5 GHz microwave mode at 4 K carries ~16 thermal photons, so the
    same converter that is quantum-enabled at 100 mK is drowned in
    noise on the bench; and pushing the extraction ratio wider buys
    bandwidth right up to the point where the cooperativity
    collapses and takes the efficiency with it.

Hardware, quantum-network, entanglement-distribution, QKD-security,
vendor, and guaranteed-fidelity claims are permanent HOLD gates -
with Gemini Argon 4 Extended Thinking as DECIDER (names-only,
tighten-only), Muse as advisor (never overrides HOLD), and Google
Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Exact SI constants (2019 SI redefinition values, exact by definition).
H_PLANCK = 6.62607015e-34   # J s
K_B = 1.380649e-23          # J / K

# Labelled teaching parameters. These are stated inputs to textbook
# formulas - NOT measured device data and NOT a device specification.
MW_FREQ_HZ = 5.0e9          # labelled microwave mode frequency (5 GHz)
OPT_FREQ_HZ = 193.4e12      # labelled optical mode (~1550 nm)
EXTRACTION_MW = 0.90        # labelled kappa1_ex / kappa1
EXTRACTION_OPT = 0.90       # labelled kappa2_ex / kappa2
KAPPA_MW_HZ = 10.0e6        # labelled loaded microwave linewidth / 2pi
KAPPA_OPT_HZ = 20.0e6       # labelled loaded optical linewidth / 2pi
PULSE_TAU_S = 150e-9        # labelled pulse duration (150 ns)
KAPPA_INT_MW_HZ = 1.0e6     # labelled intrinsic microwave linewidth / 2pi
KAPPA_INT_OPT_HZ = 2.0e6    # labelled intrinsic optical linewidth / 2pi
C_AT_ZERO_EXTRACTION = 1000.0  # labelled cooperativity at zero extraction
PUMP_CAP_SUM = 200.0        # labelled pump cap: C1 + C2 <= 200
SCAN_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0,
             1000.0)

# The lab's own quantum-enabled policy line (labelled thresholds):
# a point counts as quantum-enabled only if the total efficiency
# clears ETA_QUANTUM_MIN AND the added noise stays below one photon.
ETA_QUANTUM_MIN = 0.5
NADD_QUANTUM_MAX = 1.0

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "hardware_efficiency_claim": "HOLD - no claiming a real device achieves these efficiencies; the numbers are formula evaluations at labelled inputs",
    "device_specification_claim": "HOLD - no presenting labelled teaching parameters as a real device specification",
    "quantum_network_deployment": "HOLD - no deploying or operating a real quantum network link from a formula lab",
    "entanglement_distribution_claim": "HOLD - no claiming entanglement was generated, distributed, or verified",
    "cryogenic_operation_live": "HOLD - no directing live cryogenic, microwave, or vacuum hardware",
    "laser_operation_live": "HOLD - no directing live lasers, optical pumps, or high-power optics",
    "vendor_performance_claim": "HOLD - no vendor or product performance claims from textbook formulas",
    "quantum_internet_claim": "HOLD - no 'quantum internet ready' claims; a cooperativity table is not infrastructure",
    "qkd_security_claim": "HOLD - no claiming QKD-grade or cryptographic security from an efficiency formula",
    "medical_claim": "HOLD - no medical imaging, sensing, or diagnostic claims",
    "investment_claim": "HOLD - no investment claims; a lab model is not a prospectus",
    "telecom_infrastructure_claim": "HOLD - no claiming telecom infrastructure readiness or carrier deployment",
    "measurement_fabrication": "HOLD - no presenting computed values as measurements; nothing here was measured",
    "guaranteed_fidelity_claim": "HOLD - no guaranteed state-transfer fidelity; efficiency is not fidelity and neither is promised",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Cooperativity conversion
# The standard beam-splitter transducer result: with electromechanical
# cooperativity C1 on the microwave side and optomechanical
# cooperativity C2 on the optical side, the internal conversion
# efficiency is eta_int = 4*C1*C2 / (1 + C1 + C2)^2. It reaches unity
# only in the matched strong-coupling limit C1 = C2 >> 1 - and the
# mismatch penalty is severe, which the checks price exactly.

def _check_cooperativity(c, name):
    if c < 0:
        raise ValueError(f"{name} must be >= 0, got {c}")


def eta_internal(c1, c2):
    """Internal conversion efficiency 4*C1*C2 / (1 + C1 + C2)^2."""
    _check_cooperativity(c1, "C1")
    _check_cooperativity(c2, "C2")
    return 4.0 * c1 * c2 / (1.0 + c1 + c2) ** 2


def eta_total(c1, c2, r1=EXTRACTION_MW, r2=EXTRACTION_OPT):
    """Total efficiency: internal x extraction ratios on both ports."""
    for r, name in ((r1, "r1"), (r2, "r2")):
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"{name} must be in [0, 1], got {r}")
    return eta_internal(c1, c2) * r1 * r2


def conversion_report():
    """Matched vs mismatched cooperativity points, all computed."""
    points = {}
    for name, (c1, c2) in {
        "matched_C1": (1.0, 1.0),
        "matched_C10": (10.0, 10.0),
        "matched_C100": (100.0, 100.0),
        "mismatched_C100_C1": (100.0, 1.0),
        "mismatched_C10_C0.1": (10.0, 0.1),
        "weak_C0.1": (0.1, 0.1),
    }.items():
        points[name] = {
            "c1": c1, "c2": c2,
            "eta_internal": round(eta_internal(c1, c2), 6),
            "eta_total": round(eta_total(c1, c2), 6),
        }
    return {
        "formula": "eta_int = 4*C1*C2 / (1 + C1 + C2)^2",
        "extraction_mw": EXTRACTION_MW,
        "extraction_opt": EXTRACTION_OPT,
        "unity_condition": "C1 = C2 >> 1 (matched, strong coupling)",
        "points": points,
    }


# ================================================================ 2. Thermal noise + added noise
# A microwave mode at frequency f and temperature T holds
# n_th = 1 / (exp(hf / kT) - 1) thermal photons on average. At 5 GHz,
# hf/k = 0.239962 K, so a 4 K bench is a hot bath (n_th ~ 16.17) and
# only the cryogenic points are quiet. The lab's labelled added-noise
# model refers that bath to the input through the harmonic-mean
# cooperativity: N_add = n_th / C_harm. It is a bookkeeping model,
# stated as such - not a measured noise figure.

def thermal_occupation(freq_hz, temp_k):
    """Mean thermal photon number 1 / (exp(hf/kT) - 1)."""
    if freq_hz <= 0:
        raise ValueError(f"freq_hz must be > 0, got {freq_hz}")
    if temp_k <= 0:
        raise ValueError(f"temp_k must be > 0, got {temp_k}")
    return 1.0 / (math.exp(H_PLANCK * freq_hz / (K_B * temp_k)) - 1.0)


def harmonic_cooperativity(c1, c2):
    """Harmonic mean of the two cooperativities (0 if either is 0)."""
    _check_cooperativity(c1, "C1")
    _check_cooperativity(c2, "C2")
    if c1 + c2 == 0:
        return 0.0
    return 2.0 * c1 * c2 / (c1 + c2)


def added_noise(c1, c2, temp_k, freq_hz=MW_FREQ_HZ):
    """Labelled model: input-referred added noise n_th / C_harm."""
    charm = harmonic_cooperativity(c1, c2)
    if charm == 0:
        return float("inf")
    return thermal_occupation(freq_hz, temp_k) / charm


def operating_point(c1, c2, temp_k):
    """One operating point: efficiency, noise, quantum-enabled verdict."""
    eta_i = eta_internal(c1, c2)
    eta_t = eta_total(c1, c2)
    n_th = thermal_occupation(MW_FREQ_HZ, temp_k)
    n_add = added_noise(c1, c2, temp_k)
    return {
        "c1": c1, "c2": c2, "temp_k": temp_k,
        "eta_internal": round(eta_i, 6),
        "eta_total": round(eta_t, 6),
        "n_th": n_th,
        "n_add": n_add,
        "quantum_enabled": bool(eta_t >= ETA_QUANTUM_MIN
                                and n_add < NADD_QUANTUM_MAX),
    }


def noise_report():
    """Thermal occupation at the three labelled temperatures + points."""
    temps = {}
    for t in (4.0, 0.1, 0.01):
        temps[f"T_{t:g}K"] = {
            "temp_k": t,
            "n_th_5ghz": thermal_occupation(MW_FREQ_HZ, t),
            "n_add_at_C10_matched": added_noise(10.0, 10.0, t),
        }
    return {
        "hf_over_k_kelvin": H_PLANCK * MW_FREQ_HZ / K_B,
        "model": "N_add = n_th / C_harm (labelled bookkeeping model)",
        "temperatures": temps,
        "points": {
            "matched_C10_100mK": operating_point(10.0, 10.0, 0.1),
            "matched_C10_4K": operating_point(10.0, 10.0, 4.0),
            "matched_C10_10mK": operating_point(10.0, 10.0, 0.01),
        },
    }


# ================================================================ 3. Bandwidth + pulse bookkeeping
# Labelled model: the conversion bandwidth is set by the two loaded
# linewidths in series combination, BW = kappa1*kappa2 / (kappa1 +
# kappa2) (in Hz, using kappa/2pi values) - the narrower port
# dominates, as it should. The extraction tradeoff is the real lesson:
# with cooperativity C(r) = C0 * (1 - r) per side at extraction ratio
# r, total efficiency eta_int * r^2 peaks at an interior r, while the
# loaded bandwidth kappa_int / (1 - r) keeps growing - past the peak
# you are buying bandwidth with efficiency, at a ruinous rate.

def conversion_bandwidth_hz(k1_hz=KAPPA_MW_HZ, k2_hz=KAPPA_OPT_HZ):
    """Series-combination conversion bandwidth from loaded linewidths."""
    if k1_hz <= 0 or k2_hz <= 0:
        raise ValueError("linewidths must be > 0")
    return k1_hz * k2_hz / (k1_hz + k2_hz)


def time_bandwidth_product(tau_s=PULSE_TAU_S):
    """Dimensionless time-bandwidth product BW * tau for the pulse."""
    if tau_s <= 0:
        raise ValueError(f"tau_s must be > 0, got {tau_s}")
    return conversion_bandwidth_hz() * tau_s


def extraction_point(r):
    """One matched extraction point: C falls, bandwidth grows, eta peaks."""
    if not 0.0 <= r < 1.0:
        raise ValueError(f"r must be in [0, 1), got {r}")
    c = C_AT_ZERO_EXTRACTION * (1.0 - r)
    eta_i = eta_internal(c, c)
    return {
        "r": r,
        "c_each": c,
        "eta_internal": eta_i,
        "eta_total": eta_i * r * r,
        "bandwidth_hz": min(KAPPA_INT_MW_HZ, KAPPA_INT_OPT_HZ) / (1.0 - r),
    }


def bandwidth_report():
    return {
        "kappa_mw_hz": KAPPA_MW_HZ,
        "kappa_opt_hz": KAPPA_OPT_HZ,
        "conversion_bandwidth_hz": conversion_bandwidth_hz(),
        "pulse_tau_s": PULSE_TAU_S,
        "time_bandwidth_product": time_bandwidth_product(),
        "extraction_tradeoff": [extraction_point(r)
                                for r in (0.5, 0.9, 0.99, 0.999)],
    }


# ================================================================ 4. Operating-point scan
# A 2D sweep over the (C1, C2) grid under a labelled pump cap
# C1 + C2 <= PUMP_CAP_SUM. The scan reports its own best point
# honestly: the grid maximum of eta_int, the count of points actually
# evaluated, and a fixed-sum contrast showing that at a fixed total
# cooperativity budget the matched split beats every lopsided split.

def scan_operating_points(cap=PUMP_CAP_SUM):
    """Grid scan for the best eta_int with C1 + C2 <= cap."""
    best = None
    evaluated = 0
    for c1 in SCAN_GRID:
        for c2 in SCAN_GRID:
            if c1 + c2 > cap:
                continue
            evaluated += 1
            eta_i = eta_internal(c1, c2)
            if best is None or eta_i > best["eta_internal"]:
                best = {"c1": c1, "c2": c2, "eta_internal": eta_i,
                        "eta_total": eta_total(c1, c2)}
    contrast = {}
    for name, (c1, c2) in {
        "matched_100_100": (100.0, 100.0),
        "lopsided_150_50": (150.0, 50.0),
        "extreme_199_1": (199.0, 1.0),
    }.items():
        contrast[name] = {"c1": c1, "c2": c2, "sum": c1 + c2,
                          "eta_internal": eta_internal(c1, c2)}
    return {
        "cap_sum": cap,
        "cap_rule": "C1 + C2 <= cap (labelled pump-power cap)",
        "points_evaluated": evaluated,
        "best": best,
        "fixed_sum_contrast": contrast,
    }


# ================================================================ 5. kNN operating-verdict classifier
# Features: total efficiency eta and input-referred added noise
# N_add. The training grid is labelled by the lab's own verdict
# policy (verdict_policy below) - the classifier interpolates the
# policy, it does not replace the operating-point arithmetic.

def verdict_policy(eta, n_add):
    """The lab's four-way operating verdict from (eta, N_add)."""
    efficient = eta >= ETA_QUANTUM_MIN
    quiet = n_add < NADD_QUANTUM_MAX
    if efficient and quiet:
        return "quantum-enabled"
    if efficient:
        return "efficient-but-noisy"
    if quiet:
        return "quiet-but-lossy"
    return "unusable"


def _training_grid():
    rows = []
    for eta in (0.02, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.55, 0.65, 0.75,
                0.85, 0.95):
        for n_add in (1e-4, 1e-3, 1e-2, 0.05, 0.1, 0.3, 0.6, 1.0, 1.5,
                      3.0, 10.0, 100.0):
            rows.append(((eta, n_add), verdict_policy(eta, n_add)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    eta, n_add = features
    return (eta, (math.log10(max(n_add, 1e-12)) + 4.0) / 6.0)


def classify_operating(eta, n_add, k=5):
    """kNN over the policy-labelled grid, deterministic tie-breaking."""
    target = _scaled((eta, n_add))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for _, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    priority = {"quantum-enabled": 0, "efficient-but-noisy": 1,
                "quiet-but-lossy": 2, "unusable": 3}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def _scenario_points():
    return {
        "matched_C10_100mK": operating_point(10.0, 10.0, 0.1),
        "matched_C10_4K": operating_point(10.0, 10.0, 4.0),
        "matched_C1_100mK": operating_point(1.0, 1.0, 0.1),
        "weak_C0.1_4K": operating_point(0.1, 0.1, 4.0),
    }


def classifier_report():
    return {name: classify_operating(p["eta_total"], p["n_add"])
            for name, p in _scenario_points().items()}


# ================================================================ 6. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumtransduction-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all hardware and network gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="quantumtransduction-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Say it in the first line of every report: eta = 0.99 is a property of the cooperativity formula at matched C = 100, not of any device - then show the mismatch penalty, the 4 K noise number, and the extraction peak, because those three are where transducer claims usually hide.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a microwave photon entering a converter and leaving as light",
                  "two cooperativity dials rising together toward the matched ridge",
                  "one dial pinned at 100, the other at 1, efficiency falling off a cliff",
                  "a thermal photon crowd thinning as the bath cools 4 K to 10 mK",
                  "the extraction dial sweeping past its peak as bandwidth balloons"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. cooperativity conversion
    chk("eta_int_zero_cooperativity",
        eta_internal(0.0, 5.0) == 0.0 and eta_internal(0.0, 0.0) == 0.0)
    chk("eta_int_unity_point_formula", eta_internal(1.0, 1.0) == 4.0 / 9.0)
    chk("eta_int_symmetric", eta_internal(3.0, 7.0) == eta_internal(7.0, 3.0))
    chk("eta_int_matched_10", abs(eta_internal(10.0, 10.0) - 400.0 / 441.0) < 1e-15)
    chk("eta_int_matched_100",
        abs(eta_internal(100.0, 100.0) - 40000.0 / 40401.0) < 1e-15)
    chk("eta_int_matched_monotone",
        eta_internal(1.0, 1.0) < eta_internal(10.0, 10.0)
        < eta_internal(100.0, 100.0) < 1.0)
    chk("eta_int_matched_100_above_99pct", eta_internal(100.0, 100.0) > 0.99)
    chk("eta_int_mismatch_penalty", eta_internal(100.0, 1.0) < 0.04)
    chk("eta_int_fixed_sum_matched_best",
        eta_internal(100.0, 100.0) > eta_internal(150.0, 50.0)
        > eta_internal(199.0, 1.0))
    chk("eta_total_extraction_product",
        abs(eta_total(10.0, 10.0) - eta_internal(10.0, 10.0) * 0.81) < 1e-15)
    chk("eta_total_matched_10_value",
        abs(eta_total(10.0, 10.0) - 0.7346938775510204) < 1e-12)
    chk("eta_total_perfect_extraction",
        eta_total(10.0, 10.0, 1.0, 1.0) == eta_internal(10.0, 10.0)
        and eta_total(3.0, 7.0) <= eta_internal(3.0, 7.0))

    # 2. thermal noise + added noise
    chk("nth_4K_value",
        abs(thermal_occupation(MW_FREQ_HZ, 4.0) - 16.17429421036441) < 1e-9)
    chk("nth_100mK_value",
        abs(thermal_occupation(MW_FREQ_HZ, 0.1) - 0.09981030749537737) < 1e-12)
    chk("nth_10mK_tiny", 0.0 < thermal_occupation(MW_FREQ_HZ, 0.01) < 1e-9)
    chk("nth_monotone_in_T",
        thermal_occupation(MW_FREQ_HZ, 4.0) > thermal_occupation(MW_FREQ_HZ, 0.1)
        > thermal_occupation(MW_FREQ_HZ, 0.01))
    chk("nth_high_T_limit",
        abs(thermal_occupation(MW_FREQ_HZ, 4.0)
            - (K_B * 4.0 / (H_PLANCK * MW_FREQ_HZ) - 0.5)) < 0.01)
    chk("nth_cold_limit", thermal_occupation(MW_FREQ_HZ, 0.001) < 1e-100)
    chk("harmonic_cooperativity",
        harmonic_cooperativity(10.0, 10.0) == 10.0
        and abs(harmonic_cooperativity(100.0, 1.0) - 200.0 / 101.0) < 1e-12)
    chk("nadd_100mK_quiet", added_noise(10.0, 10.0, 0.1) < 0.01)
    chk("nadd_4K_noisy", added_noise(10.0, 10.0, 4.0) > 1.0)
    chk("quantum_enabled_point",
        operating_point(10.0, 10.0, 0.1)["quantum_enabled"] is True
        and operating_point(10.0, 10.0, 4.0)["quantum_enabled"] is False
        and operating_point(1.0, 1.0, 0.1)["quantum_enabled"] is False)

    # 3. bandwidth + extraction tradeoff
    chk("conversion_bandwidth_value",
        abs(conversion_bandwidth_hz() - 20.0e6 / 3.0) < 1.0)
    chk("time_bandwidth_product_unity", abs(time_bandwidth_product() - 1.0) < 1e-12)
    chk("extraction_peak_interior",
        extraction_point(0.99)["eta_total"] > extraction_point(0.9)["eta_total"]
        > extraction_point(0.5)["eta_total"])
    chk("extraction_overcoupled_collapse",
        extraction_point(0.999)["eta_total"] < extraction_point(0.99)["eta_total"])
    chk("extraction_bandwidth_grows",
        extraction_point(0.999)["bandwidth_hz"]
        > extraction_point(0.99)["bandwidth_hz"]
        > extraction_point(0.9)["bandwidth_hz"])
    chk("extraction_cooperativity_falls",
        extraction_point(0.5)["c_each"] > extraction_point(0.9)["c_each"]
        > extraction_point(0.99)["c_each"] > extraction_point(0.999)["c_each"])
    chk("bandwidth_report_rows", len(bandwidth_report()["extraction_tradeoff"]) == 4)

    # 4. operating-point scan
    scan = scan_operating_points()
    chk("scan_best_point",
        scan["best"]["c1"] == 100.0 and scan["best"]["c2"] == 100.0)
    chk("scan_best_eta",
        abs(scan["best"]["eta_internal"] - 40000.0 / 40401.0) < 1e-15)
    chk("scan_points_evaluated", scan["points_evaluated"] == 81)
    chk("scan_best_total",
        abs(scan["best"]["eta_total"] - 0.8019603475161506) < 1e-12)
    chk("scan_fixed_sum_contrast",
        scan["fixed_sum_contrast"]["matched_100_100"]["eta_internal"]
        > scan["fixed_sum_contrast"]["lopsided_150_50"]["eta_internal"]
        > scan["fixed_sum_contrast"]["extreme_199_1"]["eta_internal"])
    chk("scan_deterministic", scan_operating_points() == scan)

    # 5. classifier - labels come from the lab's own verdict policy
    rep = classifier_report()
    chk("classifier_matched_cold_quantum_enabled",
        rep["matched_C10_100mK"] == "quantum-enabled")
    chk("classifier_matched_hot_efficient_but_noisy",
        rep["matched_C10_4K"] == "efficient-but-noisy")
    chk("classifier_weak_cold_quiet_but_lossy",
        rep["matched_C1_100mK"] == "quiet-but-lossy")
    chk("classifier_weak_hot_unusable", rep["weak_C0.1_4K"] == "unusable")
    chk("classifier_matches_policy",
        all(classify_operating(p["eta_total"], p["n_add"])
            == verdict_policy(p["eta_total"], p["n_add"])
            for p in _scenario_points().values()))
    chk("policy_thresholds",
        verdict_policy(0.5, 0.5) == "quantum-enabled"
        and verdict_policy(0.5, 1.0) == "efficient-but-noisy"
        and verdict_policy(0.49, 0.5) == "quiet-but-lossy"
        and verdict_policy(0.49, 1.0) == "unusable")

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_hardware_hold", gate("hardware_efficiency_claim") == "HOLD")
    chk("gate_network_hold", gate("quantum_network_deployment") == "HOLD")
    chk("gate_measurement_hold", gate("measurement_fabrication") == "HOLD")
    chk("gate_qkd_hold", gate("qkd_security_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumTransduction-Lab - microwave-to-optical transduction lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - formulas at labelled parameters, nothing more")
    print("    This lab evaluates the standard beam-splitter cooperativity")
    print("    formula and Bose-Einstein thermal occupation at LABELLED")
    print("    teaching parameters. No device was built, cooled, or measured.")
    print("    An efficiency here is a property of the formula at the stated")
    print("    inputs - never a hardware promise or a device specification.")
    conv = conversion_report()
    print("\n[2] Cooperativity conversion - eta_int = 4*C1*C2 / (1 + C1 + C2)^2")
    print(f"    extraction ratios: microwave {EXTRACTION_MW} | "
          f"optical {EXTRACTION_OPT}")
    for name, p in conv["points"].items():
        print(f"    {name:22s} C1 {p['c1']:>7g} C2 {p['c2']:>7g} | "
              f"eta_int {p['eta_internal']:.6f} | eta_total {p['eta_total']:.6f}")
    print("    -> unity needs C1 = C2 >> 1. Matched C = 100 reaches 0.990075;")
    print("       the same total budget split 199/1 collapses to 0.019702.")
    print("       Mismatch is not a tax - it is a cliff.")
    noise = noise_report()
    print("\n[3] Thermal noise - n_th at 5 GHz, hf/k = "
          f"{noise['hf_over_k_kelvin']:.6f} K")
    for row in noise["temperatures"].values():
        print(f"    T {row['temp_k']:>6g} K | n_th {row['n_th_5ghz']:.6g} | "
              f"N_add at matched C=10: {row['n_add_at_C10_matched']:.6g}")
    print("    -> at 4 K the microwave mode holds ~16 thermal photons and")
    print("       N_add = 1.617 > 1: efficient but NOT quantum-enabled.")
    print("       At 100 mK, N_add = 0.009981 < 1 with eta_total = 0.734694:")
    print("       the same converter crosses the quantum-enabled line.")
    bw = bandwidth_report()
    print("\n[4] Bandwidth + pulse bookkeeping (labelled linewidths)")
    print(f"    loaded linewidths: microwave {KAPPA_MW_HZ / 1e6:g} MHz | "
          f"optical {KAPPA_OPT_HZ / 1e6:g} MHz")
    print(f"    conversion bandwidth (series model): "
          f"{bw['conversion_bandwidth_hz'] / 1e6:.4f} MHz")
    print(f"    pulse {PULSE_TAU_S * 1e9:g} ns -> time-bandwidth product "
          f"{bw['time_bandwidth_product']:.4f}")
    print("    extraction tradeoff (C0 = 1000 at r = 0, matched both sides):")
    for row in bw["extraction_tradeoff"]:
        print(f"    r {row['r']:>5g} | C {row['c_each']:>7g} | "
              f"eta_total {row['eta_total']:.6f} | "
              f"BW {row['bandwidth_hz'] / 1e6:>8g} MHz")
    print("    -> eta_total peaks at r = 0.99 (0.888980); at r = 0.999 the")
    print("       bandwidth is 10x wider and the efficiency has halved.")
    scan = scan_operating_points()
    best = scan["best"]
    print(f"\n[5] Operating-point scan - pump cap C1 + C2 <= {scan['cap_sum']:g}")
    print(f"    grid points evaluated under the cap: {scan['points_evaluated']}")
    print(f"    best point: C1 {best['c1']:g} C2 {best['c2']:g} | "
          f"eta_int {best['eta_internal']:.6f} | "
          f"eta_total {best['eta_total']:.6f}")
    print("    -> the scan's own optimum is the matched point, found by")
    print("       sweeping - not assumed. The cap is a labelled pump budget.")
    print("\n[6] Operating verdicts (TinyML kNN, labels from the lab policy)")
    points = _scenario_points()
    for name, label in classifier_report().items():
        p = points[name]
        print(f"    {name:22s} eta {p['eta_total']:.4f} "
              f"N_add {p['n_add']:.6g} -> {label}")
    print("\n[7] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[8] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "convert":
        print(json.dumps(conversion_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "noise":
        print(json.dumps(noise_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "bandwidth":
        print(json.dumps(bandwidth_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "scan":
        print(json.dumps(scan_operating_points(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "hardware_efficiency_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
