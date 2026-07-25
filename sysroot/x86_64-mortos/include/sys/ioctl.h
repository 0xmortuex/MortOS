#ifndef MORTOS_SYS_IOCTL_H
#define MORTOS_SYS_IOCTL_H

#define FIONREAD 0x541B
#define FIONBIO 0x5421
#define TIOCGWINSZ 0x5413

struct winsize {
    unsigned short ws_row;
    unsigned short ws_col;
    unsigned short ws_xpixel;
    unsigned short ws_ypixel;
};

#ifdef __cplusplus
extern "C" {
#endif

int ioctl(int descriptor, unsigned long request, ...);

#ifdef __cplusplus
}
#endif

#endif
