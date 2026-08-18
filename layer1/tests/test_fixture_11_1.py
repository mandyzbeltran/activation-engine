"""Golden scoring regression from specification section 11.1."""

from decimal import Decimal
import unittest

from layer1.aggregate.scoring import (
    noisy_or,
    score_profection,
    score_transit_to_natal,
)


class Fixture111Test(unittest.TestCase):
    def test_saturn_conj_mc_and_profection_intensity(self) -> None:
        transit = score_transit_to_natal(
            transiting_body="saturn",
            natal_target="mc",
            aspect="conjunction",
            angular_distance_deg="0.42",
            phase="applying",
            stationary=False,
            # Section 4.4 says MC's prominence is already represented by W_target.
            natal_prominent=False,
        )
        profection = score_profection(
            year_lord_match=True,
            profection_house=11,
        )
        intensity = noisy_or((
            ("drv_2", profection),
            ("drv_1", transit),
        ))

        self.assertEqual(transit, Decimal("0.620000"))
        self.assertEqual(profection, Decimal("0.420000"))
        self.assertEqual(intensity, Decimal("0.780000"))

    def test_noisy_or_is_input_order_independent(self) -> None:
        forward = noisy_or((("drv_1", "0.620"), ("drv_2", "0.420")))
        reverse = noisy_or((("drv_2", "0.420"), ("drv_1", "0.620")))
        self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main()

