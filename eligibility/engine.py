from typing import Any, Dict, List

from .models import Activity, LaunchContext

# Fields that must be present for an activity record to be considered valid.
_REQUIRED_FIELDS = {"id", "release", "markets", "required_modules"}


class ActivityEligibilityEngine:
    """Determines which activities a customer is eligible to see.

    Eligibility rules (all must hold):
    1. The activity belongs to the customer's active release.
    2. The activity supports the customer's current market.
    3. Every physical module required by the activity is available to the customer.
    4. The activity record contains all required fields and is safe to evaluate.
    """

    def get_eligible_activities(
        self,
        context: LaunchContext,
        activity_library: List[Dict[str, Any]],
    ) -> List[Activity]:
        """Return activities from *activity_library* that *context* qualifies for.

        Records that fail validation are silently skipped so that a single
        malformed entry never blocks the remaining library from being evaluated.
        """
        eligible: List[Activity] = []
        for raw in activity_library:
            if not self._is_valid(raw):
                continue
            activity = self._parse(raw)
            if self._is_eligible(context, activity):
                eligible.append(activity)
        return eligible

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_valid(self, raw: Dict[str, Any]) -> bool:
        """Return True only when *raw* contains every required field."""
        return _REQUIRED_FIELDS.issubset(raw.keys())

    def _parse(self, raw: Dict[str, Any]) -> Activity:
        return Activity(
            id=raw["id"],
            release=raw["release"],
            markets=list(raw["markets"]),
            required_modules=list(raw["required_modules"]),
        )

    def _is_eligible(self, context: LaunchContext, activity: Activity) -> bool:
        # Rule 1 – release must match the customer's active release.
        if activity.release != context.release:
            return False

        # Rule 2 – the activity must support the customer's market.
        if context.market not in activity.markets:
            return False

        # Rule 3 – every required physical module must be available to the customer.
        if not set(activity.required_modules).issubset(context.available_modules):
            return False

        return True
