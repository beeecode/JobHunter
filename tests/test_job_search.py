import unittest
from unittest.mock import Mock, patch

import requests

from job_search import (
    SEARCH_QUERIES,
    build_remote_query,
    build_email_html,
    extract_keywords,
    filter_jobs,
    get_json,
    nigeria_priority_score,
    redact_url,
)


class JobSearchTests(unittest.TestCase):
    def test_filter_jobs_deduplicates_and_prioritizes_nigeria_jobs(self):
        jobs = [
            {
                "source": "jsearch",
                "job_title": "Frontend Developer",
                "employer_name": "Example Co",
                "job_apply_link": "https://example.com/apply",
                "job_is_remote": True,
                "job_country": "Nigeria",
                "job_city": "Lagos",
                "job_description": "Build React interfaces for customers in Nigeria.",
            },
            {
                "source": "jsearch",
                "job_title": " Frontend   Developer ",
                "employer_name": "example co",
                "job_apply_link": "https://example.com/apply",
                "job_is_remote": True,
                "job_country": "Nigeria",
                "job_city": "Lagos",
                "job_description": "Duplicate posting.",
            },
            {
                "source": "jsearch",
                "job_title": "Engineering Director",
                "employer_name": "Leadership Co",
                "job_apply_link": "https://example.com/director",
                "job_is_remote": True,
                "job_description": "Executive role.",
            },
        ]

        filtered = filter_jobs(jobs)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["company"], "Example Co")
        self.assertTrue(filtered[0]["is_priority"])

    def test_filter_jobs_removes_non_remote_jsearch_jobs(self):
        jobs = [
            {
                "source": "jsearch",
                "job_title": "Backend Developer",
                "employer_name": "Office Co",
                "job_apply_link": "https://example.com/office",
                "job_is_remote": False,
                "job_description": "Python and APIs.",
            }
        ]

        self.assertEqual(filter_jobs(jobs), [])

    def test_nigeria_search_results_rank_above_global_unknown_jobs(self):
        jobs = [
            {
                "source": "jsearch",
                "search_country": None,
                "search_priority": "global",
                "job_title": "Full Stack Developer",
                "employer_name": "Global Co",
                "job_apply_link": "https://example.com/global",
                "job_is_remote": True,
                "job_description": "Remote role.",
            },
            {
                "source": "jsearch",
                "search_country": "NG",
                "search_priority": "nigeria",
                "job_title": "Full Stack Developer",
                "employer_name": "Nigeria Co",
                "job_apply_link": "https://example.com/ng",
                "job_is_remote": True,
                "job_description": "Remote role.",
            },
        ]

        filtered = filter_jobs(jobs)

        self.assertEqual(filtered[0]["company"], "Nigeria Co")
        self.assertTrue(filtered[0]["is_priority"])
        self.assertGreater(filtered[0]["priority_score"], filtered[1]["priority_score"])

    def test_nigeria_priority_score_checks_location_and_description(self):
        location_match = nigeria_priority_score({"job_location": "Lagos, Nigeria"}, "")
        description_match = nigeria_priority_score({}, "Salary paid in naira for Nigerian applicants.")

        self.assertGreaterEqual(location_match, 80)
        self.assertGreater(description_match, 0)

    def test_search_queries_include_nigeria_and_worldwide_coverage(self):
        nigeria_queries = [query for query in SEARCH_QUERIES if query["priority"] == "nigeria"]
        worldwide_queries = [query for query in SEARCH_QUERIES if query["priority"] == "worldwide"]

        self.assertGreaterEqual(len(nigeria_queries), 5)
        self.assertGreaterEqual(len(worldwide_queries), 5)
        self.assertTrue(all(query["country"] == "NG" for query in nigeria_queries))
        self.assertTrue(all(query["country"] is None for query in worldwide_queries))

    def test_build_remote_query_does_not_duplicate_remote(self):
        self.assertEqual(build_remote_query("Frontend Developer"), "Frontend Developer remote")
        self.assertEqual(build_remote_query("Frontend Developer remote"), "Frontend Developer remote")

    def test_email_html_uses_card_ui_and_priority_counts(self):
        jobs = [
            {
                "job_title": "Frontend Developer",
                "company": "Nigeria Co",
                "location": "Lagos, Nigeria",
                "salary": "Not listed",
                "source": "jsearch",
                "is_priority": True,
                "direct_link": "https://example.com/ng",
                "job_description": "Build React interfaces for Nigerian customers.",
            },
            {
                "job_title": "Backend Developer",
                "company": "Global Co",
                "location": "Remote, Unknown",
                "salary": "Not listed",
                "source": "jsearch",
                "is_priority": False,
                "direct_link": "https://example.com/global",
                "job_description": "Build APIs with Python and Docker.",
            },
        ]

        html = build_email_html(jobs)

        self.assertIn("Nigeria Priority", html)
        self.assertIn("Worldwide", html)
        self.assertIn("job-card priority-ng", html)
        self.assertIn("Top opportunities, Nigeria first", html)

    def test_extract_keywords_finds_technical_skills(self):
        keywords = extract_keywords(
            "We need a React and TypeScript developer with Node.js, Docker, and AWS experience."
        )

        self.assertIn("React", keywords["technical_skills"])
        self.assertIn("Typescript", keywords["technical_skills"])
        self.assertIn("node.js", keywords["technical_skills"])

    def test_redact_url_hides_api_key(self):
        redacted = redact_url("https://example.com/search?q=jobs&key=secret-value&cx=engine")

        self.assertIn("key=%3Credacted%3E", redacted)
        self.assertNotIn("secret-value", redacted)
        self.assertIn("cx=engine", redacted)

    @patch("job_search.requests.get")
    def test_get_json_does_not_retry_client_errors(self, mock_get):
        response = Mock()
        response.status_code = 403
        response.reason = "Forbidden"
        response.url = "https://example.com/search?key=secret-value"
        http_error = requests.HTTPError(response=response)
        response.raise_for_status.side_effect = http_error
        mock_get.return_value = response

        with self.assertRaises(RuntimeError) as error:
            get_json("https://example.com/search", params={"key": "secret-value"})

        self.assertEqual(mock_get.call_count, 1)
        self.assertIn("403 Forbidden", str(error.exception))
        self.assertNotIn("secret-value", str(error.exception))


if __name__ == "__main__":
    unittest.main()
