/* Canary vent-signature detector: pure logic, no hardware. Runs once a
 * second on the AVR and, unchanged, in the host unit tests.
 *
 * Three independent kinds of evidence, each graded NONE / WEAK / STRONG:
 *   gas   - SGP40 raw signal falling below its learned clean-air baseline
 *           (electrolyte solvent vapour: DMC, EMC, DEC; also H2 and CO)
 *   co2   - SCD41 CO2 rising fast (CO2 is a large share of vent gas)
 *   heat  - pack surface temperature high, or rising fast
 *
 * A household smell gives gas alone; a person breathing gives CO2 alone;
 * a warm room gives slow heat. A venting lithium cell gives solvent AND
 * CO2 together, then heat. ALARM needs two kinds of evidence (or one kind
 * at an extreme), WARN needs one.
 */
#ifndef DETECT_H
#define DETECT_H
#include <stdint.h>

enum level { NONE = 0, WEAK = 1, STRONG = 2 };
enum state { ST_WARMUP = 0, ST_NORMAL, ST_WARN, ST_ALARM, ST_FAULT };

/* Thresholds (see firmware/README.md and docs/decisions.md). */
#define WARMUP_S            90      /* SGP40 needs ~1 min to settle            */
#define GAS_WEAK            700     /* SRAW ticks below baseline               */
#define GAS_STRONG          2500
#define CO2_RATE_WEAK       250     /* ppm per minute                          */
#define CO2_RATE_STRONG     1200
#define CO2_EXCESS_STRONG   4000    /* ppm above learned baseline              */
#define T_WEAK_C10          500     /* 50.0 C pack surface                     */
#define T_STRONG_C10        650     /* 65.0 C                                  */
#define DTDT_WEAK_C10       10      /* 1.0 C per minute (pack above 35 C)      */
#define DTDT_STRONG_C10     30      /* 3.0 C per minute                        */
#define DTDT_MIN_T_C10      350     /* weak rate counts above 35 C          */
#define DTDT_STRONG_MIN_C10 300     /* strong rate counts above 30 C        */
#define PERSIST_S           3       /* evidence must hold this long            */
#define ALARM_HOLD_S        60      /* alarm stays at least this long          */
#define HUSH_S              120

#define F_SGP40   0x01
#define F_SHT40   0x02
#define F_SCD41   0x04
#define F_NTC     0x08

struct inputs {
    uint8_t  faults;        /* F_* bits for sensors that failed this second */
    uint16_t sraw;          /* SGP40 raw ticks                              */
    int16_t  t_pack_c10;    /* pack surface temperature, 0.1 C              */
    uint16_t co2_ppm;       /* latest SCD41 reading (0 = none yet)          */
    uint8_t  co2_new;       /* 1 when co2_ppm is a fresh reading            */
    uint8_t  button;        /* 1 on a short press this second               */
};

struct detector {
    uint32_t t;             /* seconds since power-up                       */
    uint8_t  state;
    /* gas */
    int32_t  gas_base_q8;   /* baseline SRAW, Q8                            */
    uint8_t  gas_init;
    uint16_t gas_dev;       /* baseline - sraw, ticks                       */
    /* co2: 13 readings, one per 5 s = 60 s window                         */
    uint16_t co2_hist[13];
    uint8_t  co2_n, co2_i;
    int32_t  co2_base_q4;
    int16_t  co2_rate;      /* ppm per minute                               */
    int16_t  co2_excess;
    /* heat: one sample per 10 s, 7 entries = 60 s window                  */
    int16_t  t_hist[7];
    uint8_t  t_n, t_i;
    int16_t  dtdt_c10;      /* 0.1 C per minute                             */
    /* evidence and timing */
    uint8_t  e_gas, e_co2, e_heat;
    uint8_t  persist;
    uint32_t alarm_since, alarm_clear_at;
    uint32_t hush_until;
    uint8_t  hushed;
    uint8_t  evidence_at_hush;
    uint8_t  faults;
};

void detect_init(struct detector *d);
void detect_step(struct detector *d, const struct inputs *in);
/* 1 when the sounder should be on in this state (pattern is the caller's) */
uint8_t detect_sound(const struct detector *d);

#endif
