#!/usr/bin/env python3
"""Repository Structure and Installation Contract Tests for Crypto Trader."""

import json
import os
import re
import unittest

from _load import ROOT

SKILLS = [
    "crypto-scanner",
    "crypto-news",
    "crypto-entry",
    "crypto-exit",
    "crypto-timemachine",
    "crypto-budget",
    "crypto-risk",
    "crypto-broker",
    "crypto-alerts",
    "crypto-analyst",
    "crypto-whale",
]


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.group(1) if m else ""), text


class TestRepo(unittest.TestCase):
    def test_eleven_skill_folders_at_the_root(self):
        found = sorted(
            d for d in os.listdir(ROOT)
            if os.path.isfile(os.path.join(ROOT, d, "SKILL.md"))
        )
        self.assertEqual(found, sorted(SKILLS))

    def test_frontmatter_name_and_description(self):
        for s in SKILLS:
            fm, text = frontmatter(os.path.join(ROOT, s, "SKILL.md"))
            self.assertIn(f"name: {s}\n", fm + "\n", s)
            self.assertIn("description:", fm, s)
            self.assertGreater(len(fm), 100, f"{s} description too short")
            self.assertGreater(len(text.splitlines()), 20, s)

    def test_skill_dir_variable_used(self):
        for s in SKILLS:
            _, text = frontmatter(os.path.join(ROOT, s, "SKILL.md"))
            self.assertIn("${CLAUDE_SKILL_DIR}", text, f"{s} missing CLAUDE_SKILL_DIR")

    def test_plugin_manifests(self):
        plugin_path = os.path.join(ROOT, ".claude-plugin", "plugin.json")
        with open(plugin_path, encoding="utf-8") as fh:
            plugin = json.load(fh)
        self.assertEqual(plugin["name"], "crypto-trader-skill")
        self.assertEqual(plugin["skills"], "./")

        market_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
        with open(market_path, encoding="utf-8") as fh:
            market = json.load(fh)
        self.assertEqual(market["name"], "crypto-trader-skill")
        self.assertEqual(market["plugins"][0]["source"], "./")

    def test_installer_exists(self):
        installer = os.path.join(ROOT, "install.py")
        self.assertTrue(os.path.isfile(installer))

    def test_readme_contains_single_prompt_installation(self):
        readme_path = os.path.join(ROOT, "README.md")
        with open(readme_path, encoding="utf-8") as fh:
            readme = " ".join(fh.read().split())
        self.assertIn("https://github.com/Yashaswirai/crypto-trader-skill install skill", readme)
        self.assertIn("/plugin marketplace add Yashaswirai/crypto-trader-skill", readme)
        self.assertIn("/plugin install crypto-trader-skill@crypto-trader-skill", readme)


if __name__ == "__main__":
    unittest.main()
