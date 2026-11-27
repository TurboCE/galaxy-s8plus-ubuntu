"""Check CAM0 ownership in the Linux DT embedded in an SM-G955N BOOT payload."""

import struct

from boot.mkdtbh import FDT_MAGIC, fdt_nodes


CAM0 = '/soc@0/iommu@12d10000'
BOARD = b'samsung,dream2lteks'


def verify_cam0_ownership(kernel):
    """Reject enabled clients competing for the single CAM0 owner slot."""
    magic = struct.pack('>I', FDT_MAGIC)
    offset = kernel.find(magic)
    while offset != -1:
        if len(kernel) - offset >= 40:
            total = struct.unpack_from('>I', kernel, offset + 4)[0]
            if 40 <= total <= len(kernel) - offset:
                try:
                    nodes = dict(fdt_nodes(kernel[offset:offset + total]))
                except (ValueError, struct.error):
                    # The magic can also occur as a constant in the ARM64 code.
                    pass
                else:
                    if BOARD in nodes.get('/', {}).get('compatible', b'').split(b'\0'):
                        verify_cam0_tree(nodes)
        offset = kernel.find(magic, offset + 4)


def verify_cam0_tree(nodes):
    if CAM0 not in nodes:
        return

    owners = []
    providers = {}
    available = {}
    for path, props in nodes.items():
        parent = path.rpartition('/')[0] or '/'
        available[path] = (available.get(parent, True) and
                           props.get('status', b'okay\0') in (b'okay\0', b'ok\0'))
        handle = props.get('phandle', props.get('linux,phandle'))
        cells = props.get('#iommu-cells')
        if handle is not None and cells is not None:
            if len(handle) != 4 or len(cells) != 4:
                raise ValueError(f'{path}: invalid IOMMU provider cells')
            providers[handle] = (path, struct.unpack('>I', cells)[0])

    for path, props in nodes.items():
        spec = props.get('iommus', b'')
        if not available[path] or not spec:
            continue
        pos = 0
        while pos < len(spec):
            handle = spec[pos:pos + 4]
            provider = providers.get(handle)
            if provider is None:
                raise ValueError(f'{path}: unresolved IOMMU provider')
            controller, cells = provider
            pos += (1 + cells) * 4
            if pos > len(spec):
                raise ValueError(f'{path}: truncated IOMMU specifier')
            if controller == CAM0 and path not in owners:
                owners.append(path)

    if len(owners) > 1:
        raise ValueError('SM-G955N CAM0 has multiple enabled consumers: ' + ', '.join(owners))
