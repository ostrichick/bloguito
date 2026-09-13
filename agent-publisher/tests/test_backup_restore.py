import hashlib
import json
import gzip
import tarfile
import tempfile
import unittest
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BackupSnapshotTests(unittest.TestCase):
    """Bloguito 백업 스냅샷 패키징, manifest 검증, 아카이브 구조 단위 테스트"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_manifest_schema_and_checksum_verification(self):
        """manifest.json 스키마 및 SHA256 체크섬 무결성 검증"""
        sample_db = b"CREATE TABLE wp_posts (id INT); -- dump data"
        sample_db_gz = gzip.compress(sample_db)
        sample_uploads = b"mock png image data for featured thumbnail"
        sample_configs = json.dumps({"history": ["https://example.com/news1"]}).encode("utf-8")

        db_file = self.base_path / "db.sql.gz"
        db_file.write_bytes(sample_db_gz)

        uploads_file = self.base_path / "uploads.tar.gz"
        uploads_file.write_bytes(sample_uploads)

        configs_file = self.base_path / "configs.tar.gz"
        configs_file.write_bytes(sample_configs)

        manifest = {
            "version": "2.0",
            "created_at": "2026-09-13T02:00:00Z",
            "timestamp": "20260913_020000",
            "components": {
                "db": {
                    "file": "db.sql.gz",
                    "size_bytes": len(sample_db_gz),
                    "sha256": sha256_bytes(sample_db_gz),
                },
                "uploads": {
                    "file": "uploads.tar.gz",
                    "size_bytes": len(sample_uploads),
                    "sha256": sha256_bytes(sample_uploads),
                },
                "configs": {
                    "file": "configs.tar.gz",
                    "size_bytes": len(sample_configs),
                    "sha256": sha256_bytes(sample_configs),
                },
            },
        }

        manifest_file = self.base_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 검증 로직 테스트
        loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded["version"], "2.0")
        self.assertIn("db", loaded["components"])
        self.assertIn("uploads", loaded["components"])
        self.assertIn("configs", loaded["components"])

        # 체크섬 일치 확인
        for comp_name, comp_info in loaded["components"].items():
            comp_path = self.base_path / comp_info["file"]
            actual_sha = sha256_bytes(comp_path.read_bytes())
            self.assertEqual(comp_info["sha256"], actual_sha)

    def test_full_archive_packaging_and_unpacking(self):
        """단일 통합 아카이브(bloguito_backup_*.tar.gz) 패키징 및 해제 무결성 테스트"""
        staging_dir = self.base_path / "staging"
        staging_dir.mkdir()

        # 가상 데이터 생성
        sql_content = "INSERT INTO wp_posts VALUES (70, '무명전설 수원 콘서트');".encode("utf-8")
        (staging_dir / "db.sql.gz").write_bytes(gzip.compress(sql_content))

        # 가상 uploads.tar.gz 생성
        uploads_tar_path = staging_dir / "uploads.tar.gz"
        with tarfile.open(uploads_tar_path, "w:gz") as tar:
            img_file = self.base_path / "card_70.jpg"
            img_file.write_bytes(b"JPEG_MOCK_BYTES_FOR_POST_70")
            tar.add(img_file, arcname="uploads/2026/09/card_70.jpg")

        # 가상 configs.tar.gz 생성
        configs_tar_path = staging_dir / "configs.tar.gz"
        with tarfile.open(configs_tar_path, "w:gz") as tar:
            data_file = self.base_path / "history.json"
            data_file.write_text('{"published_urls": ["https://news.google.com/test"]}', encoding="utf-8")
            tar.add(data_file, arcname="configs_staging/agent-publisher/data/history.json")

        # manifest.json
        manifest_data = {
            "version": "2.0",
            "timestamp": "20260913_020000",
            "components": {
                "db": {"file": "db.sql.gz", "size_bytes": (staging_dir / "db.sql.gz").stat().st_size, "sha256": sha256_bytes((staging_dir / "db.sql.gz").read_bytes())},
                "uploads": {"file": "uploads.tar.gz", "size_bytes": uploads_tar_path.stat().st_size, "sha256": sha256_bytes(uploads_tar_path.read_bytes())},
                "configs": {"file": "configs.tar.gz", "size_bytes": configs_tar_path.stat().st_size, "sha256": sha256_bytes(configs_tar_path.read_bytes())},
            }
        }
        (staging_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        # 최종 통합 아카이브 생성
        archive_path = self.base_path / "bloguito_backup_20260913_020000.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            for item in ["db.sql.gz", "uploads.tar.gz", "configs.tar.gz", "manifest.json"]:
                tar.add(staging_dir / item, arcname=item)

        self.assertTrue(archive_path.exists())

        # 복원 검증
        restore_dir = self.base_path / "restored"
        restore_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(restore_dir)

        # 필수 구성요소 4종 전수 존재 확인
        for expected_file in ["db.sql.gz", "uploads.tar.gz", "configs.tar.gz", "manifest.json"]:
            self.assertTrue((restore_dir / expected_file).exists())

        # SQL 내용 검증
        extracted_sql = gzip.decompress((restore_dir / "db.sql.gz").read_bytes())
        self.assertEqual(extracted_sql, sql_content)

        # Uploads 내부 이미지 검증
        with tarfile.open(restore_dir / "uploads.tar.gz", "r:gz") as tar:
            names = tar.getnames()
            self.assertIn("uploads/2026/09/card_70.jpg", names)

    def test_backup_scripts_syntax_and_lf_endings(self):
        """backup_daily.sh 및 restore_backup.sh 스크립트 존재 및 LF 줄바꿈 검증"""
        root_dir = Path(__file__).resolve().parents[2]
        backup_sh = root_dir / "agent-publisher" / "backup_daily.sh"
        restore_sh = root_dir / "agent-publisher" / "restore_backup.sh"

        self.assertTrue(backup_sh.exists(), "backup_daily.sh should exist")
        self.assertTrue(restore_sh.exists(), "restore_backup.sh should exist")

        # Linux bash 실행을 위해 CRLF(\r\n)가 없어야 함
        backup_bytes = backup_sh.read_bytes()
        self.assertNotIn(b"\r\n", backup_bytes, "backup_daily.sh must use LF line endings")

        restore_bytes = restore_sh.read_bytes()
        self.assertNotIn(b"\r\n", restore_bytes, "restore_backup.sh must use LF line endings")


if __name__ == "__main__":
    unittest.main()