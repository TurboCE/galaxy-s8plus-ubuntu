"""Check power-key blanking, lock confirmation, and wake behavior."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'compat/suspend/g955n-power-key.py'
spec=importlib.util.spec_from_file_location('power_key',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class PowerKeyDisplayTests(unittest.TestCase):
    def test_late_decon_connector_takes_over_panel_state(self):
        with tempfile.TemporaryDirectory() as directory:
            drm = Path(directory)
            fallback = drm / 'runtime_status'
            fallback.write_text('active\n')
            with patch.object(m, 'Path', return_value=drm), \
                 patch.object(m, 'PANEL_RUNTIME', fallback):
                self.assertTrue(m.panel_is_on())
                connector = drm / 'card2-DSI-1'
                device = connector / 'device/device'
                device.mkdir(parents=True)
                driver = drm / 'g955n-decon-handoff'
                driver.mkdir()
                (device / 'driver').symlink_to(driver)
                enabled = connector / 'enabled'
                enabled.write_text('disabled\n')
                self.assertFalse(m.panel_is_on())
                enabled.write_text('enabled\n')
                dpms = connector / 'dpms'
                dpms.write_text('Off\n')
                self.assertFalse(m.panel_is_on())
                dpms.write_text('On\n')
                self.assertTrue(m.panel_is_on())

    def test_panel_read_failure_restores_display(self):
        with patch.object(m, 'lock_before_blank'), \
             patch.object(m, 'panel_is_on', side_effect=FileNotFoundError('panel')), \
             patch.object(m, 'read_command') as command, \
             patch.object(m, 'wake_display') as wake:
            with self.assertRaisesRegex(FileNotFoundError, 'panel'):
                m.blank_display(('c4', 'wayland', ['user']))
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.args[-3:], ('PowerSaveMode', 'i', '3'))
        wake.assert_called_once()

    def test_wake_resets_idle_before_powering_panel(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a:calls.append(a)), \
             patch.object(m,'wait_for_panel') as wait, \
             patch.object(m,'SLEEP_MARKER') as marker:
            m.wake_display(('c4','x11',['user']))
        self.assertEqual(calls[0][-3:],('/usr/bin/xset','s','reset'))
        self.assertEqual(calls[1][-4:],('/usr/bin/xset','dpms','force','on'))
        wait.assert_called_once_with(on=True)
        marker.unlink.assert_called_once_with(missing_ok=True)

    def test_wayland_keeps_resume_marker_until_panel_wakes(self):
        session = ('c4', 'wayland', ['user'])
        with patch.object(m, 'SLEEP_MARKER') as marker, \
             patch.object(m, 'read_command') as command, \
             patch.object(m, 'panel_is_on', return_value=False), \
             patch.object(m.time, 'monotonic', side_effect=[0, 3]):
            with self.assertRaisesRegex(RuntimeError, 'Panel did not turn on'):
                m.wake_display(session)
        self.assertEqual(command.call_args.args[-3:], ('PowerSaveMode', 'i', '0'))
        marker.unlink.assert_not_called()

    def test_x11_locks_and_blanks_without_requesting_sleep(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'lock_before_blank',side_effect=lambda s:calls.append(('lock',))), \
             patch.object(m,'panel_is_on',return_value=False):
            m.blank_display(('c4','x11',['user']))
        self.assertEqual(calls[0],('lock',))
        self.assertEqual(calls[1][-4:],('/usr/bin/xset','dpms','force','off'))
        self.assertEqual(len(calls), 2)

    def test_failed_blanking_does_not_request_sleep(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'lock_before_blank'), \
             patch.object(m,'panel_is_on',return_value=True), \
             patch.object(m.time,'monotonic',side_effect=[0,3]),patch.object(m,'wake_display'):
            with self.assertRaises(RuntimeError):m.blank_display(('c4','x11',['user']))
        self.assertEqual(len(calls), 1)

    def test_lock_failure_does_not_blank_or_suspend(self):
        calls=[]
        with patch.object(m,'lock_before_blank',side_effect=RuntimeError('Not locked')), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'wake_display') as wake:
            with self.assertRaises(RuntimeError):m.blank_display(('c4','x11',['user']))
        self.assertEqual(calls,[])
        wake.assert_called_once()

    def test_lock_completes_before_blanking_and_honors_setting(self):
        answers=iter(('true','false','user',''))
        calls=[]
        def command(*args,**kwargs):calls.append(args);return next(answers)
        with patch.object(m,'read_command',side_effect=command), \
             patch.object(m,'session_locked',side_effect=[False,True]):
            m.lock_before_blank(('c4','x11',['user']))
        self.assertEqual(calls[-1],('/usr/bin/loginctl','lock-session','c4'))
        with patch.object(m,'read_command',return_value='false') as command:
            m.lock_before_blank(('c4','x11',['user']))
        self.assertEqual(command.call_count,1)


    def test_greeter_does_not_wait_for_lock_confirmation(self):
        with patch.object(m, 'read_command', side_effect=['true', 'false', 'greeter']) as command, \
             patch.object(m, 'session_locked', return_value=False):
            m.lock_before_blank(('c4', 'wayland', ['user']))
        self.assertEqual(command.call_count, 3)

    def test_already_locked_does_not_wait_for_screensaver_activation(self):
        with patch.object(m,'read_command',side_effect=['true','false']) as command, \
             patch.object(m,'session_locked',return_value=True):
            m.lock_before_blank(('c4','x11',['user']))
        self.assertEqual(command.call_count,2)

    def test_lock_request_repeats_until_gnome_reports_locked(self):
        with patch.object(m, 'read_command', side_effect=['true', 'false', 'user', '', '']) as command, \
             patch.object(m, 'session_locked', side_effect=[False, False, False, True]), \
             patch.object(m.time, 'monotonic', side_effect=[0, 0.1, 1.1]), \
             patch.object(m.time, 'sleep'):
            m.lock_before_blank(('c4', 'wayland', ['user']))
        requests = [call.args for call in command.call_args_list
                    if call.args[:2] == ('/usr/bin/loginctl', 'lock-session')]
        self.assertEqual(requests, [('/usr/bin/loginctl', 'lock-session', 'c4')] * 2)

    def test_locked_wayland_resume_uses_first_short_press_to_wake(self):
        session = ('c4', 'wayland', ['user'])
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'resume'
            marker.write_text('42\n')
            with patch.object(m, 'SLEEP_MARKER', marker), \
                 patch.object(m, 'session_locked', side_effect=[True, False]), \
                 patch.object(m, 'read_command'), \
                 patch.object(m, 'wait_for_panel'):
                self.assertFalse(m.should_blank(session, True))
                self.assertTrue(m.should_blank(session, True))
                m.wake_display(session)
                self.assertTrue(m.should_blank(session, True))
                self.assertFalse(m.should_blank(session, False))


if __name__=='__main__':unittest.main()
