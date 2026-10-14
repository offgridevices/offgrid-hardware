/* Canary vent-signature detector. See detect.h. */
#include "detect.h"
#include <string.h>

void detect_init(struct detector *d)
{
    memset(d, 0, sizeof(*d));
    d->state = ST_WARMUP;
}

static void gas_update(struct detector *d, uint16_t sraw)
{
    int32_t s = (int32_t)sraw << 8;
    if (!d->gas_init) {
        d->gas_base_q8 = s;
        d->gas_init = 1;
    } else if (d->t < WARMUP_S) {
        d->gas_base_q8 += (s - d->gas_base_q8) >> 2;          /* learn quickly */
    } else if (s > d->gas_base_q8) {
        d->gas_base_q8 += (s - d->gas_base_q8) >> 3;          /* cleaner air: follow */
    } else if (d->gas_dev < GAS_WEAK) {
        d->gas_base_q8 -= (d->gas_base_q8 - s) >> 11;         /* slow drift, ~35 min */
    }                                                          /* event: freeze */
    int32_t dev = (d->gas_base_q8 >> 8) - (int32_t)sraw;
    d->gas_dev = dev < 0 ? 0 : (dev > 60000 ? 60000 : (uint16_t)dev);
}

static void co2_update(struct detector *d, uint16_t ppm)
{
    d->co2_hist[d->co2_i] = ppm;
    d->co2_i = (d->co2_i + 1) % 13;
    if (d->co2_n < 13) d->co2_n++;
    if (d->co2_n == 1) d->co2_base_q4 = (int32_t)ppm << 4;
    uint8_t oldest = (d->co2_n < 13) ? 0 : d->co2_i;
    int32_t span_s = (int32_t)(d->co2_n - 1) * 5;
    d->co2_rate = span_s ? (int16_t)(((int32_t)ppm - d->co2_hist[oldest]) * 60 / span_s) : 0;
    int32_t p = (int32_t)ppm << 4;
    if (p < d->co2_base_q4)
        d->co2_base_q4 += (p - d->co2_base_q4) >> 2;
    else if (d->co2_excess < 1000)
        d->co2_base_q4 += (p - d->co2_base_q4) >> 9;
    int32_t ex = (int32_t)ppm - (d->co2_base_q4 >> 4);
    d->co2_excess = ex < 0 ? 0 : (ex > 30000 ? 30000 : (int16_t)ex);
}

static void heat_update(struct detector *d, int16_t t)
{
    if (d->t % 10 != 0 && d->t_n)
        return;
    d->t_hist[d->t_i] = t;
    d->t_i = (d->t_i + 1) % 7;
    if (d->t_n < 7) d->t_n++;
    uint8_t oldest = (d->t_n < 7) ? 0 : d->t_i;
    int32_t span_s = (int32_t)(d->t_n - 1) * 10;
    d->dtdt_c10 = span_s ? (int16_t)(((int32_t)t - d->t_hist[oldest]) * 60 / span_s) : 0;
}

static uint8_t grade(int32_t v, int32_t weak, int32_t strong)
{
    return v >= strong ? STRONG : (v >= weak ? WEAK : NONE);
}

void detect_step(struct detector *d, const struct inputs *in)
{
    d->t++;
    d->faults = in->faults;
    if (!(in->faults & F_SGP40))
        gas_update(d, in->sraw);
    if (in->co2_new && !(in->faults & F_SCD41))
        co2_update(d, in->co2_ppm);
    if (!(in->faults & F_NTC))
        heat_update(d, in->t_pack_c10);

    int16_t tp = in->t_pack_c10;
    d->e_gas = (d->t < WARMUP_S || (in->faults & F_SGP40)) ? NONE : grade(d->gas_dev, GAS_WEAK, GAS_STRONG);
    uint8_t r = grade(d->co2_rate, CO2_RATE_WEAK, CO2_RATE_STRONG);
    uint8_t x = grade(d->co2_excess, 1500, CO2_EXCESS_STRONG);
    d->e_co2 = (in->faults & F_SCD41) ? NONE : (r > x ? r : x);
    if (in->faults & F_NTC) {
        d->e_heat = NONE;
    } else {
        uint8_t a = grade(tp, T_WEAK_C10, T_STRONG_C10);
        uint8_t b = grade(d->dtdt_c10, DTDT_WEAK_C10, DTDT_STRONG_C10);
        if (b == STRONG && tp < DTDT_STRONG_MIN_C10) b = WEAK;
        if (b == WEAK && tp < DTDT_MIN_T_C10) b = NONE;
        d->e_heat = a > b ? a : b;
    }

    uint8_t g = d->e_gas, c = d->e_co2, h = d->e_heat;
    uint8_t alarm = (g && c && (g == STRONG || c == STRONG))   /* vent signature    */
                 || (h == STRONG)                               /* runaway heat      */
                 || (h && (g || c))                             /* heat + any gas    */
                 || (g == STRONG && c == STRONG);
    uint8_t warn = g || c || h;
    uint8_t sum = g + c + h;

    d->persist = alarm ? (d->persist < 255 ? d->persist + 1 : 255) : 0;

    if (d->state == ST_ALARM) {
        if (alarm)
            d->alarm_clear_at = d->t + ALARM_HOLD_S;
        if (in->button && !d->hushed) {
            d->hushed = 1;
            d->hush_until = d->t + HUSH_S;
            d->evidence_at_hush = sum;
        } else if (d->hushed && (d->t >= d->hush_until || sum > d->evidence_at_hush)) {
            d->hushed = 0;                     /* hush expired, or it got worse */
        }
        if (!alarm && d->t >= d->alarm_clear_at) {
            d->hushed = 0;
            d->state = warn ? ST_WARN : ST_NORMAL;
        }
        return;
    }
    if (d->persist >= PERSIST_S) {
        d->state = ST_ALARM;
        d->alarm_since = d->t;
        d->alarm_clear_at = d->t + ALARM_HOLD_S;
        d->hushed = 0;
        return;
    }
    if (d->t < WARMUP_S)
        d->state = ST_WARMUP;
    else if (in->faults & (F_SGP40 | F_SCD41 | F_SHT40 | F_NTC))
        d->state = ST_FAULT;
    else
        d->state = warn ? ST_WARN : ST_NORMAL;
}

uint8_t detect_sound(const struct detector *d)
{
    return d->state == ST_ALARM && !d->hushed;
}
