import unittest

import numpy as np
from cm_pipeline_all_in_one import overlapping_allan_variance


class AllanVarianceTests(unittest.TestCase):
    def test_offset_and_linear_drift(self):
        t = np.arange(10000) * 0.1
        tau, var, _, _ = overlapping_allan_variance(7 + 2*t, t)
        np.testing.assert_allclose(var[:, 0], 2*tau**2, rtol=1e-7)
        _, var, _, _ = overlapping_allan_variance(np.full(len(t), 7), t)
        self.assertTrue(np.all(var == 0))
        x = np.random.default_rng(42).normal(size=len(t))
        _, var, _, _ = overlapping_allan_variance(x, t)
        _, shifted, _, _ = overlapping_allan_variance(x + 100, t)
        np.testing.assert_allclose(var, shifted, rtol=1e-10)

    def test_matches_direct_windows_with_gaps_and_nonfinite_data(self):
        x = np.random.default_rng(1).normal(size=(200, 2))
        t = np.arange(200, dtype=float)
        t[100:] += 20
        x[50, 0] = np.nan
        _, var, counts, factors = overlapping_allan_variance(x, t)
        for j, m in enumerate(factors):
            for col in range(2):
                direct = [
                    (x[i+m:i+2*m, col].mean() - x[i:i+m, col].mean())**2 / 2
                    for i in range(len(x)-2*m+1)
                    if np.all(np.isfinite(x[i:i+2*m, col]))
                    and np.all(np.diff(t[i:i+2*m]) == 1)
                ]
                np.testing.assert_allclose(var[j, col], np.mean(direct), rtol=1e-12)
                self.assertEqual(counts[j, col], len(direct))

    def test_short_and_invalid_timestamps(self):
        for t in (np.arange(9), np.zeros(20), np.arange(20)[::-1]):
            with self.assertRaises(ValueError):
                overlapping_allan_variance(np.ones(len(t)), t)


if __name__ == "__main__":
    unittest.main()
