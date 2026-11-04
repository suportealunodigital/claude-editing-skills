"""Offline checks for discovery, symlink safety and shared-kit resolution."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'trial-reels', 'behind-the-person', 'explainer', 'split-screen',
         'ranking-list', 'storytelling', 'shape-shift', 'picture-stack',
         'scene-switch', 'visual-notes', 'orbit-reel'}

class CodexSkills(unittest.TestCase):
    def test_catalog_and_metadata(self):
        entries = list((ROOT / '.agents/skills').iterdir())
        self.assertEqual({p.name for p in entries}, NAMES)
        for entry in entries:
            with self.subTest(skill=entry.name):
                self.assertTrue(entry.is_symlink())
                self.assertEqual(entry.resolve(), ROOT / 'skills' / entry.name)
                content = (entry / 'SKILL.md').read_text()
                self.assertTrue(content.startswith('---\n'))
                self.assertRegex(content, rf'\nname: {re.escape(entry.name)}\n')
                self.assertRegex(content, r'\ndescription: .+\n---\n')
                self.assertIn('$' + entry.name, content)
                self.assertIn('$' + entry.name, (ROOT / 'AGENTS.md').read_text())
                self.assertTrue((entry / 'build.py').is_file())

    def test_installer_idempotence_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'checkout with spaces'
            root.mkdir()
            shutil.copy(ROOT / 'install-codex.sh', root)
            for name in NAMES:
                folder = root / 'skills' / name
                folder.mkdir(parents=True)
                (folder / 'SKILL.md').write_text('test')
            cmd = ['bash', str(root / 'install-codex.sh'), '--skip-setup']
            for _ in range(2):
                subprocess.run(cmd, check=True, capture_output=True)
            self.assertFalse((root / 'kit/.venv').exists())
            for name in NAMES:
                self.assertEqual((root / '.agents/skills' / name).resolve(), root / 'skills' / name)
            collision = root / '.agents/skills/explainer'
            collision.unlink()
            collision.mkdir()
            (collision / 'keep').write_text('user data')
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual((collision / 'keep').read_text(), 'user data')
            self.assertNotEqual(subprocess.run(['bash', str(root / 'install-codex.sh'), '--bad'], capture_output=True).returncode, 0)

    def test_original_claude_installer_still_links_all_skills(self):
        # Stub setup only to check installer wiring without network/install side effects.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(ROOT / 'install.sh', root)
            (root / 'kit').mkdir()
            (root / 'kit/setup.sh').write_text('printf "%s" "$1" > "$(dirname "$0")/received"\n')
            for name in NAMES:
                (root / 'skills' / name).mkdir(parents=True)
            env = dict(os.environ, CLAUDE_SKILLS_DIR=str(root / 'claude skills'))
            subprocess.run(['bash', str(root / 'install.sh'), '--cutout'], env=env, check=True, capture_output=True)
            self.assertEqual((root / 'kit/received').read_text(), '--cutout')
            for name in NAMES:
                self.assertEqual((root / 'claude skills' / name).resolve(), root / 'skills' / name)

    def test_documented_kit_resolution_through_symlink(self):
        for name in NAMES:
            content = (ROOT / 'skills' / name / 'SKILL.md').read_text()
            match = re.search(r"KIT=\$\(python3 -c '([^']+)'", content)
            if not match:
                continue  # photographic builders resolve __file__ themselves
            result = subprocess.check_output(['python3', '-c', match[1], str(ROOT / '.agents/skills' / name)], text=True).strip()
            self.assertEqual(Path(result), ROOT / 'kit')

    def test_builders_import_through_discovery_links(self):
        # run_name avoids rendering or executing each CLI's main block.
        for name in NAMES:
            subprocess.run(['python3', '-c', 'import runpy,sys; runpy.run_path(sys.argv[1],run_name="validation")',
                            str(ROOT / '.agents/skills' / name / 'build.py')], check=True)

if __name__ == '__main__':
    unittest.main()
