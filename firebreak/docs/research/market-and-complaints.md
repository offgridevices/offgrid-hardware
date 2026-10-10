> Research notes written before designing Firebreak (10 October 2026).
> Prices and listings are as found on that date and will have moved.
> The decisions they led to are in [`../../SPEC.md`](../../SPEC.md).

# Smoke stoppers: what exists, and what people complain about

## Coverage and limits

- **Read:** IntoFPV threads (2019–2026), Oscar Liang articles and their
  comments, RaceDayQuads reviews (through the Yotpo API), Pyrodrone,
  Rotorama, FlyingTech, Amazon, KiwiQuads, maker pages.
- **Could not read:** Reddit (blocked), YouTube comments, AliExpress
  reviews, GetFPV (403), vi-fly.com. VIFLY's specs come from retailers and
  Oscar Liang's review.
- **Not found:** no smoke stopper from Lumenier, ImmersionRC, Flywoo,
  HGLRC, BetaFPV, Happymodel, Matek, Foxeer, RadioMaster, Diatone or
  Axisflying. Treat this as "not found", not as "does not exist".
- One 2026 "guide" (blog.uavmodel.com) claims products and settings nobody
  else corroborates and reads as machine-written. It is left out.

---

## 1. The market

Two kinds of product:

- **Polyfuse (PPTC) or bulb, $5–8.** A resistor in series that heats up and
  limits current. Trips in 100–500 ms. Never fully cuts off.
- **"Smart" electronic fuse, $15–23.** A MOSFET that cuts off when a
  current sensor reads more than 1 A or 2 A. Trips in 3–20 ms.

| Product | Price | Cells | Trip | How | Connectors | UI |
|---|---|---|---|---|---|---|
| VIFLY ShortSaver 2 (2021) | $15.99–17.49 | 2–6S (7–25 V) | 1 A / 2 A switch; 3 ms short, 10 ms over-current | Electronic fuse, full cut-off | XT30 + XT60 | LEDs, power button (for binding) |
| SpeedyBee Smart Power Tester | ≈ $20–23 | **4–6S only** | 1 A / 2 A, ~5 ms; limit only changeable when off | Software cut-off + 2 A backup fuse | XT60 only | V/A display, button. Marked discontinued at Rotorama |
| iFlight Smart Smoke Stopper | $7.99–10.99 | 2–6S (some pages say 2–8S) | Fixed 1.2 A trip | "Electronic fuse" (unverified) | XT30 + XT60; XT90 version (8S, sold out) | LED, beeper |
| TBS Smoke Stopper | $7.99 | **1–14S (3–60 V)** | Fixed 1.0 A trip | Polyfuse | XT30 + XT60 | none |
| RDQ × Bengineering | $4.99–6.95 | 1–5S | 2.2 A trip, 0.5 s | Polyfuse | XT30 or XT60 | LED; unplug 10 s to reset |
| JHEMCU / GEPRC / DarwinFPV / Amass | $5–8 | 1–6S | ~1 A, 20–500 ms | Polyfuse | XT30 + XT60 | LED, some beep |
| Fractal 1S Sparkyguard | $10.50–22.50 | **1S only** | Folds back to 0.65 A above 3 A, µs response | Active limiter | A30 / BT2 | LED |
| ToolkitRC P200 V2 (bench supply) | ≈ $80 | 1–30 V out | 1–10 A adjustable, < 1 ms | Lab supply | Banana / XT60 | Display |

Related, not smoke stoppers:

- **Anti-spark filters** (iFlight $15–17, DarwinFPV $14.99, Flipsky 200 A
  13S ~$30–51, Hobbywing SEPS 14S ~$98): limit inrush, stay on in flight,
  **do not detect shorts**.

Sources:
[Oscar Liang – ShortSaver](https://oscarliang.com/vifly-shortsaver/) ·
[RDQ – ShortSaver 2](https://www.racedayquads.com/products/vifly-short-saver-2-smoke-stopper-xt30-xt60) ·
[Pyrodrone smoke stoppers](https://pyrodrone.com/collections/smoke-stoppers) ·
[FlyingTech – SpeedyBee](https://www.flyingtech.co.uk/product/speedybee-short-circuit-protector-smart-power-tester-smoke-stopper/) ·
[Rotorama – SpeedyBee](https://www.rotorama.com/product/speedy-bee-ochrana-proti-zkratu) ·
[iFlight](https://shop.iflight.com/smart-smoke-stopper-xt60-xt30-pro1407) ·
[TBS at Pyrodrone](https://pyrodrone.com/collections/smoke-stoppers/products/tbs-smoke-stopper) ·
[RDQ × Bengineering](https://www.racedayquads.com/products/smoke-stopper-xt30-by-rdq-and-bengineeringlabs-modern-led) ·
[DarwinFPV](https://darwinfpv.com/products/darwinfpv-xt30-xt60-2-in-1-short-circuit-protector) ·
[Fractal Sparkyguard](https://store.fractalengineering.net/product/fractal-1s-sparkyguard/) ·
[ToolkitRC P200 at Motion RC](https://motionrc.com/products/toolkitrc-p200-v2-200w-10a-mini-desktop-dc-power-supply-tk23100) ·
[iFlight anti-spark](https://www.rotorama.com/product/iflight-anti-spark-filter) ·
[DarwinFPV anti-spark](https://darwinfpv.com/products/darwinfpv-anti-spark-xt60-filter-for-fpv-drone)

### Gaps nobody fills

- **No smart (cut-off) smoke stopper above 6S.** Above 6S there are only
  polyfuses (TBS 14S, iFlight XT90 8S).
- **No smart one for 1S** except a 1S-only niche part. ShortSaver needs
  7 V, SpeedyBee needs 4S.
- **No native whoop connector** (BT2.0, PH2.0, A30) on a smart unit.
- **No maker publishes on-resistance or a continuous rating.** Everything
  is a 1–3 A plug-in test.
- The category is stale: in June 2025 forums still recommend the 2021
  ShortSaver 2.

---

## 2. What people complain about (ranked)

### 1. False trips on healthy builds — by far the most common

Inrush into the ESC's capacitors, ESC start-up tones, digital VTXs and
bigger packs trip 1 A / 2 A units.

- "instantly trips out on ALL my 5 inch quads, even on the 2 amp setting"
  — RDQ review, ShortSaver 2.
- ShortSaver V1 "would almost always cut off the power as soon as I connect
  a 4S 1500mAh battery" — [Oscar Liang](https://oscarliang.com/vifly-shortsaver/).
- Walksnail on 6S: red at 1 A, green at 2 A. "I have to put the threshold
  … up to 3A on some builds because it hits 1A doing the ESC startup tones."
  — [IntoFPV](https://intofpv.com/archive/index.php/thread-24508.html),
  [IntoFPV](https://intofpv.com/archive/index.php/thread-23383.html)
- 2025: 1500 µF cap + 2207 motors red at 1 A. "My smokestopper has just 2
  options: 1A and 2A … Should I consider a better smokestopper?" —
  [IntoFPV](https://intofpv.com/archive/index.php/thread-27994.html)
- Inference (no direct thread found): a DJI O4 Pro draws ~1.15 A at 9 V on
  its own ([Oscar Liang](https://oscarliang.com/how-to-setup-dji-o4-pro/)),
  so a 1 A limit on 2–3S cannot pass a healthy O4 build.

**The trap:** the only fix offered is a looser limit or a slower trip,
which lets more energy into a real fault.

### 2. False sense of security

- "Fried three engines, 4 In 1 esc and fc … The smokestopper had a green
  light" — [Oscar Liang comments](https://oscarliang.com/rdq-smoke-stopper-led-pptc/)
- Polyfuses take 100–200 ms to trip — [IntoFPV](https://intofpv.com/t-smoked-my-first-esc)
- A VTX wired to the wrong rail dies at low current: the stopper never sees
  it — [IntoFPV](https://intofpv.com/archive/index.php/thread-12883.html)
- Two 5 V regulators had half-failed (~20 Ω to ground), still booted on
  USB, and only showed up as a vague trip on battery —
  [IntoFPV](https://intofpv.com/archive/index.php/thread-22827.html).
  Users want the fault **diagnosed**, not just flagged.

### 3. Can't spin motors through it; the brownout looks like a fault

- A polyfuse dimmed, motors twitched; "spent a day debugging" —
  [IntoFPV](https://intofpv.com/t-weird-motor-behavior-on-new-build)
- "the motor does like 2 full spins before the smoke stopper trips" —
  [IntoFPV](https://intofpv.com/archive/index.php/thread-24051.html)
- "you cannot run your motors with this fitted" —
  [KiwiQuads, TBS](https://kiwiquads.co.nz/product/tbs-smoke-stopper-xt60-xt30/)

### 4. Limits too coarse to go from whoop to big quad

- 1 A / 2 A is the usual choice; V1 changed it with solder pads under heat
  shrink — [IntoFPV](https://intofpv.com/t-vifly-shortsaver-new-generation-smoke-stopper)
- 9-inch builds need more than 2 A at start-up —
  [IntoFPV](https://intofpv.com/t-first-build-and-plug-and-burn)

### 5. Cell-count gaps

- "disappointed that this doesn't work with 1s batteries" — RDQ review,
  ShortSaver 2.
- "I could find NO such thing for 1S" — [Fractal](https://store.fractalengineering.net/product/fractal-1s-sparkyguard/)

### 6. Confusing LEDs, no instructions — with real damage

- "Burnt out another new motor since someone found info saying the
  constant red light meant good to go." — RDQ review, JHEMCU.
- "No beeps, just lights and interpreting their colors." — RDQ review,
  ShortSaver.

### 7. Durability

- Dead on arrival (V2, and V1 before it); "don't last long"; bare boards
  short on conductive benches; leads rip off.

### 8. Connectors

- XT30/XT60 only. "wont fit into a [XT]60 that is embedded into the drone
  frame" — [Amazon, 2026](https://us.amazon.com/Smoke-Stopper-FPV-Drone-Short-Circuit/dp/B0CTH94Y21)

### What people like (keep it)

- **The power button.** Used as a bench switch for ELRS binding, VTX
  unlock and OSD setup: "No longer do I need three hands." (6+ RDQ reviews)

### How it is actually used

- Plug in, check for a trip, remove it, carry on. Nobody reports flying
  through one, and GetFPV and iFlight both say not to.

### Fires

- None found caused by a smoke stopper. Fire reports are builds without
  one.

---

## 3. Other facts used in the spec

- **ExpressLRS bind by power cycling:** power on, off within 2 s, three
  times, leave on after the third. Receivers with a binding phrase need
  3.4.0 or newer to enter bind this way —
  [expresslrs.org](https://expresslrs.org/quick-start/binding)
- **TI TPS4811-Q1** smart high-side driver: 3.5–80 V, back-to-back
  N-FETs, 12 V charge pump, current monitor out (IMON, ±2 % at 30 mV),
  two-level overcurrent with timer. The **TPS48111** variant adds a
  pre-charge gate driver and a 1.2 µs short-circuit response; output
  survives −30 V — [TI](https://www.ti.com/product/TPS4811-Q1). About
  $2 at 500 pcs (third-party distributor, unverified).
- **TI LMR36503** buck: 3.0–65 V in (70 V transients), 0.3 A, 2 × 2 mm —
  [TI](https://www.ti.com/product/LMR36503)
