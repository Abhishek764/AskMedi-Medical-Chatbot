"""Safety rows for the medicine check. Each red flag and exclusion is a rule a clinician
should review; every change to app/triage/ needs a row here."""

import pytest

from app.triage.engine import (
    InvalidAnswer,
    TriageState,
    apply_answer,
    decide,
    question_for,
)
from app.triage.symptoms import (
    ACETAMINOPHEN,
    IBUPROFEN,
    MEDICINE_INTENT,
    NAPROXEN,
    PSEUDOEPHEDRINE,
    find_symptom,
)


def run(symptom: str, who: str, flags: list[str], health: list[str]):
    s = TriageState(symptom)
    s = apply_answer(s, 1, [who])
    s = apply_answer(s, 2, flags)
    s = apply_answer(s, 3, health)
    return decide(s)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("I have a headache, what medicine can I take?", "headache"),
        ("what tablet is good for fever", "fever"),
        ("I have loose motions since morning", "diarrhea"),
        ("which medicine for acidity", "heartburn"),
        ("what can I take for my back pain", "pain"),
        ("I've got a runny nose and blocked nose", "cold"),
        ("best medicine for sneezing and itchy eyes", "allergy"),
    ],
)
def test_detects_medicine_requests(text, key):
    assert find_symptom(text).key == key
    assert MEDICINE_INTENT.search(text)


def test_plain_information_question_is_not_a_medicine_request():
    assert not MEDICINE_INTENT.search("What is a migraine?")


def test_healthy_adult_gets_all_options():
    out = run("headache", "adult", ["none"], ["none"])
    assert out.kind == "medicines"
    assert out.medicines == (ACETAMINOPHEN, IBUPROFEN, NAPROXEN)


def test_emergency_flag_wins_over_everything():
    out = run("headache", "child", ["thunderclap"], ["none"])
    assert out.kind == "emergency"


@pytest.mark.parametrize("who", ["child", "pregnant"])
def test_children_and_pregnancy_go_to_a_pharmacist(who):
    out = run("fever", who, ["none"], ["none"])
    assert out.kind == "pharmacist" and out.medicines == ()


@pytest.mark.parametrize("flag", ["injury", "long"])
def test_doctor_flags_and_long_duration_go_to_a_doctor(flag):
    assert run("headache", "adult", [flag], ["none"]).kind == "doctor"


@pytest.mark.parametrize("condition", ["thinners", "stomach", "kidney", "heart", "asthma"])
def test_nsaids_removed_for_risk_conditions(condition):
    out = run("headache", "adult", ["none"], [condition])
    assert out.medicines == (ACETAMINOPHEN,)
    assert {m for m, _ in out.excluded} == {IBUPROFEN, NAPROXEN}


def test_paracetamol_removed_for_liver_disease():
    out = run("headache", "adult", ["none"], ["liver"])
    assert ACETAMINOPHEN not in out.medicines
    assert dict(out.excluded)[ACETAMINOPHEN].startswith("you have liver disease")


def test_older_adults_do_not_get_nsaids():
    assert run("pain", "older", ["none"], ["none"]).medicines == (ACETAMINOPHEN,)


def test_decongestant_removed_for_heart_disease():
    assert PSEUDOEPHEDRINE not in run("cold", "adult", ["none"], ["heart"]).medicines


def test_nothing_safe_left_goes_to_pharmacist():
    out = run("headache", "adult", ["none"], ["liver", "thinners"])
    assert out.kind == "pharmacist" and out.medicines == ()


def test_other_medicines_flag_interaction_check():
    assert run("allergy", "adult", ["none"], ["other_meds"]).check_interactions


def test_answers_are_validated():
    s = TriageState("fever")
    with pytest.raises(InvalidAnswer):
        apply_answer(s, 1, ["made-up"])
    with pytest.raises(InvalidAnswer):
        apply_answer(s, 1, ["adult", "older"])  # single choice
    with pytest.raises(InvalidAnswer):
        apply_answer(s, 2, ["none"])  # wrong step
    s = apply_answer(s, 1, ["adult"])
    assert question_for(s).step == 2
    assert apply_answer(s, 2, ["none", "breathing"]).answers["2"] == ["breathing"]


def test_state_round_trip_and_tampering():
    s = apply_answer(TriageState("cough"), 1, ["adult"])
    assert TriageState.from_dict(s.to_dict()) == s
    assert TriageState.from_dict({"symptom": "made-up", "step": 1, "answers": {}}) is None
    assert TriageState.from_dict({"symptom": "cough", "step": 9, "answers": {}}) is None
