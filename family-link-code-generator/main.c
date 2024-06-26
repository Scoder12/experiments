#include "openssl/hmac.h"
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <stdint.h>
#include <arpa/inet.h>

void print_hex(const unsigned char *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        printf("%02x", buf[i]);
    }
    printf("\n");
}

uint64_t htonll(uint64_t value) {
  // The answer is 42
  static const int num = 42;

  // Check the endianness
  if (*((const char*)(&num)) == num) {
    const uint32_t high_part = htonl((uint32_t) (value >> 32));
    const uint32_t low_part = htonl((uint32_t) (value & 0xFFFFFFFFLL));

    return (((uint64_t)(low_part)) << 32) | high_part;
  }
  return value;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    printf("Usage: %s <shared secret>\n", argv[0]);
    return 1;
  }

  // these paramaters are hardcoded
  unsigned long code_granularity_ms = 1000 * 60; // 1 minute
  // these paramaters are part of the config payload
  char *key = argv[1];
  unsigned long code_validity_ms = 1000 * 60 * 60; // 60 minutes
  // unsigned long clock_drift_tolerance_ms = code_validity_ms / 2;

  for (int i = 0; i < strlen(key); i++) {
    if (key[i] == ' ' || key[i] == '\n') {
      printf("Warning: whitespace in key\n");
      break;
    }
  }

  struct timeval tv;
  if (gettimeofday(&tv, NULL)) {
    perror("gettimeofday");
    return -1;
  }
  uint64_t timestamp_millis_since_epoch = 
    (uint64_t)(tv.tv_sec) * 1000 +
    (uint64_t)(tv.tv_usec) / 1000;
  printf("Current stamp: %lu\n", timestamp_millis_since_epoch);

  const int64_t interval = timestamp_millis_since_epoch / code_validity_ms;
  const int64_t interval_beginning_timestamp_ms = interval * code_validity_ms;
  const int64_t adjusted_timestamp = interval_beginning_timestamp_ms / code_granularity_ms;
  const uint64_t big_endian_timestamp = htonll(adjusted_timestamp);

  unsigned char buf[EVP_MAX_MD_SIZE] = {0};
  printf("key len: %ld, buf len: %ld\n", strlen(key), sizeof(buf));
  unsigned int md_len = sizeof(buf);
  unsigned char *r = HMAC(
    EVP_sha1(), 
    key, strlen(key), 
    (unsigned char*) &big_endian_timestamp, sizeof(uint64_t), 
    buf, &md_len
  );
  if (r == NULL) {
    printf("HMAC() returned an error\n");
    return 1;
  }
  if (r != buf) {
    printf("HMAC() unexpectedly allocated or did something weird\n");
    return 2;
  }

  printf("digest (%d bytes): ", md_len);
  print_hex(buf, (size_t) md_len);

  // the last nibble of the digest
  const int8_t offset = ((uint8_t*) buf)[md_len - 1] & 0xf;
  printf("offset = buf[%d] & 0x0f = %02hhx\n", md_len - 1, offset);
  uint32_t pre_result = *((uint32_t*) &buf[offset]);
  printf("pre_result = %08x\n", pre_result);
  // read it as big endian then cast from unsigned to signed
  int32_t result = (int32_t) ntohl(pre_result);
  // clear sign bit
  result &= 0x7fffffff;
  printf("result = %08x\n", result);

  uint64_t valid_from_ms = interval_beginning_timestamp_ms;
  uint64_t valid_to_ms = valid_from_ms + code_validity_ms;

  int code = result % 1000000;
  puts("");
  printf("Code: %06d\n", code);
  uint64_t remaining_sec = (valid_to_ms - timestamp_millis_since_epoch) / 1000;
  printf("Expires in: %02lu:%02lu (%lu sec)\n", remaining_sec / 60, remaining_sec % 60, remaining_sec);
  return 0;
}
