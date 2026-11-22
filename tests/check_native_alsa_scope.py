#!/usr/bin/env python3
"""Exercise the actual proposed ALSA endpoint policy against pinned source."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'upstream/kernel.git'
PATCH = ROOT / 'patches/proposals/0056-g955n-scope-native-alsa.patch'
FILES = ('sound/core/sound.c',
         'arch/arm64/boot/dts/exynos/exynos8895-dream2lte_kor_10.dts')

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    for name in FILES:
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(
            ['git', '--git-dir', str(SOURCE), 'show', 'HEAD:' + name]))
    subprocess.run(['patch', '-s', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=work, check=True)
    source = (work / FILES[0]).read_text()
    start = source.index('static bool g955n_audio_scope;')
    end = source.index('static int snd_open(', start)
    access = source.index('if (!g955n_audio_open_allowed(mptr))', end)
    assert access < source.index('new_fops = fops_get', end)
    fixture = work / 'scope.c'
    fixture.write_text('''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
enum { SNDRV_DEVICE_TYPE_PCM_PLAYBACK, SNDRV_DEVICE_TYPE_PCM_CAPTURE,
       SNDRV_DEVICE_TYPE_COMPRESS, SNDRV_DEVICE_TYPE_CONTROL };
struct snd_card { const char *id; };
struct snd_minor { const struct snd_card *card_ptr; int type, device; };
''' + source[start:end] + '''
static bool allowed(const struct snd_card *card, int type, int device)
{
    struct snd_minor minor = {card, type, device};
    return g955n_audio_open_allowed(&minor);
}

int main(void)
{
    struct snd_card internal = {"Exynos8895Mader"};
    struct snd_card debug = {"aboxdump"};
    struct snd_card external = {"USB"};
    assert(allowed(&internal, SNDRV_DEVICE_TYPE_PCM_CAPTURE, 0));
    assert(allowed(&debug, SNDRV_DEVICE_TYPE_CONTROL, 0));
    g955n_audio_scope = true;
    assert(allowed(NULL, SNDRV_DEVICE_TYPE_CONTROL, 0));
    assert(allowed(&external, SNDRV_DEVICE_TYPE_PCM_CAPTURE, 0));
    assert(allowed(&internal, SNDRV_DEVICE_TYPE_CONTROL, 0));
    assert(!allowed(&debug, SNDRV_DEVICE_TYPE_CONTROL, 0));
    assert(!allowed(&debug, SNDRV_DEVICE_TYPE_PCM_CAPTURE, 9));
    assert(!allowed(&internal, SNDRV_DEVICE_TYPE_COMPRESS, 0));
    for (int device = 0; device < 32; device++) {
        assert(allowed(&internal, SNDRV_DEVICE_TYPE_PCM_PLAYBACK, device) == (device == 0));
        assert(allowed(&internal, SNDRV_DEVICE_TYPE_PCM_CAPTURE, device) == (device == 9));
    }
}
''')
    exe = work / 'scope'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(fixture), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
    print('SM-G955N native ALSA endpoint policy passed')
