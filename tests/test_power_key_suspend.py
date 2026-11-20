"""Never suspend a visibly active panel; restore it after a rejected request."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'compat/suspend/g955n-power-key.py'
spec=importlib.util.spec_from_file_location('power_key',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class PowerKeySuspendTests(unittest.TestCase):
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
             patch.object(m,'read_command',side_effect=lambda *a:calls.append(a)), \
             patch.object(m,'panel_is_on',return_value=False):
            m.suspend_session(('c4','x11',['user']))
        self.assertEqual(calls[0][-4:],('/usr/bin/xset','dpms','force','off'))
        self.assertEqual(calls[1],('/usr/bin/systemctl','suspend'))

    def test_failed_sleep_restores_display(self):
        def command(*args):
            if args[0]=='/usr/bin/systemctl':raise subprocess.CalledProcessError(1,args)
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=command), \
             patch.object(m,'panel_is_on',return_value=False),patch.object(m,'wake_display') as wake:
            with self.assertRaises(subprocess.CalledProcessError):
                m.suspend_session(('c4','x11',['user']))
            wake.assert_called_once()

    def test_failed_blanking_does_not_request_sleep(self):
        calls=[]
        with patch.object(m,'display_environment',return_value=['DISPLAY=:1']), \
             patch.object(m,'read_command',side_effect=lambda *a:calls.append(a)), \
             patch.object(m,'panel_is_on',return_value=True), \
             patch.object(m.time,'monotonic',side_effect=[0,3]),patch.object(m,'wake_display'):
            with self.assertRaises(RuntimeError):m.suspend_session(('c4','x11',['user']))
        self.assertFalse(any(c[0]=='/usr/bin/systemctl' for c in calls))


if __name__=='__main__':unittest.main()
