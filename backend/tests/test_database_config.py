"""Configuration checks isolated from app imports and its test database."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DatabaseConfigTests(unittest.TestCase):
    def read_config(self, url=None, render=False):
        env = dict(os.environ)
        env.pop("DATABASE_URL", None)
        env.pop("RENDER", None)
        if url is not None:
            env["DATABASE_URL"] = url
        if render:
            env["RENDER"] = "true"
        return subprocess.run(
            [sys.executable, "-c",
             "from backend.config import DATABASE_URL; print(DATABASE_URL)"],
            cwd=ROOT, env=env, text=True, capture_output=True, check=True,
        )

    def test_provider_urls_keep_credentials_and_ssl_options(self):
        for scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
            with self.subTest(scheme=scheme):
                result = self.read_config(
                    f"  {scheme}://user:p%40ss@host/db?sslmode=require  ", True)
                self.assertEqual(result.stdout.strip(),
                    "postgresql+psycopg2://user:p%40ss@host/db?sslmode=require")
                self.assertEqual(result.stderr, "")

    def test_local_default_and_blank_value(self):
        for value in (None, "   "):
            result = self.read_config(value)
            self.assertTrue(result.stdout.strip().startswith("sqlite:///"))
            self.assertEqual(result.stderr, "")

    def test_render_warns_about_ephemeral_accounts(self):
        for value in (None, "sqlite:///example.db"):
            result = self.read_config(value, True)
            self.assertIn("lose accounts and sessions", result.stderr)


if __name__ == "__main__":
    unittest.main()
