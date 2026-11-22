#!/usr/bin/env python3
"""Exercise the actual focus-pick condition before and after the Clutter patch."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path, help='Ubuntu package source with its quilt patches applied')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source_name = Path('clutter/clutter/clutter-stage.c')
patch = root / 'compat/mutter-x11-touch/0001-clutter-preserve-emulated-press-picking.patch'


def picker(source):
    start = source.index('  is_touch = sequence != NULL;')
    end = source.index('    {', source.index('  if (has_absolute_motion ||', start))
    return source[start:end] + '    return true;\n  return false;'


fixture = r'''
#include <stdbool.h>
#include <assert.h>
#include <stddef.h>
#define CLUTTER_CURRENT_TIME 0
#define CLUTTER_DEVICE_UPDATE_POINTER_EMULATED 4
typedef struct {
    unsigned press_count;
    bool pointer_emulated_press;
} PointerDeviceEntry;
typedef struct {
    PointerDeviceEntry *pointer_devices;
} ClutterStagePrivate;
static const void *clutter_seat_get_pointer(const void *seat) { return seat; }
static bool clutter_seat_is_unfocus_inhibited(const void *seat) { (void)seat; return false; }
#if PATCHED
static ClutterStagePrivate *clutter_stage_get_instance_private(ClutterStagePrivate *stage) { return stage; }
static PointerDeviceEntry *g_hash_table_lookup(PointerDeviceEntry *entry, const void *key) {
    (void)key;
    return entry;
}
#endif
static bool picks(ClutterStagePrivate *stage, const void *device, const void *seat,
                  const void *sequence, const void *source_device, unsigned time_ms,
                  unsigned flags) {
    (void)stage; (void)source_device; (void)time_ms;
    bool is_touch, has_absolute_motion;
    // PICKER
}
int main(void) {
    PointerDeviceEntry entry = {.press_count = 1, .pointer_emulated_press = true};
    ClutterStagePrivate stage = {.pointer_devices = &entry};
    const void *pointer = &stage;
    // The stale flag is absent from a timer-driven repick while a tap is held.
    assert(picks(&stage, pointer, pointer, NULL, NULL, 0, 0) == PATCHED);
    assert(picks(&stage, pointer, pointer, NULL, pointer, 10, 4));
    assert(picks(&stage, pointer, pointer, pointer, pointer, 10, 0));
    assert(!picks(&stage, pointer, pointer, NULL, pointer, 10, 0));
    assert(!picks(&stage, pointer, pointer, NULL, pointer, 0, 0));
    assert(!picks(&stage, pointer, pointer, NULL, NULL, 10, 0));
    entry.pointer_emulated_press = false;
    assert(!picks(&stage, pointer, pointer, NULL, NULL, 0, 0));
    entry.pointer_emulated_press = true;
    entry.press_count = 0;
    assert(!picks(&stage, pointer, pointer, NULL, NULL, 0, 0));
    stage.pointer_devices = NULL;
    assert(!picks(&stage, pointer, pointer, NULL, NULL, 0, 0));
}
'''

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    source = work / source_name
    source.parent.mkdir(parents=True)
    original = (args.source / source_name).read_text()
    source.write_text(original)
    patch_bytes = patch.read_bytes()
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', directory],
                   input=patch_bytes, check=True)
    for patched, text in enumerate((original, source.read_text())):
        c_path = work / 'fixture.c'
        c_path.write_text(fixture.replace('// PICKER', picker(text)))
        executable = work / 'fixture'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-DPATCHED=' + str(patched),
                        str(c_path), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
print('Stock drop reproduced; active replay, regular pointer, native touch and post-release checks passed')
