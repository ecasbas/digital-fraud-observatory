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
    def test_accepts_our_own_ai_verdict(self):
        self.assertIsNone(cur.rejection_reason(projection(assessed_by="ai_reasoning"), rank=None, disputed=False))

    def test_phishdestroy_and_cloudflare_not_curated(self):
        for basis in ("phishdestroy_destroylist", "cloudflare_phishing"):
            self.assertIn("basis", cur.rejection_reason(projection(assessed_by=basis), None, False))

    def test_safe_browsing_and_regulator_curated(self):
        # Owner's decision 2026-10-08: both in scope, always attributed.
        for basis in ("google_safe_browsing", "regulatory_warnings"):
            self.assertIsNone(cur.rejection_reason(projection(assessed_by=basis), None, False))

    def test_published_verdict_decides_not_pipeline_column(self):
        # A human correction to LEGIT reaches the curator as the projection's verdict.
        self.assertIn("LEGIT", cur.rejection_reason(projection(verdict="LEGIT"), None, False))

    def test_pending_report_rejected(self):
        self.assertIsNotNone(cur.rejection_reason(projection(status="pending", verdict=None), None, False))

    def test_well_known_domain_rejected(self):
        self.assertIn("well-known", cur.rejection_reason(projection(assessed_by="ai_reasoning"), rank=168, disputed=False))
        self.assertIsNone(cur.rejection_reason(projection(assessed_by="ai_reasoning"), rank=400_000, disputed=False))

    def test_published_case_not_withdrawn_for_basis_alone(self):
        self.assertIsNone(cur.rejection_reason(projection(), None, False, check_basis=False))

    def test_disputed_rejected(self):
        self.assertIn("disputed", cur.rejection_reason(projection(assessed_by="ai_reasoning"), None, True))

    def test_unknown_basis_rejected(self):
        for basis in ("unknown", None):
            self.assertIn("basis", cur.rejection_reason(projection(assessed_by=basis), None, False))


class CaseTextTests(unittest.TestCase):
    def test_destroylist_label_does_not_decide_the_category(self):
        p = projection(assessed_by="heuristics", explanation="What we found: domain registered 12 days ago.",
                       evidence=[{"label": "Listed on DestroyList, the curated phishing feed maintained by PhishDestroy", "positive": False}])
        self.assertNotEqual(cur.choose_category(p, "myxtrade.cc")[0], "Phishing")

    def test_own_first_lead_is_not_read_as_the_pitch(self):
        p = cur.split_own_first_lead(projection(
            assessed_by="ai_reasoning", explanation_language="en",
            explanation="We detected it first: our analysis rated x.top fraudulent on 2026-10-05 at 09:24 UTC. PhishDestroy later added it.\n\nThe site presents itself as a cryptocurrency trading platform."))
        self.assertTrue(p["own_first"])
        self.assertTrue(p["explanation"].startswith("The site presents itself"))
        self.assertEqual(cur.choose_category(p, "x.top")[0], "Crypto")
        case = cur.build_case(p, "SA-060", "x", "x.png", "https://desenmascara.me/screens/x.png")
        self.assertIn("before PhishDestroy", case["observations"][0])
        self.assertNotIn("not an independent finding", case["source_summary"])

    def test_safe_browsing_and_regulator_cases_are_attributed(self):
        for basis, name in (("google_safe_browsing", "Google Safe Browsing"), ("regulatory_warnings", "regulator")):
            case = cur.build_case(projection(assessed_by=basis), "SA-010", "x", "x.png", "https://desenmascara.me/screens/x.png")
            self.assertIn(name, case["assessment_source"])
            self.assertIn("not an independent finding", case["source_summary"])
            self.assertIn(name, case["summary"])
            self.assertNotIn("Desenmascara's", case["summary"])

    def test_safe_browsing_text_files_under_phishing(self):
        p = projection(assessed_by="google_safe_browsing", domain="wetransfer-smoky.vercel.app",
                       explanation="Google Safe Browsing clasifica esta URL como maliciosa (phishing / ingeniería social). Damos el sitio por fraudulento según esa fuente.")
        self.assertEqual(cur.choose_category(p, p["domain"])[0], "Phishing")

    def test_third_party_listing_is_attributed(self):
        case = cur.build_case(projection(), "SA-010", "x", "x.png", "https://desenmascara.me/screens/x.png")
        self.assertIn("PhishDestroy", case["assessment_source"])
        self.assertIn("not an independent finding", case["source_summary"])

    def test_ai_case_quotes_first_sentence_and_whole_score(self):
        p = projection(assessed_by="ai_reasoning", risk_score=94.0, explanation_language="en",
                       explanation="The site promises guaranteed returns. More text.")
        case = cur.build_case(p, "SA-010", "x", "x.png", "u")
        self.assertEqual(case["assessment"], "Fraudulent · 94/100")
        self.assertIn("“The site promises guaranteed returns.”", case["source_summary"])

    def test_spanish_analysis_becomes_english_observations(self):
        es = ("El sitio presenta un esquema de inversión en criptomonedas con promesas de retornos diarios poco realistas. "
              "Además, la falta de enlaces a perfiles reales en redes sociales y el hecho de que el dominio es reciente (124 días) "
              "refuerzan la sospecha. Tipo de fraude: esquema de ganancias cripto.")
        found = cur.prose_findings(es)
        self.assertIn("Promises returns that are unrealistic or guaranteed.", found)
        self.assertIn("Social media icons do not lead to real profiles.", found)
        self.assertIn("The domain was only 124 days old when analysed.", found)
        self.assertEqual(cur.choose_category({"explanation": es, "evidence": []}, "nobletechglobalinvesting.com")[0], "Crypto")

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

    def test_shop_tld_is_not_a_shop(self):
        es = ("El sitio se presenta como una plataforma de trading automatizado, pero está alojado en una IP "
              "de infraestructura fraudulenta. Tipo de fraude: suplantación bancaria.")
        p = {"explanation": es, "evidence": [{"label": "Suspicious TLD (.shop)", "positive": False}]}
        self.assertEqual(cur.choose_category(p, "chrysarinsoft.shop")[0], "Investment")
        self.assertNotEqual(cur.choose_category({"explanation": "", "evidence": []}, "agosbitline.shop")[0], "Shopping")

    def test_fake_store_is_shopping(self):
        es = "El sitio se presenta como una tienda online de Nike con descuentos del 80% y pago con tarjeta. Tipo de fraude: tienda falsa."
        self.assertEqual(cur.choose_category({"explanation": es, "evidence": []}, "nike-outlet-sale.top")[0], "Shopping")

    def test_wording_varies_between_neighbouring_cases(self):
        p = projection(assessed_by="ai_reasoning")
        a, b = (cur.build_case(p, i, "x", "x.png", "u") for i in ("SA-020", "SA-021"))
        self.assertNotEqual(a["summary"], b["summary"])
        self.assertNotEqual(a["short_title"], b["short_title"])
        self.assertEqual(a["summary"], cur.build_case(p, "SA-020", "y", "y.png", "u")["summary"])

    def test_extra_sources_are_cited(self):
        vt = {"name": "VirusTotal", "short": "VirusTotal", "role": "r", "url": "https://www.virustotal.com/gui/domain/x"}
        case = cur.build_case(projection(assessed_by="ai_reasoning"), "SA-010", "x", "x.png", "u", [vt], 14)
        self.assertEqual([s["name"] for s in case["sources"]], ["desenmascara.me", "VirusTotal"])
        self.assertIn("14 security vendors", case["source_summary"])

    def test_canned_no_ai_text_is_not_called_ai(self):
        p = projection(assessed_by="ai_reasoning", explanation="What we found: extreme discounts. AI was not used (it is included in our paid plans).")
        case = cur.build_case(p, "SA-020", "x", "x.png", "u")
        self.assertEqual(case["assessment_source"], "desenmascara.me · heuristic analysis")

    def test_ids_never_reused_after_withdrawal(self):
        self.assertEqual(cur.next_id([{"id": "SA-008"}], high_water=9), "SA-010")


if __name__ == "__main__":
    unittest.main()
