"""Tests for the unit suggester service."""

from django.test import TestCase

from apps.exercises.services.unit_suggester import (
    suggest_units_from_tags,
    build_tag_to_units_map,
)


class BuildTagToUnitsMapTest(TestCase):
    """Test the tag-to-units mapping builder."""

    def test_builds_non_empty_map(self):
        """Should build a non-empty mapping from taxonomy."""
        tag_map = build_tag_to_units_map()
        self.assertIsInstance(tag_map, dict)
        self.assertGreater(len(tag_map), 0)

    def test_dominant_seventh_maps_to_unit_9(self):
        """Dominant_Seventh should map to unit 9."""
        tag_map = build_tag_to_units_map()
        self.assertIn("Dominant_Seventh", tag_map)
        self.assertIn(9, tag_map["Dominant_Seventh"])

    def test_diatonic_triads_maps_to_unit_9(self):
        """Diatonic_Triads should map to unit 9."""
        tag_map = build_tag_to_units_map()
        self.assertIn("Diatonic_Triads", tag_map)
        self.assertIn(9, tag_map["Diatonic_Triads"])

    def test_caching_returns_same_object(self):
        """Multiple calls should return the same cached object."""
        map1 = build_tag_to_units_map()
        map2 = build_tag_to_units_map()
        self.assertIs(map1, map2)


class SuggestUnitsFromTagsTest(TestCase):
    """Test the unit suggestion logic."""

    def test_empty_tags_returns_empty(self):
        """Empty tag list should return empty units."""
        result = suggest_units_from_tags([])
        self.assertEqual(result, [])

    def test_suggests_unit_9_from_dominant_seventh(self):
        """Should suggest unit 9 when Dominant_Seventh tag detected."""
        tags = ["Dominant_Seventh"]
        result = suggest_units_from_tags(tags)
        self.assertIn(9, result)

    def test_suggests_unit_9_from_diatonic_triads(self):
        """Should suggest unit 9 when Diatonic_Triads tag detected."""
        tags = ["Diatonic_Triads"]
        result = suggest_units_from_tags(tags)
        self.assertIn(9, result)

    def test_multiple_tags_suggests_best_match(self):
        """Should rank units by match count."""
        tags = ["Dominant_Seventh", "Diatonic_Triads"]
        result = suggest_units_from_tags(tags, top_n=5)
        # Unit 9 should be first since it matches both tags
        if result:
            self.assertEqual(result[0], 9)

    def test_returns_at_most_top_n(self):
        """Should respect the top_n limit."""
        # These tags should match multiple units
        tags = [
            "Dominant_Seventh",
            "Diatonic_Triads",
            "Inversions_First",
            "Secondary_Dominant",
            "Neapolitan_Sixth",
            "Augmented_Sixth",
        ]
        result = suggest_units_from_tags(tags, top_n=3)
        self.assertLessEqual(len(result), 3)

    def test_unknown_tags_do_not_crash(self):
        """Unknown tags should be gracefully ignored."""
        result = suggest_units_from_tags(
            ["tag_that_does_not_exist", "another_fake_tag"]
        )
        self.assertEqual(result, [])

    def test_unknown_mixed_with_known(self):
        """Mix of unknown and known tags should work."""
        result = suggest_units_from_tags(
            ["Dominant_Seventh", "fake_tag_xyz", "Diatonic_Triads"]
        )
        self.assertIn(9, result)

    def test_returns_int_unit_numbers(self):
        """Returned units should be integers."""
        tags = ["Dominant_Seventh"]
        result = suggest_units_from_tags(tags)
        for unit in result:
            self.assertIsInstance(unit, int)

    def test_no_duplicate_units(self):
        """Result should not contain duplicates."""
        tags = ["Dominant_Seventh", "Diatonic_Triads"]
        result = suggest_units_from_tags(tags)
        self.assertEqual(len(result), len(set(result)))

    def test_descending_match_count_order(self):
        """Units should be ordered by match count (highest first)."""
        # Create tags that match some units more than others
        tag_map = build_tag_to_units_map()

        # Find a tag that matches only one unit
        single_match_tag = None
        multi_match_tag = None
        for tag, units in tag_map.items():
            if len(units) == 1:
                single_match_tag = tag
            elif len(units) > 1:
                multi_match_tag = tag

        if single_match_tag and multi_match_tag:
            # multi_match_tag unit should come before single_match_tag unit
            tags = [single_match_tag, multi_match_tag, multi_match_tag]
            result = suggest_units_from_tags(tags, top_n=10)

            # Find positions
            single_units = tag_map[single_match_tag]
            multi_units = tag_map[multi_match_tag]

            if single_units and multi_units:
                single_unit = single_units[0]
                multi_unit = multi_units[0]

                single_idx = result.index(single_unit) if single_unit in result else float('inf')
                multi_idx = result.index(multi_unit) if multi_unit in result else float('inf')

                # multi_unit should come before (lower index than) single_unit
                if single_idx != float('inf') and multi_idx != float('inf'):
                    self.assertLess(multi_idx, single_idx)
