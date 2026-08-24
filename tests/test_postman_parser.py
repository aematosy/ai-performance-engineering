#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "scripts" / "parse_postman_collection.py"
VALIDATOR = ROOT / "scripts" / "validate_normalized_postman.py"

class PostmanParserTests(unittest.TestCase):
    def base(self):
        return {"info": {"name": "Fixture", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}, "item": []}

    def run_parser(self, collection, environment=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            c, e, o = tmp/"c.json", tmp/"e.json", tmp/"o.json"
            c.write_text(json.dumps(collection), encoding="utf-8")
            cmd = [sys.executable, str(PARSER), "--collection", str(c), "--output", str(o)]
            if environment is not None:
                e.write_text(json.dumps(environment), encoding="utf-8")
                cmd += ["--environment", str(e)]
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return json.loads(o.read_text(encoding="utf-8"))

    def test_nested_and_environment_resolution(self):
        c = self.base()
        c["item"] = [{"name": "Folder", "item": [{"name": "Get", "request": {"method": "GET", "url": {"raw": "{{baseUrl}}/users/123"}}}]}]
        e = {"name": "Env", "values": [{"key": "baseUrl", "value": "https://example.test", "enabled": True}]}
        d = self.run_parser(c, e)
        self.assertEqual(d["requests"][0]["url"]["resolved"], "https://example.test/users/123")
        self.assertEqual(d["requests"][0]["folder_path"], ["Folder"])

    def test_dependency_and_redaction(self):
        c = self.base()
        c["item"] = [
            {"name": "Auth", "request": {"method": "POST", "url": {"raw": "https://example.test/auth"}}, "event": [{"listen": "test", "script": {"exec": ['pm.environment.set("access_token", "x");']}}]},
            {"name": "Consumer", "request": {"method": "GET", "url": {"raw": "https://example.test/data"}, "header": [{"key": "Authorization", "value": "Bearer {{access_token}}"}]}}
        ]
        d = self.run_parser(c)
        self.assertEqual(d["summary"]["dependency_count"], 1)
        self.assertEqual(d["requests"][1]["headers"][0]["value"], "<REDACTED>")

    def test_unsupported_script(self):
        c = self.base()
        c["item"] = [{"name": "Get", "request": {"method": "GET", "url": {"raw": "https://example.test"}}, "event": [{"listen": "test", "script": {"exec": ['pm.sendRequest("https://example.test/other")']}}]}]
        d = self.run_parser(c)
        self.assertEqual(d["summary"]["unsupported_feature_count"], 1)

if __name__ == "__main__":
    unittest.main()
