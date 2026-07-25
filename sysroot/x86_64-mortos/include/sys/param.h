#ifndef MORTOS_SYS_PARAM_H
#define MORTOS_SYS_PARAM_H

#define MAXHOSTNAMELEN 64
#define MAXPATHLEN 4096
#define PATH_MAX MAXPATHLEN

#ifndef MIN
#define MIN(left, right) ((left) < (right) ? (left) : (right))
#endif
#ifndef MAX
#define MAX(left, right) ((left) > (right) ? (left) : (right))
#endif

#endif
