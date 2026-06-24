"""Compatibility module for historical student view test imports.

Student view tests are split by behavior across sibling test modules. Test classes
are loaded lazily so Django discovery does not collect duplicates from this file.
"""

_CLASS_MODULES = {
    "StudentBasicViewTests": "apps.student.tests.test_auth_views",
    "StudentRoleBoundaryTests": "apps.student.tests.test_auth_views",
    "PlayerViewTests": "apps.student.tests.test_player_views",
    "Unit4PersonalizedServingViewTests": "apps.student.tests.test_player_views",
    "StudentUnitViewTests": "apps.student.tests.test_unit_views",
    "StudentUnitProgressBackLinkTests": "apps.student.tests.test_unit_views",
    "StudentHomeResumeTests": "apps.student.tests.test_home_views",
    "StudentHomeUnitDiscoveryTests": "apps.student.tests.test_home_views",
    "StudentHomeQueryBudgetTests": "apps.student.tests.test_home_views",
    "ChallengeGenerationConstraintTests": "apps.student.tests.test_challenge_views",
    "DesignTokensTests": "apps.student.tests.test_design_css",
    "PlayerCanvasCssExtractionTests": "apps.student.tests.test_design_css",
}


def __getattr__(name):
    module_name = _CLASS_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)

    from importlib import import_module

    return getattr(import_module(module_name), name)
