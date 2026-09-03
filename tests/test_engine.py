"""Tests for the ActivityEligibilityEngine.

Covers all four eligibility rules as well as the validation guard that keeps
malformed activity records from breaking the evaluation loop.
"""

import pytest

from eligibility import ActivityEligibilityEngine, LaunchContext


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return ActivityEligibilityEngine()


@pytest.fixture
def base_context():
    """A fully equipped launch context for the holiday release in market 'US'."""
    return LaunchContext(
        release="holiday-launch",
        market="US",
        available_modules={"base-set", "expansion-a", "expansion-b"},
    )


def _activity(
    id="act-1",
    release="holiday-launch",
    markets=None,
    required_modules=None,
):
    """Helper that returns a raw activity dict with sensible defaults."""
    return {
        "id": id,
        "release": release,
        "markets": markets if markets is not None else ["US"],
        "required_modules": required_modules if required_modules is not None else ["base-set"],
    }


# ---------------------------------------------------------------------------
# Rule 4 – validation: records missing required fields are skipped
# ---------------------------------------------------------------------------

class TestValidation:
    def test_missing_id_is_skipped(self, engine, base_context):
        raw = _activity()
        del raw["id"]
        assert engine.get_eligible_activities(base_context, [raw]) == []

    def test_missing_release_is_skipped(self, engine, base_context):
        raw = _activity()
        del raw["release"]
        assert engine.get_eligible_activities(base_context, [raw]) == []

    def test_missing_markets_is_skipped(self, engine, base_context):
        raw = _activity()
        del raw["markets"]
        assert engine.get_eligible_activities(base_context, [raw]) == []

    def test_missing_required_modules_is_skipped(self, engine, base_context):
        raw = _activity()
        del raw["required_modules"]
        assert engine.get_eligible_activities(base_context, [raw]) == []

    def test_invalid_record_does_not_block_valid_ones(self, engine, base_context):
        """A bad record in the library must not prevent valid activities from appearing."""
        bad = {"id": "bad-act"}  # missing release, markets, required_modules
        good = _activity(id="good-act")
        result = engine.get_eligible_activities(base_context, [bad, good])
        assert len(result) == 1
        assert result[0].id == "good-act"

    def test_empty_library_returns_empty_list(self, engine, base_context):
        assert engine.get_eligible_activities(base_context, []) == []


# ---------------------------------------------------------------------------
# Rule 1 – release must match the customer's active release
# ---------------------------------------------------------------------------

class TestReleaseRule:
    def test_matching_release_is_included(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(release="holiday-launch")])
        assert len(result) == 1

    def test_different_release_is_excluded(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(release="spring-launch")])
        assert result == []

    def test_only_matching_release_activities_are_returned(self, engine, base_context):
        library = [
            _activity(id="correct", release="holiday-launch"),
            _activity(id="wrong", release="spring-launch"),
        ]
        result = engine.get_eligible_activities(base_context, library)
        assert [a.id for a in result] == ["correct"]


# ---------------------------------------------------------------------------
# Rule 2 – activity must support the customer's market
# ---------------------------------------------------------------------------

class TestMarketRule:
    def test_activity_supporting_customer_market_is_included(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(markets=["US", "CA"])])
        assert len(result) == 1

    def test_activity_not_supporting_customer_market_is_excluded(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(markets=["CA", "UK"])])
        assert result == []

    def test_activity_with_no_markets_is_excluded(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(markets=[])])
        assert result == []

    def test_different_market_context(self, engine):
        ca_context = LaunchContext(
            release="holiday-launch",
            market="CA",
            available_modules={"base-set"},
        )
        library = [
            _activity(id="us-only", markets=["US"]),
            _activity(id="ca-and-us", markets=["CA", "US"]),
        ]
        result = engine.get_eligible_activities(ca_context, library)
        assert [a.id for a in result] == ["ca-and-us"]


# ---------------------------------------------------------------------------
# Rule 3 – every required module must be available to the customer
# ---------------------------------------------------------------------------

class TestModuleAvailabilityRule:
    def test_activity_with_no_required_modules_is_included(self, engine, base_context):
        result = engine.get_eligible_activities(base_context, [_activity(required_modules=[])])
        assert len(result) == 1

    def test_all_required_modules_available(self, engine, base_context):
        result = engine.get_eligible_activities(
            base_context, [_activity(required_modules=["base-set", "expansion-a"])]
        )
        assert len(result) == 1

    def test_one_missing_module_excludes_activity(self, engine, base_context):
        result = engine.get_eligible_activities(
            base_context, [_activity(required_modules=["base-set", "delayed-expansion"])]
        )
        assert result == []

    def test_all_modules_missing_excludes_activity(self, engine, base_context):
        result = engine.get_eligible_activities(
            base_context, [_activity(required_modules=["delayed-expansion"])]
        )
        assert result == []

    def test_unavailable_module_never_appears_in_results(self, engine):
        """Acceptance criterion: unavailable modules never appear in launch-release activities."""
        limited_context = LaunchContext(
            release="holiday-launch",
            market="US",
            available_modules={"base-set"},  # delayed expansion NOT available
        )
        library = [
            _activity(id="base-only", required_modules=["base-set"]),
            _activity(id="needs-expansion", required_modules=["base-set", "delayed-expansion"]),
        ]
        result = engine.get_eligible_activities(limited_context, library)
        assert len(result) == 1
        assert result[0].id == "base-only"
        assert not any(a.id == "needs-expansion" for a in result)

    def test_delayed_expansion_activities_appear_when_enabled(self, engine):
        """Acceptance criterion: delayed expansion can be enabled without reworking the launch release."""
        expanded_context = LaunchContext(
            release="holiday-launch",
            market="US",
            available_modules={"base-set", "delayed-expansion"},
        )
        library = [
            _activity(id="base-only", required_modules=["base-set"]),
            _activity(id="needs-expansion", required_modules=["base-set", "delayed-expansion"]),
        ]
        result = engine.get_eligible_activities(expanded_context, library)
        assert len(result) == 2
        assert {a.id for a in result} == {"base-only", "needs-expansion"}


# ---------------------------------------------------------------------------
# Combined / integration scenarios
# ---------------------------------------------------------------------------

class TestCombinedRules:
    def test_all_rules_must_pass(self, engine):
        context = LaunchContext(
            release="holiday-launch",
            market="UK",
            available_modules={"base-set"},
        )
        library = [
            # Fails rule 1 (wrong release)
            _activity(id="wrong-release", release="spring-launch", markets=["UK"], required_modules=["base-set"]),
            # Fails rule 2 (wrong market)
            _activity(id="wrong-market", release="holiday-launch", markets=["US"], required_modules=["base-set"]),
            # Fails rule 3 (missing module)
            _activity(id="missing-module", release="holiday-launch", markets=["UK"], required_modules=["expansion-a"]),
            # Passes all rules
            _activity(id="eligible", release="holiday-launch", markets=["UK"], required_modules=["base-set"]),
        ]
        result = engine.get_eligible_activities(context, library)
        assert [a.id for a in result] == ["eligible"]

    def test_eligible_activities_determined_by_market_and_launch_configuration(self, engine):
        """Acceptance criterion: eligible activities are determined by market and launch config."""
        us_context = LaunchContext(
            release="holiday-launch",
            market="US",
            available_modules={"base-set", "expansion-a"},
        )
        uk_context = LaunchContext(
            release="holiday-launch",
            market="UK",
            available_modules={"base-set"},
        )
        library = [
            _activity(id="global-base", markets=["US", "UK"], required_modules=["base-set"]),
            _activity(id="us-expansion", markets=["US"], required_modules=["base-set", "expansion-a"]),
            _activity(id="uk-only", markets=["UK"], required_modules=["base-set"]),
        ]
        us_result_ids = {a.id for a in engine.get_eligible_activities(us_context, library)}
        uk_result_ids = {a.id for a in engine.get_eligible_activities(uk_context, library)}

        assert us_result_ids == {"global-base", "us-expansion"}
        assert uk_result_ids == {"global-base", "uk-only"}

    def test_returns_activity_objects_with_correct_data(self, engine, base_context):
        raw = _activity(
            id="act-42",
            release="holiday-launch",
            markets=["US"],
            required_modules=["base-set"],
        )
        result = engine.get_eligible_activities(base_context, [raw])
        assert len(result) == 1
        act = result[0]
        assert act.id == "act-42"
        assert act.release == "holiday-launch"
        assert act.markets == ["US"]
        assert act.required_modules == ["base-set"]
