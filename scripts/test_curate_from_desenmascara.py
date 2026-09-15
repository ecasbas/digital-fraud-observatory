"""Selection rules of the observatory curator. Run: python3 scripts/test_curate_from_desenmascara.py"""
import unittest

import curate_from_desenmascara as cur


def projection(**overrides):
    base = {"status": "complete", "verdict": "FRAUDULENT", "assessed_by": "phishdestroy_destroylist",
            "domain": "mantintransact.online", "risk_score": 100, "report_url": "https://desenmascara.me/analisis/x",
            "assessed_at": "2026-09-13T08:54:50+00:00", "explanation": "Fraud type: bank impersonation.",
            "evidence": [{"label": "Possible MANTIN TRANSACT impersonation", "positive": False},
                         {"label": "Domain registered 14 days ago", "positive": False},
                         {"label": "Contact details found", "positive": True}]}
    base.update(overrides)
    return base


class RejectionTests(unittest.TestCase):
    def test_accepts_attributable_fraud(self):
        self.assertIsNone(cur.rejection_reason(projection(), rank=None, disputed=False))

    def test_published_verdict_decides_not_pipeline_column(self):
        # A human correction to LEGIT reaches the curator as the projection's verdict.
        self.assertIn("LEGIT", cur.rejection_reason(projection(verdict="LEGIT"), None, False))

    def test_pending_report_rejected(self):
        self.assertIsNotNone(cur.rejection_reason(projection(status="pending", verdict=None), None, False))

    def test_well_known_domain_rejected(self):
        self.assertIn("well-known", cur.rejection_reason(projection(), rank=168, disputed=False))
        self.assertIsNone(cur.rejection_reason(projection(), rank=400_000, disputed=False))

    def test_disputed_rejected(self):
        self.assertIn("disputed", cur.rejection_reason(projection(), None, True))

    def test_regulator_and_unknown_basis_rejected(self):
        for basis in ("regulatory_warnings", "unknown", None):
            self.assertIn("basis", cur.rejection_reason(projection(assessed_by=basis), None, False))


class CaseTextTests(unittest.TestCase):
    def test_third_party_listing_is_attributed(self):
        case = cur.build_case(projection(), "SA-010", "x", "x.png", "https://desenmascara.me/screens/x.png")
        self.assertIn("PhishDestroy", case["assessment_source"])
        self.assertIn("not an independent finding", case["source_summary"])

    def test_own_name_is_not_impersonation(self):
        obs = cur.observations_from(projection(), "mantintransact.online")
        self.assertFalse(any("impersonation" in o for o in obs))
        self.assertTrue(any("14 days" in o for o in obs))
        self.assertFalse(any("Contact details" in o for o in obs))

    def test_foreign_brand_impersonation_kept(self):
        p = projection(evidence=[{"label": "Possible PayPal impersonation", "positive": False}])
        self.assertTrue(cur.observations_from(p, "secure-login-verify.top"))

    def test_category_prefers_stated_fraud_type(self):
        self.assertEqual(cur.choose_category(projection(), "mantintransact.online")[0], "Banking")

    def test_ids_never_reused_after_withdrawal(self):
        self.assertEqual(cur.next_id([{"id": "SA-008"}], high_water=9), "SA-010")


if __name__ == "__main__":
    unittest.main()
