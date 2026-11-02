/* Canary v1 hardware-in-the-loop simulation.
 *
 * Runs the real firmware ELF (firmware/build/canary.elf) on simavr's
 * ATmega328P model at 8 MHz with:
 *   - virtual Sensirion SGP40 (0x59), SHT40 (0x44) and SCD41 (0x62) on the
 *     TWI bus, speaking their datasheet command sets and CRC-8 framing
 *   - the two NTC dividers driven onto ADC0/ADC1 as voltages
 *   - the TEST/HUSH button on PD2
 * and records what a person would see and hear: the three LED PWM duties,
 * the sounder drive (Timer1 toggling PB1, counted edge by edge), and the
 * telemetry the firmware prints on TXD.
 *
 *   harness <canary.elf> <world.csv> <out_prefix>
 *
 * world.csv: one row per second:
 *   t,t_pack,t_probe,t_amb,rh,sraw,co2,sgp,sht,scd,button
 * (t_probe empty/nan = probe unplugged; sgp/sht/scd 0 = sensor not answering;
 *  button 1 = held during that second's first 200 ms)
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <simavr/sim_avr.h>
#include <simavr/sim_elf.h>
#include <simavr/sim_io.h>
#include <simavr/avr_twi.h>
#include <simavr/avr_adc.h>
#include <simavr/avr_ioport.h>
#include <simavr/avr_uart.h>

#define MAXS 20000
struct world { double t_pack, t_probe, t_amb, rh, sraw, co2; int sgp, sht, scd, button; };
static struct world W[MAXS];
static int nW;

static avr_t *avr;
static FILE *f_uart, *f_out;
static double now_s(void) { return (double)avr->cycle / avr->frequency; }
static const struct world *cur(void)
{
    int i = (int)now_s();
    if (i >= nW) i = nW - 1;
    return &W[i];
}

/* ---------------------------------------------------------------- CRC */
static uint8_t crc8(const uint8_t *d, int n)
{
    uint8_t c = 0xFF;
    while (n--) {
        c ^= *d++;
        for (int b = 0; b < 8; b++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x31) : (uint8_t)(c << 1);
    }
    return c;
}
static int put_word(uint8_t *o, uint16_t w)
{
    o[0] = w >> 8; o[1] = w & 0xFF; o[2] = crc8(o, 2);
    return 3;
}

/* ---------------------------------------------------------- I2C devices */
struct dev {
    uint8_t addr;
    uint8_t rx[16]; int nrx;
    uint8_t tx[16]; int ntx, itx;
    double ready_at;              /* response valid after this time */
    int periodic; double started; int served_epoch;
    long transactions, crc_errors;
};
static struct dev sgp = { .addr = 0x59 }, sht = { .addr = 0x44 }, scd = { .addr = 0x62 };
static struct dev *sel;
static int sel_read;
static int present(struct dev *d)
{
    const struct world *w = cur();
    return d == &sgp ? w->sgp : d == &sht ? w->sht : w->scd;
}

/* a write transaction finished: decode the command */
static void dev_command(struct dev *d)
{
    const struct world *w = cur();
    d->transactions++;
    d->ntx = d->itx = 0;
    if (d == &sht && d->nrx == 1 && d->rx[0] == 0xFD) {
        uint16_t st = (uint16_t)lround((w->t_amb + 45.0) * 65535.0 / 175.0);
        uint16_t srh = (uint16_t)lround((w->rh + 6.0) * 65535.0 / 125.0);
        d->ntx = put_word(d->tx, st); d->ntx += put_word(d->tx + 3, srh);
        d->ready_at = now_s() + 0.0083;               /* 8.3 ms, high repeatability */
    } else if (d == &sgp && d->nrx == 8 && d->rx[0] == 0x26 && d->rx[1] == 0x0F) {
        if (crc8(d->rx + 2, 2) != d->rx[4] || crc8(d->rx + 5, 2) != d->rx[7]) { d->crc_errors++; return; }
        double s = w->sraw;
        d->ntx = put_word(d->tx, (uint16_t)lround(s));
        d->ready_at = now_s() + 0.025;
    } else if (d == &sgp && d->nrx == 2 && d->rx[0] == 0x28 && d->rx[1] == 0x0E) {
        d->ntx = put_word(d->tx, 0xD400);
        d->ready_at = now_s() + 0.300;
    } else if (d == &scd && d->nrx == 2) {
        uint16_t c = (d->rx[0] << 8) | d->rx[1];
        double t = now_s();
        int epoch = d->periodic ? (int)((t - d->started) / 5.0) : 0;
        if (c == 0x21B1) { d->periodic = 1; d->started = t; d->served_epoch = 0; }
        else if (c == 0x3F86) { d->periodic = 0; }
        else if (c == 0xE4B8) {
            int ready = d->periodic && epoch >= 1 && epoch != d->served_epoch;
            d->ntx = put_word(d->tx, ready ? 0x8006 : 0x8000);
            d->ready_at = t + 0.001;
        } else if (c == 0xEC05) {
            d->served_epoch = epoch;
            d->ntx = put_word(d->tx, (uint16_t)lround(w->co2));
            d->ntx += put_word(d->tx + 3, (uint16_t)lround((w->t_amb + 45.0) * 65535.0 / 175.0));
            d->ntx += put_word(d->tx + 6, (uint16_t)lround(w->rh * 65535.0 / 100.0));
            d->ready_at = t + 0.001;
        }
    }
}

static avr_irq_t *twi_in;
static void twi_hook(struct avr_irq_t *irq, uint32_t value, void *param)
{
    (void)irq; (void)param;
    avr_twi_msg_irq_t v; v.u.v = value;
    if (getenv("TWI_DEBUG") && now_s() > 1.0 && now_s() < 2.1) fprintf(stderr, "%.6f twi msg=%02x addr=%02x data=%02x\n", now_s(), v.u.twi.msg, v.u.twi.addr, v.u.twi.data);
    if (v.u.twi.msg & TWI_COND_STOP) {
        if (sel && !sel_read) dev_command(sel);
        sel = NULL;
    }
    /* simavr 1.6 master: the address phase is a START message carrying
     * the address byte (SLA+R/W) in .addr */
    if (v.u.twi.msg & TWI_COND_START) {
        if (sel && !sel_read) dev_command(sel);   /* repeated start ends a write */
        sel = NULL;
        uint8_t a = v.u.twi.addr >> 1;
        struct dev *d = a == sgp.addr ? &sgp : a == sht.addr ? &sht : a == scd.addr ? &scd : NULL;
        if (d && present(d)) {
            int rd = v.u.twi.addr & 1;
            /* a read before the measurement is done is NACKed, as the parts do */
            if (rd && now_s() < d->ready_at) d = NULL;
            if (d) {
                sel = d; sel_read = rd;
                if (!rd) d->nrx = 0; else d->itx = 0;
                avr_raise_irq(twi_in, avr_twi_irq_msg(TWI_COND_ACK, v.u.twi.addr, 1));
            }
        }
        return;
    }
    if (sel) {
        if (v.u.twi.msg & TWI_COND_WRITE) {
            if (sel->nrx < 16) sel->rx[sel->nrx++] = v.u.twi.data;
            avr_raise_irq(twi_in, avr_twi_irq_msg(TWI_COND_ACK, sel->addr, 1));
        }
        if (v.u.twi.msg & TWI_COND_READ) {
            uint8_t b = sel->itx < sel->ntx ? sel->tx[sel->itx++] : 0xFF;
            avr_raise_irq(twi_in, avr_twi_irq_msg(TWI_COND_READ, sel->addr, b));
        }
    }
}

/* ------------------------------------------------------------------ UART */
static char line[512]; static int nline;
static void uart_hook(struct avr_irq_t *irq, uint32_t value, void *param)
{
    (void)irq; (void)param;
    if (value == '\n' || nline == (int)sizeof(line) - 1) {
        line[nline] = 0;
        fprintf(f_uart, "%.3f %s\n", now_s(), line);
        nline = 0;
    } else if (value != '\r') {
        line[nline++] = (char)value;
    }
}

/* -------------------------------------------------------------- sounder */
static long buz_edges;
static int buz_level;
static void buz_hook(struct avr_irq_t *irq, uint32_t value, void *param)
{
    (void)irq; (void)param;
    if ((int)(value & 1) != buz_level) { buz_level = value & 1; buz_edges++; }
}

/* -------------------------------------------------------------------- ADC */
static uint32_t ntc_mv(double t_c, double beta)
{
    double r = 10000.0 * exp(beta * (1.0 / (t_c + 273.15) - 1.0 / 298.15));
    return (uint32_t)lround(3300.0 * r / (10000.0 + r));
}

static void no_sleep(avr_t *a, avr_cycle_count_t n) { (void)a; (void)n; }

static int load_world(const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char buf[512];
    if (!fgets(buf, sizeof buf, f)) { fclose(f); return 0; }   /* header */
    while (fgets(buf, sizeof buf, f) && nW < MAXS) {
        struct world *w = &W[nW];
        char *p = buf, *tok;
        double v[11]; int k = 0;
        while ((tok = strsep(&p, ",\n")) && k < 11) v[k++] = (*tok ? atof(tok) : NAN);
        w->t_pack = v[1]; w->t_probe = v[2]; w->t_amb = v[3]; w->rh = v[4]; w->sraw = v[5];
        w->co2 = v[6]; w->sgp = (int)v[7]; w->sht = (int)v[8]; w->scd = (int)v[9]; w->button = (int)v[10];
        nW++;
    }
    fclose(f);
    return nW;
}

int main(int argc, char **argv)
{
    if (argc < 4) { fprintf(stderr, "usage: harness fw.elf world.csv out_prefix\n"); return 2; }
    elf_firmware_t fw;
    memset(&fw, 0, sizeof fw);
    if (elf_read_firmware(argv[1], &fw)) { fprintf(stderr, "cannot read %s\n", argv[1]); return 2; }
    if (!load_world(argv[2])) { fprintf(stderr, "cannot read %s\n", argv[2]); return 2; }
    char path[512];
    snprintf(path, sizeof path, "%s_uart.log", argv[3]); f_uart = fopen(path, "w");
    snprintf(path, sizeof path, "%s_io.csv", argv[3]); f_out = fopen(path, "w");
    fprintf(f_out, "t,green,amber,red,tone_on,buz_hz\n");

    avr = avr_make_mcu_by_name("atmega328p");
    avr_init(avr);
    avr_load_firmware(avr, &fw);
    avr->frequency = 8000000;
    avr->vcc = avr->avcc = avr->aref = 3300;
    avr->log = LOG_WARNING;
    avr->sleep = no_sleep;           /* simulated time, not wall-clock */
    if (getenv("AVR_TRACE_LOG")) avr->log = LOG_TRACE;

    uint32_t fl = 0;
    avr_ioctl(avr, AVR_IOCTL_UART_GET_FLAGS('0'), &fl);
    fl &= ~AVR_UART_FLAG_STDIO;
    avr_ioctl(avr, AVR_IOCTL_UART_SET_FLAGS('0'), &fl);
    avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT), uart_hook, NULL);

    twi_in = avr_io_getirq(avr, AVR_IOCTL_TWI_GETIRQ(0), TWI_IRQ_INPUT);
    if (!twi_in) { fprintf(stderr, "no TWI irq\n"); return 2; }
    avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_TWI_GETIRQ(0), TWI_IRQ_OUTPUT), twi_hook, NULL);
    avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ('B'), 1), buz_hook, NULL);
    avr_irq_t *btn = avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ('D'), 2);
    avr_irq_t *adc0 = avr_io_getirq(avr, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_ADC0);
    avr_irq_t *adc1 = avr_io_getirq(avr, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_ADC1);
    avr_raise_irq(btn, 1);                    /* external 10k pull-up */

    double end = nW;
    uint64_t step = avr->frequency / 1000;    /* sample the world every 1 ms */
    uint64_t next = 0;
    double acc_g = 0, acc_a = 0, acc_r = 0, acc_tone = 0; int nacc = 0;
    long edges0 = 0; double t_rep = 0.1;
    while (now_s() < end) {
        int st = avr_run(avr);
        if (st == cpu_Done || st == cpu_Crashed) { fprintf(stderr, "cpu stopped (%d) at %.3f s\n", st, now_s()); return 1; }
        if (avr->cycle < next) continue;
        next = avr->cycle + step;
        const struct world *w = cur();
        avr_raise_irq(adc0, ntc_mv(w->t_pack, 3380.0));
        avr_raise_irq(adc1, isnan(w->t_probe) ? 3300 : ntc_mv(w->t_probe, 3950.0));
        double frac = now_s() - floor(now_s());
        avr_raise_irq(btn, (w->button && frac < 0.2) ? 0 : 1);

        /* what you see: PWM duty if the compare output is connected */
        uint8_t *d = avr->data;
        double g = (d[0xB0] & 0x20) ? d[0xB4] / 255.0 : 0;   /* TCCR2A COM2B1, OCR2B */
        double a = (d[0x44] & 0x20) ? d[0x48] / 255.0 : 0;   /* TCCR0A COM0B1, OCR0B */
        double r = (d[0x44] & 0x80) ? d[0x47] / 255.0 : 0;   /* TCCR0A COM0A1, OCR0A */
        int tone = (d[0x80] & 0x40) != 0;                    /* TCCR1A COM1A0 */
        acc_g += g; acc_a += a; acc_r += r; acc_tone += tone; nacc++;
        if (now_s() >= t_rep) {
            double hz = (buz_edges - edges0) / 2.0 / 0.1;
            fprintf(f_out, "%.1f,%.3f,%.3f,%.3f,%.2f,%.0f\n", t_rep, acc_g / nacc, acc_a / nacc,
                    acc_r / nacc, acc_tone / nacc, hz);
            edges0 = buz_edges; acc_g = acc_a = acc_r = acc_tone = 0; nacc = 0;
            t_rep += 0.1;
        }
    }
    fprintf(stderr, "done: %.1f s simulated; i2c transactions sgp=%ld sht=%ld scd=%ld crc_err=%ld\n",
            now_s(), sgp.transactions, sht.transactions, scd.transactions, sgp.crc_errors);
    fclose(f_uart); fclose(f_out);
    return 0;
}
