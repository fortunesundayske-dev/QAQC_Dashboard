import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.create_streamlit_secrets import create_secrets


class StreamlitSecretsTests(unittest.TestCase):
    def test_generator_creates_valid_toml_and_preserves_local_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env_path = root / ".env"
            output_path = root / ".streamlit" / "secrets.toml"
            env_path.write_text(
                "MONGODB_URI=mongodb://developer:password@example.invalid/qaqc\n"
                "QAQC_EXCHANGE_SENDER=fortune.kpakue@evomeclimited.com\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                missing = create_secrets(env_path, output_path)
                with output_path.open("rb") as stream:
                    generated = tomllib.load(stream)

                self.assertEqual(
                    generated["MONGODB_URI"],
                    "mongodb://developer:password@example.invalid/qaqc",
                )
                self.assertEqual(
                    generated["QAQC_EXCHANGE_SENDER"],
                    "fortune.kpakue@evomeclimited.com",
                )
                self.assertIn("QAQC_EXCHANGE_CLIENT_SECRET", missing)

                text = output_path.read_text(encoding="utf-8").replace(
                    'QAQC_EXCHANGE_CLIENT_ID = ""',
                    'QAQC_EXCHANGE_CLIENT_ID = "locally-entered-client-id"',
                )
                output_path.write_text(text, encoding="utf-8")

                create_secrets(env_path, output_path)
                with output_path.open("rb") as stream:
                    regenerated = tomllib.load(stream)
                self.assertEqual(
                    regenerated["QAQC_EXCHANGE_CLIENT_ID"],
                    "locally-entered-client-id",
                )


if __name__ == "__main__":
    unittest.main()
