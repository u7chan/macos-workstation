"""小さなオフラインアーカイブと実際のchezmoiで、フォント定義の適用を確認する。

アーカイブ内のファイル選別・繰り返し適用・チェックサム検証を行う。
macOSでのフォント認識や描画は対象外とし、別途実機で確認する。
"""

import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import unittest


HOME_SOURCE = Path(__file__).resolve().parents[1] / "home"
CHEZMOI = shutil.which("chezmoi")
FONT_FILES = {
    f"MesloLGMNerdFont-{style}.ttf": f"fixture {style}\n".encode()
    for style in ("Regular", "Bold", "Italic", "BoldItalic")
}
MANAGED_FILES = {**FONT_FILES, "LICENSE.txt": b"fixture license\n"}


@unittest.skipUnless(CHEZMOI, "chezmoi is required for font integration tests")
class FontTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="font test ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.source = self.root / "source"
        self.home.mkdir()
        self.source.mkdir()
        self.declaration = (HOME_SOURCE / ".chezmoiexternal.toml").read_text()
        declarations = tomllib.loads(self.declaration)
        self.assertEqual(len(declarations), 1)
        destination, self.settings = next(iter(declarations.items()))
        self.target = self.home / destination
        self.archive = self.root / "fonts.tar.xz"
        archive_files = {
            **MANAGED_FILES,
            "MesloLGMNerdFontMono-Regular.ttf": b"mono variant\n",
            "MesloLGMNerdFontPropo-Regular.ttf": b"proportional variant\n",
            "MesloLGMDZNerdFont-Regular.ttf": b"dotted zero variant\n",
            "MesloLGSNerdFont-Regular.ttf": b"different line spacing\n",
            "README.md": b"upstream documentation\n",
        }
        with tarfile.open(self.archive, "w:xz") as archive:
            for name, data in archive_files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
        self.write_declaration()
        self.config = self.root / "chezmoi.toml"
        self.config.write_text("")

    def write_declaration(self, checksum=None):
        checksum = checksum or hashlib.sha256(self.archive.read_bytes()).hexdigest()
        fixture = self.declaration.replace(self.settings["url"], self.archive.as_uri())
        fixture = fixture.replace(self.settings["checksum"]["sha256"], checksum)
        (self.source / ".chezmoiexternal.toml").write_text(fixture)

    def apply(self):
        return subprocess.run(
            [
                CHEZMOI, "--source", str(self.source),
                "--destination", str(self.home), "--config", str(self.config),
                "--cache", str(self.root / "cache"),
                "--persistent-state", str(self.root / "state.boltdb"),
                "apply", "--force", "--no-tty",
            ],
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True, text=True, check=False,
        )

    def assert_applied(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, data in MANAGED_FILES.items():
            self.assertEqual((self.target / name).read_bytes(), data)

    def test_selects_only_declared_faces_and_license_without_removing_other_fonts(self):
        self.target.mkdir(parents=True)
        unrelated = self.target.parent / "Unrelated.ttf"
        unrelated.write_bytes(b"unrelated font\n")
        extra = self.target / "Custom.ttf"
        extra.write_bytes(b"user-added font\n")
        self.assert_applied()
        self.assertEqual(
            {path.name for path in self.target.iterdir()},
            set(MANAGED_FILES) | {extra.name},
        )
        mtimes = {path: path.stat().st_mtime_ns for path in self.target.iterdir()}
        self.assert_applied()
        self.assertEqual(
            {path: path.stat().st_mtime_ns for path in self.target.iterdir()}, mtimes,
        )
        self.assertEqual(unrelated.read_bytes(), b"unrelated font\n")
        self.assertEqual(extra.read_bytes(), b"user-added font\n")

    def test_repairs_missing_and_modified_managed_fonts(self):
        self.assert_applied()
        regular = self.target / "MesloLGMNerdFont-Regular.ttf"
        bold = self.target / "MesloLGMNerdFont-Bold.ttf"
        regular.write_bytes(b"modified font\n")
        bold.unlink()
        self.assert_applied()

    def test_checksum_mismatch_stops_without_replacing_existing_font(self):
        self.target.mkdir(parents=True)
        existing = self.target / "MesloLGMNerdFont-Regular.ttf"
        existing.write_bytes(b"existing font\n")
        self.write_declaration(checksum="0" * 64)
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256 mismatch", result.stderr.lower())
        self.assertEqual(existing.read_bytes(), b"existing font\n")
        self.assertEqual(list(self.target.iterdir()), [existing])


if __name__ == "__main__":
    unittest.main()
