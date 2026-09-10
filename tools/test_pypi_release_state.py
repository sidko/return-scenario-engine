import importlib.util
import io
import json
import os
import runpy
import tempfile
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


SCRIPTS = [
    Path(__file__).with_name('pypi_release_state.py'),
    Path(__file__).parents[2] / 'financial-series-boundaries/tools/pypi_release_state.py',
    Path(__file__).parents[2] / 'duckdb-safe-snapshot/tools/pypi_release_state.py',
]


class ReleaseStateTest(unittest.TestCase):
    def test_ignores_json_and_rejects_partial_postcheck(self):
        for script in SCRIPTS:
            with tempfile.TemporaryDirectory() as temp:
                dist = Path(temp) / 'dist'; dist.mkdir(); output = Path(temp) / 'out'
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, 'w') as wheel: wheel.writestr('pkg.py', 'same')
                (dist / 'package.whl').write_bytes(archive.getvalue())
                (dist / 'metadata.json').write_text('{}')
                old_env, old_open = os.environ.copy(), urllib.request.urlopen
                os.environ.update({'DIST_DIR': str(dist), 'PYPI_PACKAGE': 'x', 'PYPI_VERSION': 'v1', 'MODE': 'pre', 'GITHUB_OUTPUT': str(output)})
                urllib.request.urlopen = lambda url: (_ for _ in ()).throw(urllib.error.HTTPError(str(url), 404, 'missing', None, None))
                try:
                    runpy.run_path(str(script), run_name='__main__')
                    self.assertIn('state=publish', output.read_text())
                finally:
                    urllib.request.urlopen = old_open; os.environ.clear(); os.environ.update(old_env)


if __name__ == '__main__': unittest.main()
