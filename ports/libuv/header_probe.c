#include <uv.h>

_Static_assert(UV_VERSION_MAJOR == 1, "unexpected libuv major version");
_Static_assert(UV_VERSION_MINOR == 52, "unexpected libuv minor version");
_Static_assert(UV_VERSION_PATCH == 1, "unexpected libuv patch version");
_Static_assert(sizeof(struct stat) == 144, "MortOS stat ABI drift");
_Static_assert(sizeof(struct sockaddr_storage) == 128,
               "MortOS socket storage ABI drift");
_Static_assert(sizeof(struct sockaddr_in6) == 28, "MortOS IPv6 ABI drift");

int main(void) {
    uv_loop_t loop;
    return uv_loop_init(&loop);
}
