import unittest
from pathlib import Path
from unittest import mock

from ctfcli.cli.challenges import ChallengeCommand


class TestCLIChallengesCommand(unittest.TestCase):
    @mock.patch("ctfcli.cli.challenges.Config")
    @mock.patch("ctfcli.cli.challenges.Challenge.load_installed_challenges", return_value=[])
    @mock.patch("ctfcli.cli.challenges.ChallengeCommand._resolve_single_challenge")
    def test_install_passes_ignore_lfs_to_create(self, mock_resolve_single, _mock_load_remote, _mock_config):
        challenge_instance = mock.MagicMock()
        challenge_instance.__getitem__.side_effect = lambda key: "LFS Challenge" if key == "name" else None
        challenge_instance.challenge_file_path = Path("challenge.yml")
        mock_resolve_single.return_value = challenge_instance

        status = ChallengeCommand().install(challenge="dummy", ignore="lfs")

        self.assertEqual(status, 0)
        challenge_instance.create.assert_called_once_with(ignore=("lfs",))

    @mock.patch("ctfcli.cli.challenges.Config")
    @mock.patch("ctfcli.cli.challenges.Challenge.load_installed_challenges", return_value=[{"name": "LFS Challenge"}])
    @mock.patch("ctfcli.cli.challenges.ChallengeCommand._resolve_single_challenge")
    def test_sync_passes_ignore_lfs_to_sync(self, mock_resolve_single, _mock_load_remote, _mock_config):
        challenge_instance = mock.MagicMock()
        challenge_instance.__getitem__.side_effect = lambda key: "LFS Challenge" if key == "name" else None
        challenge_instance.challenge_file_path = Path("challenge.yml")
        mock_resolve_single.return_value = challenge_instance

        status = ChallengeCommand().sync(challenge="dummy", ignore="lfs")

        self.assertEqual(status, 0)
        challenge_instance.sync.assert_called_once_with(ignore=("lfs",))
