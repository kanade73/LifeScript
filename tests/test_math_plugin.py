"""Tests for the math plugin."""

from lifescript.plugins.math_plugin import get_random_number


class TestMathPlugin:
    def test_random_number_in_range(self):
        result = get_random_number(1, 10)
        assert 1 <= result <= 10

    def test_random_number_default_range(self):
        result = get_random_number()
        assert 1 <= result <= 100

    def test_random_number_same_min_max(self):
        result = get_random_number(5, 5)
        assert result == 5
