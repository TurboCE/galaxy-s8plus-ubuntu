/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdbool.h>
#include <stdio.h>
#include <time.h>
#include <string.h>

/* libXtst client ABI, linked against the installed runtime soname. */
extern int XTestFakeMotionEvent(Display *, int, int, int, unsigned long);
extern int XTestFakeKeyEvent(Display *, unsigned int, Bool, unsigned long);
extern int XTestFakeButtonEvent(Display *, unsigned int, Bool, unsigned long);

static unsigned long elapsed_ms(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (unsigned long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void pause_ms(long ms)
{
    struct timespec delay = {ms / 1000, (ms % 1000) * 1000000};
    nanosleep(&delay, NULL);
}

static bool position(Display *display, Window window, int *x, int *y)
{
    Window child;
    return XTranslateCoordinates(display, window, DefaultRootWindow(display),
                                 0, 0, x, y, &child);
}

int main(int argc, char **argv)
{
    bool scripted_move = argc == 2 && !strcmp(argv[1], "--move-window");
    if (!scripted_move && (argc != 2 || strcmp(argv[1], "--run")))
        return 2;
    Display *display = XOpenDisplay(NULL);
    if (!display)
        return 2;

    int screen = DefaultScreen(display);
    Window root = RootWindow(display, screen);
    if (DisplayWidth(display, screen) < 960 || DisplayHeight(display, screen) < 700) {
        XCloseDisplay(display);
        return 2;
    }
    Window window = XCreateSimpleWindow(display, root, 280, 360, 384, 256, 0,
                                        BlackPixel(display, screen), WhitePixel(display, screen));
    if (scripted_move) {
        XSetWindowAttributes attributes = {.override_redirect = True};
        XChangeWindowAttributes(display, window, CWOverrideRedirect, &attributes);
    }
    XStoreName(display, window, "SM-G955N drag measurement");
    XMapRaised(display, window);
    XSync(display, False);
    pause_ms(800);

    int pointer_x, pointer_y, unused_x, unused_y, initial_x, initial_y;
    unsigned int buttons;
    Window unused_root, unused_child;
    bool pointer_known = XQueryPointer(display, root, &unused_root, &unused_child,
                                       &pointer_x, &pointer_y, &unused_x, &unused_y, &buttons);
    bool context_ok = pointer_known && !(buttons & (Button1Mask | Button2Mask | Button3Mask)) &&
                      position(display, window, &initial_x, &initial_y) &&
                      initial_x > 0 && initial_y > 0;
    bool pressed = false;
    KeyCode super = XKeysymToKeycode(display, XK_Super_L);
    unsigned moved = 0;
    if (!context_ok || !super || (buttons & (ShiftMask | ControlMask | Mod1Mask | Mod4Mask)))
        goto cleanup;

    /* GNOME modifier + primary drag on our own test window. */
    int start_x = initial_x + 120;
    int start_y = initial_y + 80;
    int step = start_x + 240 < DisplayWidth(display, screen) ? 4 : -4;
    if (!scripted_move) {
        XTestFakeMotionEvent(display, screen, start_x, start_y, 0);
        XTestFakeKeyEvent(display, super, True, 0);
        XTestFakeButtonEvent(display, 1, True, 0);
        pressed = true;
    }
    XSync(display, False);
    pause_ms(150);

    unsigned long begin = elapsed_ms();
    int previous_x = initial_x, previous_y = initial_y;
    for (int i = 1; i <= 180; i++) {
        int phase = i % 120;
        int offset = phase <= 60 ? phase : 120 - phase;
        if (scripted_move)
            XMoveWindow(display, window, initial_x + offset * step, initial_y);
        else
            XTestFakeMotionEvent(display, screen, start_x + offset * step, start_y, 0);
        XFlush(display);
        pause_ms(16);
        int x, y;
        if (!position(display, window, &x, &y))
            break;
        if (x != previous_x || y != previous_y)
            moved++;
        previous_x = x;
        previous_y = y;
        printf("%lu,%d,%d,%d\n", elapsed_ms() - begin, offset * step, x, y);
    }

cleanup:
    if (pressed) {
        XTestFakeButtonEvent(display, 1, False, 0);
        XTestFakeKeyEvent(display, super, False, 0);
        XTestFakeMotionEvent(display, screen, pointer_x, pointer_y, 0);
    }
    XDestroyWindow(display, window);
    XSync(display, False);
    XCloseDisplay(display);
    if (moved < 4)
        fprintf(stderr, "Only %u changes observed during the drag\n", moved);
    return moved >= 4 ? 0 : 3;
}
