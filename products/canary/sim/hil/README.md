# Hardware-in-the-loop simulation

`harness.c` runs the real `firmware/build/canary.elf` on simavr's ATmega328P
with virtual Sensirion SGP40 (0x59), SHT40 (0x44) and SCD41 (0x62) on the TWI
bus, NTC voltages on ADC0/ADC1 and the button on PD2. It records LED PWM
duty, the sounder pin's edges and the UART telemetry. `scenarios.py` builds
eight worlds, runs them in parallel and checks what a person would see and
hear. Results: `out/results.json`, plots `out/*.png`, summary in `../../TESTS.md`.

simavr: use upstream master (tested at 5b08da6). The Ubuntu 24.04 package
(1.6) acknowledges SLA+W with TWI status 0x28 instead of 0x18, which a polled
TWI master (correctly) treats as a failure.

```sh
git clone https://github.com/buserror/simavr /opt/simavr && make -C /opt/simavr build-simavr
mkdir -p /opt/simavr-inc && ln -sfn /opt/simavr/simavr/sim /opt/simavr-inc/simavr
gcc -O2 -I/opt/simavr-inc -I/opt/simavr/simavr/obj-x86_64-linux-gnu -o harness harness.c \
    /opt/simavr/simavr/obj-x86_64-linux-gnu/libsimavr.a -lelf -lm
make -C ../../firmware && python3 scenarios.py
```
