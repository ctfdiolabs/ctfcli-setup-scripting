import io
import unittest

from ctfcli.utils.hashing import hash_file


class TestHashFile(unittest.TestCase):
    def test_hash_file_sha1(self):
        fp = io.BytesIO(b"abc")
        self.assertEqual(hash_file(fp, "sha1"), "a9993e364706816aba3e25717850c26c9cd0d89d")

    def test_hash_file_sha256(self):
        fp = io.BytesIO(b"abc")
        self.assertEqual(
            hash_file(fp, "sha256"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_hash_file_unsupported_algorithm(self):
        fp = io.BytesIO(b"abc")
        with self.assertRaises(NotImplementedError):
            hash_file(fp, "md5")
