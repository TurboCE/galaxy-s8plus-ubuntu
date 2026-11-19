#!/usr/bin/env python3
"""Compare panel submission structure offsets with the pinned vendor header."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = '54feaea9870dd0e90ceced5623e0544d965b400b'
HEADER = 'drivers/video/fbdev/exynos/dpu/decon.h'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--kernel', type=Path, default=ROOT / 'upstream/kernel.git')
    args = parser.parse_args()
    vendor = subprocess.check_output(
        ['git', '-C', str(args.kernel), 'show', f'{PIN}:{HEADER}'], text=True)
    declarations = []
    for name in (
        'enum decon_blending', 'enum decon_pixel_format', 'enum dpp_flip',
        'enum dpp_csc_eq', 'enum dpp_comp_src', 'struct decon_win_rect',
        'struct dpp_params', 'struct decon_frame', 'struct decon_win_config',
        'struct decon_win_config_data',
    ):
        start = vendor.index(name + ' {')
        end = vendor.index('\n};', start) + 3
        declarations.append(vendor[start:end].replace('struct decon_frame', 'struct vendor_frame'))
    source = '''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define CONFIG_SUPPORT_DSU 1
#define MAX_DECON_WIN 6
#define MAX_PLANE_CNT 3
typedef uint32_t __u32;
typedef uint32_t u32;
typedef uint64_t dma_addr_t;
enum decon_idma_type { IDMA_G0, IDMA_G1 };
''' + '\n'.join(declarations)
    source += '''
#include "decon-output.c"
#define SAME_OFFSET(kernel_member, local_member) \
    _Static_assert(offsetof(struct decon_win_config, kernel_member) == \
                   offsetof(struct decon_window, local_member), #kernel_member)
SAME_OFFSET(state, state);
SAME_OFFSET(fd_idma, dma_buf);
SAME_OFFSET(fence_fd, fence);
SAME_OFFSET(plane_alpha, alpha);
SAME_OFFSET(blending, blend);
SAME_OFFSET(idma_type, channel);
SAME_OFFSET(format, format);
SAME_OFFSET(dpp_parm, dpp);
SAME_OFFSET(src, source);
SAME_OFFSET(dst, destination);
SAME_OFFSET(protection, protected_content);
SAME_OFFSET(compression, compressed);
_Static_assert(offsetof(struct decon_win_config_data, config) ==
               offsetof(struct decon_config, windows), "window array");
_Static_assert(S3CFB_WIN_CONFIG == DECON_WIN_CONFIG, "ioctl number");
_Static_assert((int)DECON_PIXEL_FORMAT_RGBA_8888 == (int)G955N_DECON_RGBA8888 &&
               (int)DECON_PIXEL_FORMAT_BGRA_8888 == (int)G955N_DECON_BGRA8888 &&
               (int)DECON_PIXEL_FORMAT_RGBX_8888 == (int)G955N_DECON_RGBX8888, "RGB formats");
'''
    source = source.replace('S3CFB_WIN_CONFIG', "_IOW('F', 209, struct decon_win_config_data)")
    panel = ROOT / 'compat/native-gnome/direct-panel'
    subprocess.run([args.cc, '-std=c11', '-fsyntax-only', '-I', str(panel), '-x', 'c', '-'],
                   input=source, text=True, check=True)
    print('Pinned DECON submission offsets and ioctl match')


if __name__ == '__main__':
    main()
