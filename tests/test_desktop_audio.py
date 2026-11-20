"""Do not mistake startup junk or missing counters for usable desktop audio."""
import array
import importlib.util
import math
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'compat/pipewire/check-desktop-audio.py'
spec = importlib.util.spec_from_file_location('desktop_audio', path)
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def stereo(values):
    samples = array.array('h', (x for value in values for x in (value, value)))
    if audio.os.sys.byteorder != 'little':
        samples.byteswap()
    return samples.tobytes()


class DesktopAudioTests(unittest.TestCase):
    def test_startup_clipping_does_not_become_a_live_microphone(self):
        raw = stereo([32767] * 12000 + [0] * 48000)
        result = audio.statistics(raw)
        self.assertEqual(result['startup_clipped_samples'], 12000)
        self.assertFalse(result['nonconstant_signal'])
        self.assertEqual(result['clipped_samples'], 0)

    def test_expected_tone_is_measured_after_startup(self):
        values = [0] * 12000 + [round(1000 * math.sin(2 * math.pi * 697 * i / 48000))
                               for i in range(48000)]
        result = audio.statistics(stereo(values))
        self.assertTrue(result['nonconstant_signal'])
        self.assertEqual(result['frames'], 48000)
        for low, high in result['quarter_second_tone_amplitudes']:
            self.assertLess(low, 15)
            self.assertGreater(high, 990)

    def test_internal_hardware_errors_are_separate_from_client_errors(self):
        rows = '\n'.join([
            'R 49 2048 48000 1us 1us 0.00 0.00 2 S16LE 2 48000 alsa_output.platform-sound',
            'R 99 4800 48000 1us 1us 0.00 0.00 50 S16LE 2 48000 + pw-play',
            'R 49 2048 48000 1us 1us 0.00 0.00 5 S16LE 2 48000 alsa_output.platform-sound',
            'S 37 0 0 --- --- --- --- 0 alsa_input.platform-sound',
            'R 37 2048 48000 1us 1us 0.00 0.00 0 S16LE 2 48000 alsa_input.platform-sound',
        ])
        self.assertEqual(audio.hardware_error_samples(rows), {'sink': [2, 5], 'source': [0]})
        self.assertEqual(audio.hardware_error_samples(''), {'sink': [], 'source': []})


if __name__ == '__main__':
    unittest.main()
