import unittest

from alias_engine import expand_aliases
from normalize import normalize_input


class AliasExpansionTests(unittest.TestCase):
    def test_calc_alias_expands_to_calculator(self):
        self.assertEqual(expand_aliases("calc"), "calculator")

    def test_open_calc_expands_target(self):
        self.assertEqual(normalize_input("open calc"), "open calculator")

    def test_open_calculator_stays_clean(self):
        self.assertEqual(normalize_input("open calculator"), "open calculator")

    def test_calculator_does_not_expand_inside_word(self):
        self.assertEqual(expand_aliases("calculator"), "calculator")

    def test_repeated_expansion_is_idempotent(self):
        once = normalize_input("open calc")
        twice = expand_aliases(once)
        self.assertEqual(once, "open calculator")
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()
