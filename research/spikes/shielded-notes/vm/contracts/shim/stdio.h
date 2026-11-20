/* Freestanding shim for the riscv64 contract build. blake2b-rs's C reference
   source includes <stdio.h>, but only its self-test (BLAKE2B_SELFTEST, not
   defined here) calls anything from it, so an empty header is enough. */
#ifndef NOIR_CKB_SHIM_STDIO_H
#define NOIR_CKB_SHIM_STDIO_H
#endif
