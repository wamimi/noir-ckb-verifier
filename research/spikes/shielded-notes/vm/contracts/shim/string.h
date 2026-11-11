/* Minimal <string.h> for building the unused C part of blake2b-rs (a hard dependency of
   sparse-merkle-tree) for a bare-metal RISC-V target. The script does not call that code. */
#ifndef SPIKE_STRING_H
#define SPIKE_STRING_H
#include <stddef.h>
void *memcpy(void *dest, const void *src, size_t n);
void *memset(void *dest, int c, size_t n);
#endif
