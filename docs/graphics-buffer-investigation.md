# Native graphics buffer checkpoint

GNOME still uses llvmpipe. No desktop/panel acceleration pass is claimed.

On recovered kernel15, a fresh private original allocator registered with its
real PID. One 64x64 RGBA buffer passed CPU allocation/import/write/read/free.
A separate process-scoped reference libhybris pbuffer again passed 300 alternating
shader/readback frames on Mali-G71. Thus pbuffer rendering alone does not test
shared native-buffer ownership or presentation.

Initial EGLImage/native-buffer tests rendered the first color, but later reads
retained earlier pixels. Checking only a center pixel could miss this; every
pixel is now checked, and all three frame colors differ, including the final
independent CPU result. Rebinding programs, changing uniform setter, full/aligned
readback, glFinish after readback and EGL fence completion alone did not establish
correct repeated reads. The tested callee-saved FP registers were preserved.

The passing change uses the actual mapper CPU lock/unlock contract after GPU
completion for every CPU observation of the shared buffer. The callback checks
all pixels with the actual allocated stride and waits for the unlock fence.
Three unique colors passed this mapper check, GL readback and final independent
CPU check; all EGL fences completed. Complete private trace/maps, process and
namespace cleanup, unchanged boot/taint and no new kernel fault signatures were
recorded. This identifies the missing ownership/cache synchronization in the
probe path; it does not establish a general Mali driver fix or a panel result.

The original composer first aborted on /dev/binder EACCES. A separate explicit
composer runtime now grants graphics access only on its newly created private
Binder inode, preserving host permissions. Standard Binder also needs its real
service manager: without it composer waits. Starting the original bounded
servicemanager produced a real service-list response and the original composer
registered IComposer/default with its actual PID. No Android init/autostart or
fake ready response was used. Display nodes remained absent and open attempts
returned ENOENT, so this is registration, not usable display initialization.
A retained passthrough metadata entry with PID -1 after remote service death
must be distinguished from a live remote registration. All host Binder clients
were gone after the complete private runtime ended.

The private compositor package initially lost an intermediate library symlink,
so its native loader could not resolve libgbinder. Packaging now retains and
checks every link in each chain. Native loader dependency resolution passed
with private wlroots/Hybris libraries and existing Ubuntu dependencies. No
compositor process or display takeover has been run at this checkpoint.
