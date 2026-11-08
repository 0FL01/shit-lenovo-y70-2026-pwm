/* Offline parser-level counterexample. No kernel/device access or DSI sender.
 * Mirrors the target long-copy branch after header alignment, not its entire
 * hardware/repeated-read path. ECC validation belongs to hardware and is not
 * modeled here; the tested parser neither reads ECC nor validates word count.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Model classification only, NOT a return value of the target parser.
 * Target 0x197618 -> 0x1976e8/0x1976ec calls __fortify_panic here.
 * Do not deliberately trigger that kernel path to run this offline test.
 */
enum { MODEL_FORTIFY_PANIC = -1 };

static uint16_t payload_crc(const uint8_t *data, size_t size)
{
    uint16_t crc = 0xffff;
    for (size_t i = 0; i < size; i++) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; bit++)
            crc = (uint16_t)((crc >> 1) ^ ((crc & 1) ? 0x8408 : 0));
    }
    return crc;
}

static int long_copy(const uint8_t *aligned_header, size_t available,
                     size_t requested, uint8_t *output)
{
    /* Target 0x197608..0x197628: allocation-bound check, then copy rx_len.
     * Header word count at [1:3] is not used to bound this copy.
     */
    if (available < 4 || requested > available - 4)
        return MODEL_FORTIFY_PANIC;
    memcpy(output, aligned_header + 4, requested);
    return (int)requested;
}

int main(void)
{
    const unsigned cases[][2] = {{3, 1}, {3, 2}, {3, 3}, {6, 4},
                                 {6, 6}, {10, 8}, {10, 10}};
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        unsigned requested = cases[i][0], payload_size = cases[i][1];
        uint8_t buffer[16] = {0}, output[10] = {0};
        unsigned packet_size = payload_size + 6;
        unsigned header_offset = 16 - packet_size;
        uint8_t *header = buffer + header_offset;
        header[0] = 0x1c; /* DCS long response */
        header[1] = (uint8_t)payload_size;
        /* Synthetic payload, not asserted to be a captured DDIC response. */
        for (unsigned j = 0; j < payload_size; j++)
            header[4 + j] = (uint8_t)j;
        if (payload_size == 3)
            header[6] = 0x65;
        uint16_t crc = payload_crc(header + 4, payload_size);
        header[4 + payload_size] = (uint8_t)crc;
        header[5 + payload_size] = (uint8_t)(crc >> 8);
        int result = long_copy(header, sizeof(buffer) - header_offset,
                               requested, output);
        if (result != (int)requested || memcmp(output, header + 4, requested))
            return 1;
        if (requested > payload_size && output[payload_size] != (uint8_t)crc)
            return 2;
        if (i == 0 && (crc != 0x0f87 || output[0] || output[1] != 0x87 || output[2] != 0x0f))
            return 3;
        printf("requested=%u payload=%u returned=%d footer_bytes_copied=%u\n",
               requested, payload_size, result, requested - payload_size);
    }
    uint8_t short_buffer[4] = {0}, output[3] = {0};
    if (long_copy(short_buffer, sizeof(short_buffer), 3, output) != MODEL_FORTIFY_PANIC)
        return 4;
    puts("PASS: 7 parser cases + 1 modeled fortify-panic path; not a graceful target refusal or live DDIC qualification");
    return 0;
}
