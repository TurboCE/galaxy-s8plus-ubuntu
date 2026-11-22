#!/usr/bin/env python3
"""Exercise the actual proposed modem cancellation helper with a busy callback."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'upstream/kernel.git'
MODEM = Path('drivers/misc/modem_v1')
NAMES = ('link_device_memory.h', 'link_device_memory_sbd.c', 'link_device_shmem.c')

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

struct modem_ctl { int lock; };
struct hrtimer { bool running, queued, rearm; };
static struct modem_ctl modem;
static struct hrtimer active;
static unsigned int attempts, callbacks;

#define spin_lock_irqsave(lock, flags) do { \
    assert(*(lock) == 0); *(lock) = 1; (flags) = 4; \
} while (0)
#define spin_unlock_irqrestore(lock, flags) do { \
    assert(*(lock) == 1 && (flags) == 4); *(lock) = 0; \
} while (0)

static int hrtimer_try_to_cancel(struct hrtimer *timer)
{
    assert(modem.lock == 1);
    ++attempts;
    if (timer->running)
        return -1;
    bool queued = timer->queued;
    timer->queued = false;
    return queued;
}

static void cpu_relax(void)
{
    unsigned long flags;
    assert(active.running);
    /* A competing callback must be able to take the modem lock here. */
    spin_lock_irqsave(&modem.lock, flags);
    active.running = false;
    active.queued = active.rearm;
    ++callbacks;
    spin_unlock_irqrestore(&modem.lock, flags);
}
"""

CHECKS = r"""
int main(void)
{
    cancel_modem_timer(&modem, &active);
    assert(attempts == 1 && callbacks == 0 && !active.queued && modem.lock == 0);

    active.queued = true;
    cancel_modem_timer(&modem, &active);
    assert(attempts == 2 && callbacks == 0 && !active.queued && modem.lock == 0);

    active.running = true;
    cancel_modem_timer(&modem, &active);
    assert(attempts == 4 && callbacks == 1 && !active.running && !active.queued);

    active.running = true;
    active.rearm = true;
    cancel_modem_timer(&modem, &active);
    assert(attempts == 6 && callbacks == 2 && !active.running && !active.queued);
    puts("Modem timers pass idle, queued, running, and running/rearmed cancellation.");
}
"""


def main():
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        base = work / MODEM
        base.mkdir(parents=True)
        for name in NAMES:
            source = subprocess.check_output(
                ['git', '-C', str(UPSTREAM), 'show', 'HEAD:' + str(MODEM / name)])
            (base / name).write_bytes(source)
        patch = ROOT / 'patches/proposals/0055-modem-timer-cancel-locking.patch'
        subprocess.run(['git', 'apply', str(patch)], cwd=work, check=True)
        start = 'static inline void cancel_modem_timer('
        header = (base / 'link_device_memory.h').read_text()
        i = header.index(start)
        j = header.index('\n}', i) + 2
        assert (base / 'link_device_memory_sbd.c').read_text().count('cancel_modem_timer(') == 1
        assert (base / 'link_device_shmem.c').read_text().count('cancel_modem_timer(') == 3
        program = work / 'modem-timer.c'
        program.write_text(STUBS + header[i:j] + '\n' + CHECKS)
        tool = work / 'modem-timer'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(program), '-o', str(tool)], check=True)
        subprocess.run([str(tool)], check=True, timeout=5)


if __name__ == '__main__':
    main()
