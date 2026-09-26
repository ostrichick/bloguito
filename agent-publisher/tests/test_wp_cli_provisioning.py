import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "wordpress" / "provision-wp-cli.sh"
COMPOSE = ROOT / "wordpress" / "docker-compose.yml"


class WpCliProvisioningTests(unittest.TestCase):
    def test_provisioner_is_version_and_checksum_pinned(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('WP_CLI_VERSION="2.12.0"', text)
        match = re.search(r'WP_CLI_SHA256="([0-9a-f]{64})"', text)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.group(1),
            "ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c",
        )
        self.assertIn("releases/download/v${WP_CLI_VERSION}/wp-cli-${WP_CLI_VERSION}.phar", text)
        self.assertNotIn("/releases/latest/", text)

    def test_provisioner_fails_closed_before_atomic_install(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('downloaded_sha="$(sha256sum', text)
        self.assertIn('if [ "$downloaded_sha" != "$WP_CLI_SHA256" ]', text)
        self.assertIn('mktemp "${destination_dir}/.wp-cli-${WP_CLI_VERSION}.XXXXXX"', text)
        self.assertIn('mv -f -- "$temporary" "$DESTINATION"', text)

    def test_compose_mounts_the_provisioned_phar_read_only(self):
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("./wp-cli.phar:/usr/local/bin/wp:ro", text)


if __name__ == "__main__":
    unittest.main()
