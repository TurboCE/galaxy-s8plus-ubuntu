"""Never suspend a visibly active panel; restore it after a rejected request."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'compat/suspend/g955n-power-key.py'
spec=importlib.util.spec_from_file_location('power_key',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class PowerKeySuspendTests(unittest.TestCase):
    def test_decon_panel_follows_connector_blanking(self):
        m.panel_state.cache_clear()
        self.addCleanup(m.panel_state.cache_clear)
        with tempfile.TemporaryDirectory() as directory:
            drm = Path(directory)
            connector = drm / 'card2-DSI-1'
            device = connector / 'device/device'
            device.mkdir(parents=True)
            driver = drm / 'g955n-decon-handoff'
            driver.mkdir()
            (device / 'driver').symlink_to(driver)
            enabled = connector / 'enabled'
            with patch.object(m, 'Path', return_value=drm):
                enabled.write_text('enabled\n')
                self.assertTrue(m.panel_is_on())
                enabled.write_text('disabled\n')
                self.assertFalse(m.panel_is_on())

    def test_wake_resets_idle_before_powering_panel(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a:calls.append(a)):
            m.wake_display(('c4','x11',['user']))
        self.assertEqual(calls[0][-3:],('/usr/bin/xset','s','reset'))
        self.assertEqual(calls[1][-4:],('/usr/bin/xset','dpms','force','on'))

    def test_x11_blanks_before_requesting_sleep(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'lock_before_sleep',side_effect=lambda s:calls.append(('lock',))), \
             patch.object(m,'panel_is_on',return_value=False):
            m.suspend_session(('c4','x11',['user']))
        self.assertEqual(calls[0],('lock',))
        self.assertEqual(calls[1][-4:],('/usr/bin/xset','dpms','force','off'))
        self.assertEqual(calls[2],m.LOGIND_SUSPEND)

    def test_failed_sleep_restores_display(self):
        def command(*args,**kwargs):
            if args==m.LOGIND_SUSPEND:raise subprocess.CalledProcessError(1,args)
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=command), \
             patch.object(m,'lock_before_sleep'), \
             patch.object(m,'panel_is_on',return_value=False),patch.object(m,'wake_display') as wake:
            with self.assertRaises(subprocess.CalledProcessError):
                m.suspend_session(('c4','x11',['user']))
            wake.assert_called_once()

    def test_failed_blanking_does_not_request_sleep(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'lock_before_sleep'), \
             patch.object(m,'panel_is_on',return_value=True), \
             patch.object(m.time,'monotonic',side_effect=[0,3]),patch.object(m,'wake_display'):
            with self.assertRaises(RuntimeError):m.suspend_session(('c4','x11',['user']))
        self.assertNotIn(m.LOGIND_SUSPEND,calls)

    def test_lock_failure_does_not_blank_or_suspend(self):
        calls=[]
        with patch.object(m,'lock_before_sleep',side_effect=RuntimeError('Not locked')), \
             patch.object(m,'read_command',side_effect=lambda *a,**kw:calls.append(a)), \
             patch.object(m,'wake_display') as wake:
            with self.assertRaises(RuntimeError):m.suspend_session(('c4','x11',['user']))
        self.assertEqual(calls,[])
        wake.assert_called_once()

    def test_lock_completes_before_sleep_and_honors_setting(self):
        answers=iter(('true','false',''))
        calls=[]
        def command(*args,**kwargs):calls.append(args);return next(answers)
        with patch.object(m,'read_command',side_effect=command), \
             patch.object(m,'session_locked',side_effect=[False,True]):
            m.lock_before_sleep(('c4','x11',['user']))
        self.assertEqual(calls[-1],('/usr/bin/loginctl','lock-session','c4'))
        with patch.object(m,'read_command',return_value='false') as command:
            m.lock_before_sleep(('c4','x11',['user']))
        self.assertEqual(command.call_count,1)

    def test_already_locked_does_not_wait_for_screensaver_activation(self):
        with patch.object(m,'read_command',side_effect=['true','false']) as command, \
             patch.object(m,'session_locked',return_value=True):
            m.lock_before_sleep(('c4','x11',['user']))
        self.assertEqual(command.call_count,2)


if __name__=='__main__':unittest.main()
