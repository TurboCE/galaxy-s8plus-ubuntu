#!/bin/sh
set -eu

# Build only the engine. The matching Ubuntu package supplies its data and UI.
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 OUTPUT_ENGINE" >&2
    exit 2
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
release=aa4b71c69cf9d77466e9c6713c99d6bdffee6a68
fix=eaaf6aa222926835fa155d587b05c199107cb449

curl -fsSL "https://codeload.github.com/libhangul/ibus-hangul/tar.gz/$release" \
    -o "$work/source.tar.gz"
curl -fsSL "https://github.com/libhangul/ibus-hangul/commit/$fix.patch" \
    -o "$work/osk.patch"
(
    cd "$work"
    sha256sum --check <<'EOF'
a9485d695e388ea74599b54a996df7ee6259344ecaaa1b149b3b16f5d002c842  source.tar.gz
dba0ca7d499eead492a1a0ea32b9812e073d0ab3665ddaf678cb6214461901a8  osk.patch
EOF
    tar -xzf source.tar.gz
    cd "ibus-hangul-$release"
    patch --batch --forward -p1 < ../osk.patch

    cc -O2 -D_GNU_SOURCE -DGETTEXT_PACKAGE='"ibus-hangul"' \
        -DPKGDATADIR='"/usr/share/ibus-hangul"' \
        -DIBUSHANGUL_DATADIR='"/usr/share/ibus-hangul"' \
        -DLOCALEDIR='"/usr/share/locale"' \
        $(pkg-config --cflags ibus-1.0 libhangul) \
        src/main.c src/engine.c src/ustring.c \
        -o ../ibus-engine-hangul $(pkg-config --libs ibus-1.0 libhangul)
)
install -m 0755 "$work/ibus-engine-hangul" "$1"
