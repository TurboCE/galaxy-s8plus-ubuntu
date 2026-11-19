/* SPDX-License-Identifier: MIT
 * SM-G955N native-port boundary before every production PCM open.
 * All hw control/PCM resolution uses private minimal ALSA configuration roots.
 */
#ifndef G955N_SPA_ALSA_SCOPE_H
#define G955N_SPA_ALSA_SCOPE_H
#include <alsa/asoundlib.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdatomic.h>
#ifndef G955N_SCOPE_MODEL_PATH
#define G955N_SCOPE_MODEL_PATH "/proc/device-tree/model"
#endif

enum g955n_card_scope { G955N_OTHER = 0, G955N_PRIMARY = 1, G955N_DEBUG = 2 };
struct g955n_pcm_target { int card, scope; unsigned long pcm, sub; };

static inline bool g955n_scope_model(void)
{
    char model[256] = { 0 };
    FILE *f = fopen(G955N_SCOPE_MODEL_PATH, "re");
    if (!f) return false;
    size_t n = fread(model, 1, sizeof(model) - 1, f);
    fclose(f);
    return n > 0 && strstr(model, "SM-G955N") != NULL;
}

/* No global config update, user .asoundrc, aliases or hooks are evaluated.
 * selector is validated by the caller before interpolation. */
static inline int g955n_scope_card(const char *selector, int *actual_card)
{
    snd_ctl_t *ctl = NULL;
    snd_config_t *config = NULL;
    snd_ctl_card_info_t *info;
    char text[160];
    int r;
    snd_ctl_card_info_alloca(&info);
    snprintf(text, sizeof(text), "ctl.g955n_native { type hw card \"%s\" }", selector);
    r = snd_config_load_string(&config, text, 0);
    if (r < 0) return r;
    r = snd_ctl_open_lconf(&ctl, "g955n_native", SND_CTL_NONBLOCK, config);
    snd_config_delete(config);
    if (r < 0) return r;
    r = snd_ctl_card_info(ctl, info);
    if (r >= 0) {
        int card = snd_ctl_card_info_get_card(info);
        const char *driver = snd_ctl_card_info_get_driver(info);
        const char *name = snd_ctl_card_info_get_name(info);
        const char *longname = snd_ctl_card_info_get_longname(info);
        const char *id = snd_ctl_card_info_get_id(info);
        if (actual_card) *actual_card = card;
        bool primary = !strcmp(driver, "Exynos8895-Made") ||
            !strcmp(name, "Exynos8895-Madera") || !strcmp(id, "Exynos8895Mader");
        bool debug = !strcmp(driver, "abox_dump") || !strcmp(name, "abox_dump") ||
            !strcmp(id, "aboxdump");
        if (primary) {
            r = !strcmp(driver, "Exynos8895-Made") &&
                !strcmp(name, "Exynos8895-Madera") &&
                !strcmp(longname, "Exynos8895-Madera") &&
                !strcmp(id, "Exynos8895Mader") ? G955N_PRIMARY : -EPERM;
            if (r == G955N_PRIMARY) {
                snd_pcm_info_t *pcm;
                snd_pcm_info_alloca(&pcm);
                snd_pcm_info_set_device(pcm, 0);
                snd_pcm_info_set_subdevice(pcm, 0);
                snd_pcm_info_set_stream(pcm, SND_PCM_STREAM_PLAYBACK);
                int e = snd_ctl_pcm_info(ctl, pcm);
                if (e < 0) r = e;
                else if (snd_pcm_info_get_card(pcm) != card ||
                    snd_pcm_info_get_device(pcm) != 0 ||
                    snd_pcm_info_get_subdevice(pcm) != 0 ||
                    snd_pcm_info_get_stream(pcm) != SND_PCM_STREAM_PLAYBACK ||
                    strcmp(snd_pcm_info_get_id(pcm), "RDMA0 (*)") ||
                    strcmp(snd_pcm_info_get_name(pcm), "") ||
                    snd_pcm_info_get_subdevices_count(pcm) != 1)
                    r = -EPERM;
            }
        } else if (debug)
            r = !strcmp(driver, "abox_dump") && !strcmp(name, "abox_dump") &&
                !strcmp(longname, "abox_dump") && !strcmp(id, "aboxdump") ?
                G955N_DEBUG : -EPERM;
        else r = G955N_OTHER;
    }
    snd_ctl_close(ctl);
    return r;
}

static inline int g955n_scope_index(unsigned int index)
{
    char selector[32];
    if (!g955n_scope_model()) return -ENODEV;
    snprintf(selector, sizeof(selector), "%u", index);
    return g955n_scope_card(selector, NULL);
}

/* ALSA 1.2.11 UCM main.c prefixes local PlaybackPCM values with
 * "_ucm%04X.". utils.c:uc_mgr_alibcfg_by_device requires the dot at
 * byte eight and parses exactly four hex digits; support that actual wire
 * syntax, rather than extrapolating printf minimum width to larger IDs.
 * Treat only that canonical namespace as metadata, never look it up. The
 * suffix must still be direct hw and pass the independent hardware policy. */
static inline const char *g955n_scope_hw_name(const char *device)
{
    const char *p = device;
    if (!strncmp(p, "_ucm", 4)) {
        const char *id = p + 4;
        unsigned int digits = 0;
        p = id;
        while ((*p >= '0' && *p <= '9') || (*p >= 'A' && *p <= 'F')) {
            if (++digits > 4) return NULL;
            p++;
        }
        if (digits != 4 || *p != '.')
            return NULL;
        p++;
    }
    return !strncmp(p, "hw:", 3) ? p : NULL;
}

static inline int g955n_scope_resolve(const char *device, int stream,
        struct g955n_pcm_target *target)
{
    char selector[64];
    const char *p, *hw;
    char *end;
    size_t n;
    if (!g955n_scope_model()) return -ENODEV;
    hw = g955n_scope_hw_name(device);
    if (!hw) return -EPERM;
    p = strchr(hw + 3, ',');
    if (!p || (n = (size_t)(p - hw - 3)) == 0 || n >= sizeof(selector)) return -EPERM;
    memcpy(selector, hw + 3, n); selector[n] = 0;
    for (size_t i = 0; i < n; i++)
        if (!((selector[i] >= 'a' && selector[i] <= 'z') ||
              (selector[i] >= 'A' && selector[i] <= 'Z') ||
              (selector[i] >= '0' && selector[i] <= '9') ||
              selector[i] == '_' || selector[i] == '-')) return -EPERM;
    if (p[1] < '0' || p[1] > '9') return -EPERM;
    errno = 0; target->pcm = strtoul(p + 1, &end, 10);
    if (errno) return -EPERM;
    target->sub = 0;
    if (*end == ',') {
        p = end;
        if (p[1] < '0' || p[1] > '9') return -EPERM;
        errno = 0; target->sub = strtoul(p + 1, &end, 10);
        if (errno) return -EPERM;
    }
    if (*end || target->pcm > 0x7fffffffUL || target->sub > 0x7fffffffUL) return -EPERM;
    target->scope = g955n_scope_card(selector, &target->card);
    if (target->scope < 0) return target->scope;
    if (target->scope != G955N_PRIMARY) return -EPERM;
    if (target->scope == G955N_PRIMARY &&
        (target->pcm != 0 || target->sub != 0 || stream != SND_PCM_STREAM_PLAYBACK)) return -EPERM;
    return 0;
}

/* Per-origin sequence enables counting even denied requests before any open. */
static inline int g955n_scope_pcm_audit(const char *device, int stream,
        const char *origin, struct g955n_pcm_target *resolved)
{
    static atomic_ulong sequence = 0;
    struct g955n_pcm_target target = { -1, -1, ~0UL, ~0UL };
    int r = g955n_scope_resolve(device, stream, &target);
    unsigned long seq = atomic_fetch_add_explicit(&sequence, 1, memory_order_relaxed) + 1;
    fprintf(stderr, "G955N_PCM_SCOPE origin=%s pid=%ld seq=%lu card=%d pcm=%ld direction=%s scope=%d result=%d device=%s\n",
        origin, (long)getpid(), seq, target.card, target.pcm == ~0UL ? -1L : (long)target.pcm,
        stream == SND_PCM_STREAM_PLAYBACK ? "playback" : "capture", target.scope, r, device);
    if (resolved) *resolved = target;
    return r;
}

static inline int g955n_scope_open(snd_pcm_t **handle, const char *device,
        int stream, int mode, const char *origin)
{
    struct g955n_pcm_target target;
    snd_config_t *config = NULL;
    char text[192];
    int r = g955n_scope_pcm_audit(device, stream, origin, &target);
    if (r < 0) return r;
    /* Numeric card from actual control INFO; caller's hw aliases/configuration
     * do not participate in opening the PCM. No global config is consulted. */
    snprintf(text, sizeof(text), "pcm.g955n_native { type hw card %d device %lu subdevice %lu }",
        target.card, target.pcm, target.sub);
    r = snd_config_load_string(&config, text, 0);
    if (r < 0) return r;
    r = snd_pcm_open_lconf(handle, "g955n_native", stream, mode, config);
    snd_config_delete(config);
    return r;
}
#endif
