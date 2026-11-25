#!/usr/bin/env python3
"""Stage the reviewed GPL Samsung AID calculator for the optional module build."""

import argparse
import hashlib
from pathlib import Path

SOURCES = {
    "dimming.c": "a0550cf5dd21b6057b439274e9275b24f976aff6de0834d0bffcf4355a44a1ec",
    "dimming.h": "707fa31b19003f86d54dc79f6c4126e51fd3fb11ae0c03c9ee3c59f83cd6a21f",
    "dimming_gamma.h": "0152ce10367d47e8e722dfd2488cfdada0d2ff8e33fc323cdfe5eed53cfef21c",
    "s6e3ha6/s6e3ha6_dream2_a3_sa_panel.h": "6be34d111265ff6f9959586b5f2dd7464fbbffcaf2db5dc44a7d8cb7188ab6c1",
    "s6e3ha6/s6e3ha6_dimming.h": "2b8dada0cecadc031d884c6c65305bc6001a246b2b7f208b9123eed62ce9a504",
    "s6e3ha6/s6e3ha6_dream2_a3_sa_panel_dimming.h": "a666517f0067237bc3d3102b2d03a22914beee3c18a2abbc70028833a22c1e67",
}


def stage(source, destination):
    files = {}
    for filename, checksum in SOURCES.items():
        data = (source / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError(f"Unexpected Samsung source: {filename}")
        files[filename] = data.decode()

    calculator = files["dimming.c"]
    # Report allocation and calculation failures to the caller before using output.
    calculator = calculator.replace(
        "if (unlikely(!tp)) {\n\t\tpr_err(\"%s, tuning point not prepared",
        "if (!calc_gray_order || !calc_vout_order)\n\t\treturn -ENOMEM;\n\n"
        "\tif (unlikely(!tp)) {\n\t\tpr_err(\"%s, tuning point not prepared",
    ).replace(
        "\tgenerate_gray_scale(dim_info);",
        "\tif (generate_gray_scale(dim_info))\n\t\treturn -EINVAL;",
    ).replace(
        "\tgenerate_gamma_table(dim_info);",
        "\tif (generate_gamma_table(dim_info))\n\t\treturn -EINVAL;",
    )
    calculator += """
/* The port invokes the calculator once per probe and owns its scratch space. */
void g955n_aid_release_orders(void)
{
	kfree(calc_gray_order);
	kfree(calc_vout_order);
	calc_gray_order = NULL;
	calc_vout_order = NULL;
}
"""
    interface = files["dimming.h"].replace("#define DEBUG_EXCUTION_TIME", "").replace(
        "#define DEBUG_DIMMING_RESULT\n", ""
    )
    interface = interface.replace("in_range(", "aid_in_range(")
    interface = interface.replace(
        "void get_dimming_gamma_compact(struct dimming_info *, u32, u8 *);",
        "void get_dimming_gamma_compact(struct dimming_info *, u32, u8 *);\n"
        "void g955n_aid_release_orders(void);",
    )
    variant = files["s6e3ha6/s6e3ha6_dream2_a3_sa_panel_dimming.h"]
    variant = variant.replace('#include "../panel_dimming.h"\n', "")
    # Preserve the tuning rows, excluding Samsung's backlight framework tables.
    variant = variant[:variant.index("#if PANEL_BACKLIGHT_PAC_STEPS")]
    variant += "\n#endif\n"

    panel = files["s6e3ha6/s6e3ha6_dream2_a3_sa_panel.h"]
    aor = panel.split("#if PANEL_BACKLIGHT_PAC_STEPS == 512", 1)[1]
    aor = aor[:aor.index("/* HBM */")]
    aor = aor.replace("static u8", "static const u8")
    aor = aor.replace("[S6E3HA6_TOTAL_PAC_STEPS][2]", "[][2]")
    aor = panel[:panel.index("*/") + 2] + aor + "};\n"

    generated = destination / "aid-source"
    (generated / "s6e3ha6").mkdir(parents=True, exist_ok=True)
    (generated / "dimming.c").write_text(calculator)
    (generated / "dimming.h").write_text(interface)
    (generated / "s6e3ha6/dream2-a3-aor.h").write_text(aor)
    (generated / "dimming_gamma.h").write_text(files["dimming_gamma.h"])
    (generated / "s6e3ha6/s6e3ha6_dimming.h").write_text(files["s6e3ha6/s6e3ha6_dimming.h"])
    (generated / "s6e3ha6/dream2-a3.h").write_text(variant)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samsung_panel", type=Path)
    parser.add_argument("module_directory", type=Path)
    args = parser.parse_args()
    stage(args.samsung_panel, args.module_directory)
