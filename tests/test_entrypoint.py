"""Exercise the image's entrypoint and real SDK against a local HTTP fixture."""

import unittest

from fixture_api import FixtureAPI


class WebEntrypointTests(unittest.TestCase):
    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for failure in ("API Error:", "An unexpected error occurred:", "Traceback"):
            self.assertNotIn(failure, result.stdout + result.stderr)
        self.assertIn("URL indexed successfully", result.stdout)

    def check_crawl(self, existing):
        with FixtureAPI(existing=existing) as api:
            api.pages.update({
                "/site/": (200, '''<html><head><title>Home title</title></head><body>
                    <nav>Excluded navigation
                    <a href="/site/child#first">First child link</a>
                    <a href="/site/child#second">Repeated child link</a>
                    <a href="/site/redirect">Redirect</a>
                    <a href="/site/missing">Missing page</a>
                    <a href="/outside">Outside path</a></nav>
                    <main><h1>Home content</h1><p>Welcome documentation.</p></main></body></html>''', {}),
                "/site/child": (200, '''<html><head><title>Child title</title></head><body>
                    <nav>Excluded child navigation</nav><main><h2>Child content</h2>
                    <a href="/site/deep">Deeper page</a><a href="/site/#top">Home</a>
                    </main></body></html>''', {}),
                "/site/deep": (200, '''<title>Deep title</title><main>Deep documentation
                    <a href="/site/child#again">Child again</a></main>''', {}),
                "/site/redirect": (302, "", {"Location": "/site/redirected"}),
                "/site/redirected": (200, "<title>Redirected title</title><main>Redirected documentation</main>", {}),
                "/site/missing": (404, "Missing page", {}),
                "/outside": (200, "Should never be fetched", {}),
            })
            result = api.run("fixture-api-key", "fixture-index", api.url + "/site/", "--element", "main")
            self.assert_success(result)
            self.assertIn("Total pages added to index: 4", result.stdout)
            self.assertIn("404 Error: Page not found", result.stdout)
            self.assertIn("Skipped (No content)", result.stdout)
            self.assertEqual(len(api.documents), 4)
            docs = {doc["key"]: doc for doc in api.documents}
            self.assertEqual(set(docs), {api.url + path for path in ("/site/", "/site/child", "/site/deep", "/site/redirect")})
            for path, title, content in (
                ("/site/", "Home title", "Home content"),
                ("/site/child", "Child title", "Child content"),
                ("/site/deep", "Deep title", "Deep documentation"),
                ("/site/redirect", "Redirected title", "Redirected documentation"),
            ):
                doc = docs[api.url + path]
                self.assertIn(content, doc["content"])
                self.assertNotIn("Excluded", doc["content"])
                self.assertEqual(doc["content"], " ".join(doc["content"].split()))
                self.assertEqual(doc["metadata"], {
                    "url": api.url + path, "name": title,
                    "page_description": "Fixture page description", "keywords": ["fixture", "documentation"],
                })
            fetched = [path for method, path, _ in api.requests if method == "GET" and not path.startswith("/v1/")]
            self.assertEqual(set(fetched), {"/site/", "/site/child", "/site/deep", "/site/redirect", "/site/redirected", "/site/missing"})
            self.assertEqual(len(fetched), len(set(fetched)), "Fragment links or cycles caused duplicate fetches")
            self.assertEqual(len(api.calls), 4)
            for call in api.calls:
                self.assertEqual(call["name"], "extract_docs_metadata")
                self.assertEqual(call["model"], "gcp/gemini-2.0-flash-lite-eu")
                self.assertEqual(set(call["output_schema"]["required"]), {"page_description", "keywords"})
                self.assertTrue(call["parent_span_uuid"])
            self.assertEqual(len(api.created_indexes), 0 if existing else 1)
            spans = [body for method, path, body in api.requests if (method, path) == ("POST", "/v1/spans")]
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0]["name"], "recursive_scrape")
            self.assertTrue(any(method == "PUT" and path.startswith("/v1/spans/")
                                for method, path, _ in api.requests))

    def test_positional_api_key_creates_index_and_recursively_crawls(self):
        self.check_crawl(existing=False)

    def test_positional_api_key_reuses_existing_index(self):
        self.check_crawl(existing=True)

    def test_unmatched_element_falls_back_to_full_page(self):
        with FixtureAPI(existing=True) as api:
            api.pages["/site/"] = (200, "<title>Fallback</title><nav>Navigation text</nav><article>Full page content</article>", {})
            result = api.run("fixture-api-key", "fixture-index", api.url + "/site/", "--element", "main")
            self.assert_success(result)
            self.assertEqual(len(api.documents), 1)
            self.assertIn("Navigation text", api.documents[0]["content"])
            self.assertIn("Full page content", api.documents[0]["content"])
            self.assertEqual(api.documents[0]["metadata"]["name"], "Fallback")

    def test_missing_start_page_is_skipped_without_metadata_or_document(self):
        with FixtureAPI(existing=True) as api:
            api.pages["/site/"] = (404, "Not found", {})
            result = api.run("fixture-api-key", "fixture-index", api.url + "/site/")
            self.assert_success(result)
            self.assertIn("404 Error: Page not found", result.stdout)
            self.assertIn("Total pages added to index: 0", result.stdout)
            self.assertEqual(api.calls, [])
            self.assertEqual(api.documents, [])

    def test_document_rejection_reports_failure_and_no_success_message(self):
        with FixtureAPI(existing=True, reject_document=True) as api:
            api.pages["/site/"] = (200, "<title>Rejected</title><main>Documentation</main>", {})
            result = api.run("fixture-api-key", "fixture-index", api.url + "/site/")
            self.assertIn("API Error:", result.stdout)
            self.assertIn("Failed to add document", result.stdout)
            self.assertNotIn("URL indexed successfully", result.stdout)
            self.assertEqual(len(api.calls), 1)
            self.assertEqual(api.documents, [])

    def test_cli_help_requires_no_api_requests(self):
        with FixtureAPI() as api:
            result = api.run("--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--element", result.stdout)
            self.assertIn("api_key", result.stdout)
            self.assertEqual(api.requests, [])

    def test_cli_missing_arguments_fails_before_api_requests(self):
        with FixtureAPI() as api:
            result = api.run("fixture-api-key")
            self.assertEqual(result.returncode, 2)
            self.assertIn("required", result.stderr)
            self.assertEqual(api.requests, [])


if __name__ == "__main__":
    unittest.main()
