import io
import json
import os
import runpy
import tarfile
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch


CHECKER = Path(__file__).with_name("pypi_release_state.py")


def wheel(timestamp, contents=b"same contents"):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(zipfile.ZipInfo("package/__init__.py", timestamp), contents)
    return raw.getvalue()


def source(timestamp):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        member = tarfile.TarInfo("package-1.0/package/__init__.py")
        member.size, member.mtime = len(b"same contents"), timestamp
        archive.addfile(member, io.BytesIO(b"same contents"))
    return raw.getvalue()


class ReleaseStateTest(unittest.TestCase):
    def run_checker(self, local_files, remote_files, mode="pre"):
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp) / "dist"
            dist.mkdir()
            for name, contents in local_files.items():
                (dist / name).write_bytes(contents)
            output = Path(temp) / "output"

            def urlopen(url):
                url = str(url)
                if url.startswith("https://pypi.org/"):
                    if not remote_files:
                        error = urllib.error.HTTPError(url, 404, "missing", None, None)
                        error.close()
                        raise error
                    return io.BytesIO(json.dumps({"urls": [
                        {"filename": name, "url": f"https://files.example/{name}"}
                        for name in remote_files
                    ]}).encode())
                return io.BytesIO(remote_files[url.rsplit("/", 1)[-1]])

            environment = {
                "DIST_DIR": str(dist), "PYPI_PACKAGE": "package",
                "PYPI_VERSION": "v1.0", "MODE": mode,
                "GITHUB_OUTPUT": str(output),
            }
            with patch.dict(os.environ, environment, clear=True), patch(
                "urllib.request.urlopen", side_effect=urlopen
            ), patch("time.sleep") as sleep:
                try:
                    runpy.run_path(str(CHECKER), run_name="__main__")
                except SystemExit as error:
                    return None, str(error), sleep.call_args_list
            return output.read_text(), None, sleep.call_args_list

    def test_precheck_ignores_json_and_reports_publish_or_skip(self):
        artifact = wheel((2020, 1, 1, 0, 0, 0))
        local = {"package.whl": artifact, "attestation.json": b"{}"}
        for remote, expected in (({}, "publish"), ({"package.whl": artifact}, "skip")):
            with self.subTest(remote=remote):
                output, error, _ = self.run_checker(local, remote)
                self.assertIsNone(error)
                self.assertEqual(output, f"state={expected}\n")

    def test_precheck_reports_publish_for_matching_partial_remote(self):
        wheel_file = wheel((2020, 1, 1, 0, 0, 0))
        output, error, _ = self.run_checker(
            {"package.whl": wheel_file, "package.tar.gz": source(1)},
            {"package.whl": wheel_file},
        )
        self.assertIsNone(error)
        self.assertEqual(output, "state=publish\n")

    def test_rejects_remote_artifact_with_different_contents(self):
        output, error, _ = self.run_checker(
            {"package.whl": wheel((2020, 1, 1, 0, 0, 0))},
            {"package.whl": wheel((2021, 1, 1, 0, 0, 0), b"different")},
        )
        self.assertIsNone(output)
        self.assertEqual(error, "PyPI artifact content differs from this build")

    def test_postcheck_retries_partial_remote_then_fails(self):
        wheel_file = wheel((2020, 1, 1, 0, 0, 0))
        output, error, sleeps = self.run_checker(
            {"package.whl": wheel_file, "package.tar.gz": source(1)},
            {"package.whl": wheel_file}, mode="post",
        )
        self.assertIsNone(output)
        self.assertEqual(error, "PyPI upload did not become fully visible")
        self.assertEqual([call.args for call in sleeps], [(5,), (5,)])

    def test_accepts_matching_archives_with_different_container_timestamps(self):
        output, error, _ = self.run_checker(
            {"package.whl": wheel((2020, 1, 1, 0, 0, 0)), "package.tar.gz": source(1)},
            {"package.whl": wheel((2021, 1, 1, 0, 0, 0)), "package.tar.gz": source(2)},
        )
        self.assertIsNone(error)
        self.assertEqual(output, "state=skip\n")


if __name__ == "__main__":
    unittest.main()
