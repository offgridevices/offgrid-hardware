/* Canary v1 firmware: ATmega328P @ 8 MHz internal RC, 3.3 V.
 *
 * Once a second: read the pack temperature (NTCs), humidity and air
 * temperature (SHT40), the VOC raw signal (SGP40, humidity-compensated) and,
 * every 5 s, CO2 (SCD41); run the detector (detect.c); drive the LEDs and
 * the sounder; print one telemetry line on the TXD pad (38400 8N1).
 */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <util/delay.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "board.h"
#include "detect.h"

#define FW_VERSION "1.0.0"

/* ------------------------------------------------------------- timebase */
/* Timer2 fast PWM, /64: overflow at 8 MHz / 64 / 256 = 488.28 Hz */
static volatile uint32_t ticks;
static volatile uint8_t btn_low_ms, btn_event;

static uint32_t now_ms(void)
{
    uint32_t t;
    cli(); t = ticks; sei();
    return (t * 2048UL) / 1000UL;
}

ISR(TIMER2_OVF_vect)
{
    ticks++;
    /* button: PD2 low = pressed; event on release after >= 30 ms */
    if (!(PIND & _BV(PIN_BTN))) {
        if (btn_low_ms < 250) btn_low_ms++;
    } else {
        if (btn_low_ms >= 15) btn_event = 1;
        btn_low_ms = 0;
    }
}

static void wait_ms(uint16_t ms)
{
    uint32_t end = now_ms() + ms;
    while ((int32_t)(now_ms() - end) < 0) {
        sleep_mode();
        wdt_reset();
    }
}

/* --------------------------------------------------------- LEDs, sound */
static void leds(uint8_t g, uint8_t a, uint8_t r)
{
    OCR2B = g; OCR0B = a; OCR0A = r;
}

static void tone(uint8_t on)
{
    if (on) TCCR1A |= _BV(COM1A0);
    else { TCCR1A &= ~_BV(COM1A0); PORTB &= ~_BV(PIN_BUZ); }
}

static void io_init(void)
{
    DDRD |= _BV(PIN_LED_GRN) | _BV(PIN_LED_AMB) | _BV(PIN_LED_RED) | _BV(PIN_TXD);
    DDRB |= _BV(PIN_BUZ);
    PORTB &= ~_BV(PIN_BUZ);
    /* Timer0: fast PWM on OC0A (red) and OC0B (amber), /64 */
    TCCR0A = _BV(COM0A1) | _BV(COM0B1) | _BV(WGM01) | _BV(WGM00);
    TCCR0B = _BV(CS01) | _BV(CS00);
    /* Timer2: fast PWM on OC2B (green), /64, overflow = tick */
    TCCR2A = _BV(COM2B1) | _BV(WGM21) | _BV(WGM20);
    TCCR2B = _BV(CS22);
    TIMSK2 = _BV(TOIE2);
    /* Timer1: CTC, toggle OC1A at 2 x BUZ_HZ -> BUZ_HZ square wave */
    TCCR1A = 0;
    TCCR1B = _BV(WGM12) | _BV(CS10);
    OCR1A = (uint16_t)(F_CPU_HZ / (2UL * BUZ_HZ) - 1);
    leds(0, 0, 0);
    /* ADC: AVcc reference, /64 = 125 kHz */
    ADMUX = _BV(REFS0);
    ADCSRA = _BV(ADEN) | _BV(ADPS2) | _BV(ADPS1);
    DIDR0 = _BV(ADC0D) | _BV(ADC1D);
    /* USART0: 38400 8N1, U2X */
    UCSR0A = _BV(U2X0);
    UBRR0 = 25;
    UCSR0B = _BV(TXEN0);
    /* TWI: 100 kHz */
    TWSR = 0;
    TWBR = (uint8_t)((F_CPU_HZ / 100000UL - 16) / 2);
    set_sleep_mode(SLEEP_MODE_IDLE);
}

/* ------------------------------------------------------------------ UART */
static int uart_putc(char c, FILE *f)
{
    (void)f;
    while (!(UCSR0A & _BV(UDRE0)))
        ;
    UDR0 = c;
    return 0;
}
static FILE uart = FDEV_SETUP_STREAM(uart_putc, NULL, _FDEV_SETUP_WRITE);

/* ------------------------------------------------------------------- I2C */
static uint8_t twi_wait(void)
{
    uint16_t n = 0;
    while (!(TWCR & _BV(TWINT)))
        if (++n > 20000) return 0;            /* ~10 ms: bus stuck */
    return 1;
}
static uint8_t twi_start(uint8_t addr_rw)
{
    TWCR = _BV(TWINT) | _BV(TWSTA) | _BV(TWEN);
    if (!twi_wait()) return 0;
    TWDR = addr_rw;
    TWCR = _BV(TWINT) | _BV(TWEN);
    if (!twi_wait()) return 0;
    uint8_t st = TWSR & 0xF8;
    return st == 0x18 || st == 0x40;          /* SLA+W ACK / SLA+R ACK */
}
static void twi_stop(void) { TWCR = _BV(TWINT) | _BV(TWSTO) | _BV(TWEN); }

static uint8_t i2c_write(uint8_t addr, const uint8_t *b, uint8_t n)
{
    uint8_t ok = twi_start(addr << 1);
    for (uint8_t i = 0; ok && i < n; i++) {
        TWDR = b[i];
        TWCR = _BV(TWINT) | _BV(TWEN);
        ok = twi_wait() && (TWSR & 0xF8) == 0x28;
    }
    twi_stop();
    return ok;
}
static uint8_t i2c_read(uint8_t addr, uint8_t *b, uint8_t n)
{
    uint8_t ok = twi_start((addr << 1) | 1);
    for (uint8_t i = 0; ok && i < n; i++) {
        TWCR = _BV(TWINT) | _BV(TWEN) | (i + 1 < n ? _BV(TWEA) : 0);
        ok = twi_wait();
        b[i] = TWDR;
    }
    twi_stop();
    return ok;
}

/* Sensirion CRC-8: polynomial 0x31, init 0xFF */
static uint8_t crc8(const uint8_t *d, uint8_t n)
{
    uint8_t c = 0xFF;
    while (n--) {
        c ^= *d++;
        for (uint8_t b = 0; b < 8; b++)
            c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x31) : (uint8_t)(c << 1);
    }
    return c;
}
static uint8_t words_ok(const uint8_t *b, uint8_t nwords)
{
    for (uint8_t i = 0; i < nwords; i++)
        if (crc8(b + 3 * i, 2) != b[3 * i + 2]) return 0;
    return 1;
}
static uint8_t cmd16(uint8_t addr, uint16_t cmd)
{
    uint8_t b[2] = { cmd >> 8, cmd & 0xFF };
    return i2c_write(addr, b, 2);
}

/* --------------------------------------------------------------- sensors */
static int16_t amb_c10 = 250;     /* SHT40 air temperature, 0.1 C */
static uint16_t rh_ticks = 0x8000, t_ticks = 0x6666;   /* SGP40 compensation inputs */
static uint8_t rh_pct = 50;

static uint8_t sht40_read(void)
{
    uint8_t b[6];
    uint8_t c = 0xFD;                        /* measure, high repeatability */
    if (!i2c_write(I2C_SHT40, &c, 1)) return 0;
    wait_ms(10);
    if (!i2c_read(I2C_SHT40, b, 6) || !words_ok(b, 2)) return 0;
    uint16_t st = ((uint16_t)b[0] << 8) | b[1], srh = ((uint16_t)b[3] << 8) | b[4];
    amb_c10 = (int16_t)(-450 + (int32_t)1750 * st / 65535);
    int32_t rh = -6 + (int32_t)125 * srh / 65535;
    rh_pct = rh < 0 ? 0 : (rh > 100 ? 100 : rh);
    /* SGP40 compensation words: RH%*65535/100, (T+45)*65535/175 */
    rh_ticks = (uint16_t)((uint32_t)rh_pct * 65535UL / 100);
    t_ticks = (uint16_t)((uint32_t)(amb_c10 + 450) * 65535UL / 1750);
    return 1;
}

static uint8_t sgp40_read(uint16_t *sraw)
{
    uint8_t b[8] = { 0x26, 0x0F, rh_ticks >> 8, rh_ticks & 0xFF, 0, t_ticks >> 8, t_ticks & 0xFF, 0 };
    b[4] = crc8(b + 2, 2);
    b[7] = crc8(b + 5, 2);
    if (!i2c_write(I2C_SGP40, b, 8)) return 0;
    wait_ms(30);
    uint8_t r[3];
    if (!i2c_read(I2C_SGP40, r, 3) || !words_ok(r, 1)) return 0;
    *sraw = ((uint16_t)r[0] << 8) | r[1];
    return 1;
}

static uint8_t sgp40_selftest(void)
{
    if (!cmd16(I2C_SGP40, 0x280E)) return 0;
    wait_ms(320);
    uint8_t r[3];
    if (!i2c_read(I2C_SGP40, r, 3) || !words_ok(r, 1)) return 0;
    return r[0] == 0xD4 && r[1] == 0x00;
}

static uint8_t scd41_start(void)
{
    cmd16(I2C_SCD41, 0x3F86);               /* stop_periodic_measurement */
    wait_ms(500);
    return cmd16(I2C_SCD41, 0x21B1);        /* start_periodic_measurement (5 s) */
}

/* returns 0 = bus error, 1 = no new data, 2 = new reading */
static uint8_t scd41_poll(uint16_t *ppm)
{
    uint8_t r[9];
    if (!cmd16(I2C_SCD41, 0xE4B8)) return 0; /* get_data_ready_status */
    wait_ms(2);
    if (!i2c_read(I2C_SCD41, r, 3) || !words_ok(r, 1)) return 0;
    if (!((((uint16_t)r[0] << 8) | r[1]) & 0x07FF)) return 1;
    if (!cmd16(I2C_SCD41, 0xEC05)) return 0; /* read_measurement */
    wait_ms(2);
    if (!i2c_read(I2C_SCD41, r, 9) || !words_ok(r, 3)) return 0;
    *ppm = ((uint16_t)r[0] << 8) | r[1];
    return 2;
}

static uint16_t adc_read(uint8_t ch)
{
    ADMUX = _BV(REFS0) | ch;
    uint16_t s = 0;
    for (uint8_t i = 0; i < 5; i++) {
        ADCSRA |= _BV(ADSC);
        while (ADCSRA & _BV(ADSC))
            ;
        if (i) s += ADC;                     /* first conversion after mux change discarded */
    }
    return s / 4;
}

/* 0.1 C from a 10-bit reading of NTC-low-side divider; INT16_MIN if open/short */
static int16_t ntc_c10(uint16_t adc, float beta)
{
    if (adc < 15 || adc > 1008) return INT16_MIN;
    float r = NTC_R25 * (float)adc / (float)(1023 - adc);
    float t = 1.0f / (1.0f / 298.15f + logf(r / NTC_R25) / beta) - 273.15f;
    return (int16_t)lrintf(t * 10.0f);
}

/* ------------------------------------------------------------- patterns */
static uint8_t tri(uint32_t ms, uint16_t period, uint8_t peak)
{
    uint16_t p = ms % period, h = period / 2;
    uint16_t v = p < h ? p : period - p;
    return (uint8_t)((uint32_t)v * peak / h);
}

/* Temporal-three (as smoke alarms use): 0.5 on, 0.5 off x3, then 1.5 off */
static uint8_t t3(uint32_t ms)
{
    uint16_t p = ms % 4000;
    return p < 3000 && (p % 1000) < 500;
}

static void render(const struct detector *d, uint32_t ms, uint32_t chirp_until)
{
    switch (d->state) {
    case ST_WARMUP: leds((ms % 1000) < 500 ? 40 : 0, 0, 0); break;
    case ST_NORMAL: leds(tri(ms, 4000, 48), 0, 0); break;
    case ST_WARN:   leds(0, (ms % 1000) < 250 ? 255 : 0, 0); break;
    case ST_ALARM:  leds(0, 0, (ms % 250) < 125 ? 255 : 0); break;
    case ST_FAULT:  { uint16_t p = ms % 2000;
                      leds(0, (p < 120 || (p >= 300 && p < 420)) ? 255 : 0, 0); } break;
    }
    uint8_t s = detect_sound(d) ? t3(ms - d->alarm_since * 1000UL) : 0;
    tone(s || (int32_t)(chirp_until - ms) > 0);
}

/* -------------------------------------------------------------------- main */
static void selftest(struct inputs *in)
{
    leds(60, 0, 0); wait_ms(300);
    leds(0, 255, 0); wait_ms(300);
    leds(0, 0, 255); tone(1); wait_ms(300); tone(0);
    leds(0, 0, 0);
    uint8_t ok = sgp40_selftest();
    printf("selftest sgp40=%s\n", ok ? "ok" : "FAIL");
    if (!ok) in->faults |= F_SGP40;
}

int main(void)
{
    MCUSR = 0;
    wdt_enable(WDTO_2S);
    io_init();
    stdout = &uart;
    sei();
    printf("\nCANARY v1 fw " FW_VERSION "\n");

    static struct detector det;
    detect_init(&det);
    uint8_t scd_ok = scd41_start();
    uint16_t co2 = 0;
    uint8_t last_state = ST_WARMUP;
    uint32_t next = now_ms() + 1000, chirp_until = 0, last_fault_chirp = 0;

    for (;;) {
        uint32_t ms = now_ms();
        render(&det, ms, chirp_until);
        if ((int32_t)(ms - next) < 0) {
            sleep_mode();
            wdt_reset();
            continue;
        }
        next += 1000;

        struct inputs in;
        memset(&in, 0, sizeof(in));
        cli(); in.button = btn_event; btn_event = 0; sei();

        int16_t tb = ntc_c10(adc_read(ADC_CH_NTC_BRD), NTC_B_BRD);
        int16_t tp = ntc_c10(adc_read(ADC_CH_NTC_PRB), NTC_B_PRB);   /* probe optional */
        if (tb == INT16_MIN) in.faults |= F_NTC;
        in.t_pack_c10 = (tp != INT16_MIN && tp > tb) ? tp : tb;

        if (!sht40_read()) in.faults |= F_SHT40;
        if (!sgp40_read(&in.sraw)) in.faults |= F_SGP40;
        uint8_t s = scd_ok ? scd41_poll(&co2) : 0;
        if (!s) { in.faults |= F_SCD41; scd_ok = scd41_start(); }
        in.co2_new = (s == 2);
        in.co2_ppm = co2;

        if (in.button && det.state != ST_ALARM) {
            selftest(&in);
            in.button = 0;
        }
        detect_step(&det, &in);

        ms = now_ms();
        if (det.state == ST_WARN && last_state != ST_WARN && last_state != ST_ALARM)
            chirp_until = ms + 80;
        if (det.state == ST_FAULT && ms - last_fault_chirp > 60000UL) {
            chirp_until = ms + 40;
            last_fault_chirp = ms;
        }
        last_state = det.state;

        printf("t=%lu st=%u tp=%d tb=%d tpr=%d ta=%d rh=%u sraw=%u gdev=%u co2=%u rate=%d ex=%d dtdt=%d e=%u%u%u f=%02x snd=%u hush=%u\n",
               (unsigned long)det.t, det.state, in.t_pack_c10, tb, tp == INT16_MIN ? -9999 : tp,
               amb_c10, rh_pct, in.sraw, det.gas_dev, co2, det.co2_rate, det.co2_excess,
               det.dtdt_c10, det.e_gas, det.e_co2, det.e_heat, in.faults, detect_sound(&det),
               det.hushed);
    }
}
