"""
tests.test_employment_type_gate — Regression tests for candidate constraint employment-type gate.
"""

import unittest
from evaluate import _gate_employment_type, run_explicit_constraint_gates


class TestEmploymentTypeGate(unittest.TestCase):
    def test_intern_rejected(self):
        job = {"title": "Software Engineer Intern", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded keyword in title", reason)

    def test_internship_rejected(self):
        job = {"title": "Product Management Internship", "job_type": ""}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded keyword in title", reason)

    def test_product_manager_intern_rejected(self):
        job = {"title": "Product Manager Intern", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded keyword in title", reason)

    def test_intern_with_hyphen_rejected(self):
        job = {"title": "Intern-Firmware Developer", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded keyword in title", reason)

    def test_international_not_rejected(self):
        job = {"title": "Product Manager, International Emerging Stores Payments", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertTrue(passes)
        self.assertEqual(reason, "employment_type: acceptable")

    def test_internal_not_rejected(self):
        job = {"title": "Internal Audit Manager — Payments", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertTrue(passes)
        self.assertEqual(reason, "employment_type: acceptable")

    def test_internet_not_rejected(self):
        job = {"title": "Internet Security Product Specialist", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertTrue(passes)
        self.assertEqual(reason, "employment_type: acceptable")

    def test_interoperability_not_rejected(self):
        job = {"title": "Lead PM — Interoperability & Open Banking", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertTrue(passes)
        self.assertEqual(reason, "employment_type: acceptable")

    def test_internally_not_rejected(self):
        job = {"title": "Staff Engineer, Internally Facing Systems", "job_type": "fulltime"}
        passes, reason = _gate_employment_type(job)
        self.assertTrue(passes)
        self.assertEqual(reason, "employment_type: acceptable")

    def test_case_insensitivity(self):
        job_upper_intern = {"title": "SOFTWARE ENGINEERING INTERN", "job_type": ""}
        passes, _ = _gate_employment_type(job_upper_intern)
        self.assertFalse(passes)

        job_mixed_international = {"title": "Director of INTERNATIONAL Expansion", "job_type": ""}
        passes, _ = _gate_employment_type(job_mixed_international)
        self.assertTrue(passes)

    def test_job_type_part_time_rejected(self):
        job = {"title": "Product Consultant", "job_type": "part-time"}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded job_type value", reason)

    def test_job_type_internship_rejected(self):
        job = {"title": "Executive Assistant to CEO", "job_type": "parttime, internship"}
        passes, reason = _gate_employment_type(job)
        self.assertFalse(passes)
        self.assertIn("excluded job_type value", reason)


if __name__ == "__main__":
    unittest.main()
