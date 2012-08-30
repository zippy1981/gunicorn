#include <pthread.h>

unsigned long
atomic_int_add(unsigned long *dst, unsigned long incr)
{
     return __sync_add_and_fetch(dst, incr);
}

unsigned long
atomic_int_sub(unsigned long *dst, unsigned long incr)
{
     return __sync_sub_and_fetch(dst, incr);
}
