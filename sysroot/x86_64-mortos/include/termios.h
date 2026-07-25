#ifndef MORTOS_TERMIOS_H
#define MORTOS_TERMIOS_H

typedef unsigned int tcflag_t;
typedef unsigned char cc_t;
typedef unsigned int speed_t;

#define NCCS 32

struct termios {
    tcflag_t c_iflag;
    tcflag_t c_oflag;
    tcflag_t c_cflag;
    tcflag_t c_lflag;
    cc_t c_line;
    cc_t c_cc[NCCS];
    speed_t c_ispeed;
    speed_t c_ospeed;
};

#define TCSANOW 0
#define TCSADRAIN 1
#define TCSAFLUSH 2

#define ECHO 0000010
#define ECHONL 0000100
#define ICANON 0000002
#define ISIG 0000001
#define IEXTEN 0100000
#define OPOST 0000001
#define IXON 0002000
#define ICRNL 0000400
#define BRKINT 0000002
#define INPCK 0000020
#define ISTRIP 0000040
#define CS8 0000060

#define VINTR 0
#define VQUIT 1
#define VERASE 2
#define VKILL 3
#define VEOF 4
#define VTIME 5
#define VMIN 6
#define VSTART 8
#define VSTOP 9
#define VSUSP 10

#ifdef __cplusplus
extern "C" {
#endif

int tcgetattr(int descriptor, struct termios *attributes);
int tcsetattr(
    int descriptor, int optional_actions, const struct termios *attributes);
void cfmakeraw(struct termios *attributes);
speed_t cfgetispeed(const struct termios *attributes);
speed_t cfgetospeed(const struct termios *attributes);
int cfsetispeed(struct termios *attributes, speed_t speed);
int cfsetospeed(struct termios *attributes, speed_t speed);

#ifdef __cplusplus
}
#endif

#endif
