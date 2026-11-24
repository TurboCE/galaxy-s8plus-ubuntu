"""Do not mistake startup junk or missing counters for usable desktop audio."""
import array
import importlib.machinery
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
    def test_stock_audio_requires_attestation_for_this_boot(self):
        loader = importlib.machinery.SourceFileLoader(
            'audio_launcher', str(path.with_name('g955n-wireplumber')))
        launcher_spec = importlib.util.spec_from_loader(loader.name, loader)
        launcher = importlib.util.module_from_spec(launcher_spec)
        loader.exec_module(launcher)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker, prop, boot = (root / name for name in ('marker', 'property', 'boot'))
            boot.write_text('current')
            with patch.multiple(launcher, KERNEL_SCOPE=marker, SCOPE_PROPERTY=prop, BOOT_ID=boot), \
                 patch.object(launcher, 'trusted_regular') as trusted:
                self.assertFalse(launcher.kernel_scope_active())
                marker.write_text('old')
                self.assertFalse(launcher.kernel_scope_active())
                prop.touch()
                self.assertFalse(launcher.kernel_scope_active())
                marker.write_text('current')
                self.assertTrue(launcher.kernel_scope_active())
                trusted.assert_called_with(marker)
                trusted.side_effect = ValueError('untrusted')
                with self.assertRaises(ValueError):
                    launcher.kernel_scope_active()

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

    def test_speaker_response_requires_the_expected_tone_order_and_timing(self):
        def recording(tones):
            values = [0] * (audio.RATE * 4)
            for start, frequency in tones:
                start = round(start * audio.RATE)
                for i in range(audio.RATE // 2):
                    values[start + i] = round(1000 * math.sin(2 * math.pi * frequency * i / audio.RATE))
            return audio.statistics(stereo(values))

        nominal = recording(((1.0, 523.25), (2.0, 697.0)))
        reversed_tones = recording(((1.0, 697.0), (2.0, 523.25)))
        late = recording(((2.75, 523.25), (3.25, 697.0)))
        self.assertTrue(nominal['synthetic_tone_response_detected'])
        self.assertFalse(reversed_tones['synthetic_tone_response_detected'])
        self.assertFalse(late['synthetic_tone_response_detected'])

    def test_capture_status_follows_the_actual_alsa_card(self):
        for native, card, capture_device in [
                (False, 'Exynos8895-Madera', 9), (True, 'SM-G955N Audio', 1)]:
            with self.subTest(card=card):
                playback = f'{card}\nalsa.device = "0"\nmedia.class = "Audio/Sink"'
                capture = f'{card}\nalsa.device = "{capture_device}"\nmedia.class = "Audio/Source"'
                if native:
                    playback += '\napi.alsa.open.ucm = "true"\napi.alsa.path = "hw:Audio,0"'
                    capture += f'\napi.alsa.open.ucm = "true"\napi.alsa.path = "hw:Audio,{capture_device}"'
                with patch.object(audio, 'command', side_effect=[playback, capture]):
                    self.assertEqual(audio.default_audio_devices(native)['capture'],
                                     Path(f'/proc/asound/card0/pcm{capture_device}c/sub0/status'))
                with patch.object(audio, 'command', side_effect=[playback, capture.replace(
                        f'alsa.device = "{capture_device}"', 'alsa.device = "2"')]):
                    with self.assertRaisesRegex(RuntimeError, 'Default capture'):
                        audio.default_audio_devices(native)

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
