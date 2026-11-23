"""Verify the retained transport sampler stops after its boot-time window."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


SAMPLER = (
    Path(__file__).resolve().parents[1] / "scripts/boot/mainline618-transport-evidence.sh"
)


class TransportEvidenceTests(unittest.TestCase):
    def run_sampler(self, elapsed_per_sleep):
        with TemporaryDirectory() as directory:
            fixture = Path(directory)
            clock = fixture / "uptime"
            records = fixture / "pmsg"
            clock.write_text("10.50 0.00\n")

            script = (
                SAMPLER.read_text()
                .replace("/proc/uptime", '"$1/uptime"')
                .replace("/dev/pmsg0", '"$1/pmsg"')
                .replace("/sys/class/", '"$1"/sys/class/')
                .replace(
                    "sleep 5",
                    'printf "%s.50 0.00\\n" "$((${uptime%%.*} + $2))" > "$1/uptime"',
                )
            )
            subprocess.run(
                ["sh", "-s", "--", directory, str(elapsed_per_sleep)],
                input=script,
                text=True,
                check=True,
                timeout=10,
            )
            return records.read_text().splitlines()

    def test_unsuspended_sampling_respects_record_limit(self):
        records = self.run_sampler(5)
        self.assertEqual(len(records), 122)
        self.assertEqual(records[-1], "G955N TRANSPORT END samples=60")

    def test_suspend_time_counts_against_the_sampling_window(self):
        records = self.run_sampler(155)
        heartbeats = [line for line in records if " HEARTBEAT " in line]
        self.assertEqual(
            heartbeats,
            [
                "G955N TRANSPORT HEARTBEAT uptime=10.50",
                "G955N TRANSPORT HEARTBEAT uptime=165.50",
            ],
        )
        self.assertEqual(records[-1], "G955N TRANSPORT END samples=2")
