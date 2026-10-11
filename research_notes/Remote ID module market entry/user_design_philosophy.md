# How Shreyash designs products: notes from the SmokeBreak session

**Source:** the Claude Code Remote session "Universal drone battery board design"
(session_01SBnFJLvm1wBa1jZy4RXnma), 10 Oct 2026 19:53 UTC to 11 Oct 2026 about 07:02 UTC.
I read every page of user and assistant messages, from the first message to the newest
event at the time of reading. The session was still running then: the PCB build had
just started. I also skimmed branch `claude/firebreak-spec` of `offgridevices/offgrid-hardware`:
`README.md`, `smokebreak/SPEC.md`, `smokebreak/concepts/README.md`,
`smokebreak/concepts/10-armed-toggle/concept.md` and `smokebreak/v1/ARCHITECTURE.md`.
Quotes are copied exactly, typos included.

The session has only about 15 real messages from Shreyash. Most of the transcript is
Claude working on its own, with subagent reports and render jobs in between. His
messages are short and dense, so each one counts a lot.

---

## 1. The product and its goals

**SmokeBreak** (working names were Firebreak and then "smoke something") is a smart
**smoke stopper** for FPV drones that also checks LiPo batteries. It sits on the bench
between the LiPo and the drone. Before any battery voltage reaches the drone it tests the
drone at 3 V, which catches shorts, half-shorts and reversed leads. It then charges the
drone's capacitors slowly, so plugging in causes no false trips, and powers the drone
behind a two-tier electronic fuse. It remembers each drone and warns when one draws more
current than last time. The final board adds per-cell battery checking over the balance
lead and survives every wrong connection. One unit covers **1S whoops to 14S heavy-lift**
("all sizes of drones and batteries"). Shreyash chose the **"Arm"** design: an
aircraft-style guarded toggle. You lift the guard to arm, flick the switch to power, and
closing the guard always cuts power in hardware. A 1.9" colour screen plays a dramatic
arming sequence, and a status ring lights around the switch. The product brief was to fix
what people complain about in current smoke stoppers and to "do something unique", sold as
an OffGrid enclosed product. The price went from "same price as current smoke stoppers" to
"Ignore price" and then settled at **$30 retail with a $20–22 landed cost**. The case is
3D-printed and he assembles it himself. The board has to be upload-ready for PCBWay
assembly.

---

## 2. Design principles (as rules, with evidence)

1. **One product for every size.** Cover the whole range instead of making separate
   models.
   - *"Help me get this board built that can be used for all sizes of drones and
     batteries for them."*
   - He chose **14S** over 12S. He asked how to *"reduce the cost but still be able to
     have 14S batteries no problem."* Lowering the top voltage to save money was never an
     option for him.

2. **Start from real user pain, found by research, then fix it.**
   - *"Research what a smoke stopper is missing from internet threads and see whats the
     latest issue people wre facing and I wanna fix that."*
   - He accepted the spec's complaint list as the basis: false trips, "green light, still
     smoked", confusing LEDs, and no 1S or above-6S support.

3. **It must be different. A copy is not a product.**
   - *"it needs to do something unique. Help me figute that out too."*
   - *"Something unique and different."*
   - The features he kept are ones no competitor has: checking before powering, no
     inrush, and remembering each drone.

4. **Noob-proof.** Someone who has never seen it should use it correctly the first time,
   from the face alone and without a manual.
   - He sent the single message *"Noob proof"*, which became a spec rule.
   - "Noob-proof" was one of the five scores used to rate all 20 concepts.
   - The Arm concept scored Noob-proof 5.

5. **Premium experience, never a "cheap looking board with buttons".**
   - *"I want a UX of the product that solves problems for people. A premium experience
     and not a cheap looking board with buttons."*
   - Concepts were scored on Premium and Build quality. Cost was dropped as a score.

6. **Quality over cost, but within real numbers.** He first said *"Ignore price. We will
   do the best smoke stopper on the market."* Later he set *"$30. And our landed cost
   should be around 20-22$. Not more."* He accepts cost-downs that give up nothing
   visible. He rejects ones that hurt the experience. Paying for feel is fine:
   - *"that arm switch needs to be the best one out there. A satisdying click sound is
     worth money!!!"*

7. **Physical, tactile, slightly theatrical interaction.**
   - He chose the guarded arm switch (*"Hahaha the arm is so good and we make it dramatic
     on the screen haha. Lets do it"*), not Claude's top picks (Flip, Crown, Ignition,
     Puck).
   - He likes hazard stripes, beeps and a green "LIVE" flash. Powering on should feel
     like an event.

8. **Safety by physical design, independent of firmware.**
   - He accepted, and kept, the rule that closing the guard always cuts power through a
     hall sensor in hardware, "even if the software has crashed".
   - He accepted the protections stacked from fastest to smartest.
   - He asked for *"all simulations and tests to verify it works and will work in all
     edge cases of a bad battery beinf connected to it... Wrong connector sides or
     whatever."*

9. **Survive every misuse and explain it in words.** Every wrong connection must be
   survivable and shown on screen: battery on the drone side, batteries on both sides,
   reversed leads, a shifted balance plug, a balance lead from another pack. He asked for
   this; the table in ARCHITECTURE.md §4 is how it was carried out.

10. **Show rich information, beautifully.**
    - *"If we can show information about the battery and each cell and all other
      beautifully on the screen then even better."*
    - His idea of "better" includes more insight per glance: per-cell bars, delta,
      internal resistance.

11. **Engineering beauty inside too.** The PCB should be:
    - *"really stable and high quality parts fit beautifully. Not sperarically but
      beautifully. Like a well planned city kinda pcb."*
    - The board itself is part of the brand. In the early spec the PCB was the front
      panel.

12. **Brand is sacred, and Apple is the bar.**
    - *"Never get the dimensions of the logo wrong. Keep it exactly how its supposed to
      be in all animatiosn too."*
    - *"Look at rules about logo placwment for logos from Apple and i wanna do that. Logo
      placement gotta be premium and keep brand top notch."*
    - The rules that came out of this: one mark per product, no logo on the working face,
      the mark is never a light or button, it is never animated, and clear space is at
      least ¼ of the mark's width.

13. **Apple-style simplicity in labelling.**
    - *"I like arrows on boards. Simple apple product like arrows. Simple and stuff that
      explains it all."*
    - One arrow style everywhere, sentence case, few words, and a printed numbered flow:
      "1 Battery in → 2 Drone in → 3 Press Power".

14. **Manufacturable by a small team.**
    - *"Pcb should be so good that I can upload the final one on pcb way and it woll
      automarically detect all parts."*
    - BOM with exact part numbers. SMD parts on one side; through-hole parts he solders
      himself; a 3D-printed case he assembles himself.

15. **Open hardware, reproducible** (repo README). The licence is CERN-OHL-S v2. The board
    is generated by a script with verification gates that fail the build. A stranger can
    order a board from the committed Gerbers and BOM.

---

## 3. UX preferences

- **Setup:** zero configuration. Plug the battery in, plug the drone in, then one
  deliberate action. Drones are recognised automatically (no pairing or naming). The
  limit defaults to Auto.
- **Controls:** few, physical, each doing one thing, with the function printed beside it.
  - He liked the original buttons being *"in a better spot to push"* with *"clear
    silkscreen instructions"*.
  - Anything dangerous takes a second confirmation: the 25 A motor test asks "Props
    off?".
- **Indicators:**
  - A colour screen that says in words what happened and what to do. He accepted that
    confusing LEDs ("red meant good to go") are a known way people burn parts.
  - A status ring as the light at a glance.
  - Distinct beeps for each state.
- **Connectors:**
  - He asked *"What would be the best connectors to add? All female or somemale some
    female?"* and accepted the reasoning: male on the battery side, female on the drone
    side, matching FPV convention, with the live side recessed.
  - XT60 and XT30 are built in, so most users need no adapter.
  - Wrong-side plugging is handled and explained, not just blocked.
- **USB-C:** yes (*"Usb c would be good"*), for firmware updates and exporting data. A
  phone app was left out of v1.
- **Foolproofing:**
  - Arrows show direction and flow.
  - Closing the guard is a physical reset that also clears faults.
  - "Black wire here" is marked on the balance header.
  - The product should explain itself, with no manual needed.
- **Feedback loop with him:** he wants to *see* things before deciding.
  - *"make sure I can see what these designs look like visually. A video would be
    ideal... Use blender... put numbers on it so I can tell you feedback thats more
    accurate."*
  - Numbered concepts, spin videos and storyboards, with feedback given by number.

---

## 4. Explicitly rejected or corrected

| What Claude did or proposed | His correction | Why |
|---|---|---|
| Names Firebreak, Tripwire, Checkpoint | *"Can we use smoke something name instead?"* → chose **SmokeBreak** | Wants a name that says the category and is memorable |
| Cost-down parts and a $22.99–24.99 price target | *"Ignore price. We will do the best smoke stopper on the market."* Claude restored the better parts. Later he set $30 retail / $20–22 landed | Quality and experience come first, then a firm but realistic budget |
| Flat PCB-as-faceplate box with three buttons | *"not a cheap looking board with buttons"* → 20 industrial-design concepts | Premium product experience over a bare board |
| Claude's top picks (11 Flip, 09 Crown, 18 Ignition, 02 Puck) | He picked **10 Arm** | Drama and tactile ritual, plus a physically obvious safe state |
| Hand-drawn logo ring with slightly wrong stroke and node | *"Never get the dimensions of the logo wrong"* | Brand accuracy is not negotiable, including in animations |
| Switch placed inside the logo ring; logo used as a status light and animated | *"The switch shouldnt be inside the logo... rules about logo placwment... from Apple"* | The logo is never a part. Premium brand discipline. Concept 04 Halo was retired because its body was the logo shape |
| Text-only progress | Asked for visuals: video, Blender, numbered | He decides visually and wants precise, numbered feedback targets |
| Rendering on the CPU | *"Are you using all the cores to render it?"* | Impatient with waste. Expects the machine to be pushed |

He did **not** push back on: 14S, USB-C, adding the BT2.0 adapter, the guard hardware
cut-off, the drone-memory feature, or splitting heavy-lift adapters into a separate
accessory.

---

## 5. How he works with Claude

- **Short, fast, typo-heavy messages, often several in a row.** For example, "Noob proof"
  sent seven seconds after the arrows message. Read for intent, not literal wording.
  Typos are normal, so never ask about them.
- **Delegates big chunks and expects autonomy.**
  - *"Go ahead and build it all. I will open this chat to see the progress but otherwise
    I will wanna see the final thing."*
  - *"Make like 20 different deaigns with subagents."*
  - He likes parallel subagents and long background jobs.
- **Spec first, then build.** *"Lets design the specs fully first and then we will
  build."* He answers decision lists, numbered 1–4, in the same numbering.
- **Likes tables.** *"Give me a table with the breakdown."* Cost tables with "what we
  give up" columns worked well.
- **Decides with visuals.** Renders, turntable videos, storyboards and contact sheets,
  all numbered.
- **Enthusiastic when something lands** ("Hahaha the arm is so good"). Blunt when it
  doesn't ("The switch shouldnt be inside the logo").
- **Expects a recommendation with every choice.** Claude's "my pick" column was useful
  even though he overrode it.
- **Expects everything committed and pushed.** A stop hook enforces this.
- **Things that annoy him:**
  - brand errors;
  - cheap-looking results;
  - generic me-too features;
  - anything slow that could be faster;
  - having to imagine a design from text.
- **Lasting rules get saved.** Rules he states ("never get the logo wrong") were written
  into the spec and his Notion memory as permanent rules. Treat his "never" statements
  as permanent.

---

## 6. What this means for a broadcast Remote ID module (vs Ruko R111S: 13.5 g, GPS, buzzer, ~3 h battery)

What he would most likely want, ranked by how strongly the evidence supports it:

1. **Universal fit.**
   - It should work on any drone: whoop to heavy-lift, any frame, any power source.
   - Wide-input power from 1S to 6S, or higher if it can be done cheaply. Also run on its
     own internal battery.
   - Several mounting options.
   - Same thinking as "1S to 14S in one unit".
2. **A unique angle, not an R111S clone.** Find what R111S and Holybro/Dronetag users
   complain about in forums first, as he did for smoke stoppers. Then pick 2–3 things no
   competitor does. Candidates to research:
   - honest broadcast status (is it *really* broadcasting, with a GPS fix?);
   - a pre-flight self-check that tells you, like the 3 V probe did;
   - no-app setup;
   - auto-wake on drone power;
   - a flight log export.
3. **Noob-proof compliance.**
   - The pilot should know at a glance, with no app, whether the module is legal to fly
     with right now: GPS fix, broadcasting, battery level.
   - States in plain words or unambiguous light and sound patterns. Never an LED code
     that can be misread (his "red meant good to go" lesson).
   - A printed arrow for the antenna or "this side up" orientation.
   - One-button or zero-button operation.
   - Defaults that just work: auto-on, auto-broadcast, nothing to configure in the field.
4. **Failure modes handled in hardware and explained.**
   - What happens with no GPS fix, a low battery, a dead battery mid-flight, or external
     power lost?
   - He will want every edge case listed, simulated and tested, like the SmokeBreak
     wrong-connection table.
   - The buzzer should mean something specific: lost fix, low battery, not broadcasting.
5. **Premium, tactile and branded, even at 13.5 g.**
   - It must not look like a bare board in shrink wrap. It needs a designed enclosure.
   - The OffGrid mark appears exactly once, never as the LED ring and never animated.
   - Apple-style arrows and few words on the case.
   - Expect him to ask for 10–20 numbered form-factor concepts with renders and spin
     videos before choosing.
6. **Weight, size and battery life are where it wins or loses on spec.** Match or beat
   13.5 g and 3 h (the R111S baseline).
   - He accepts paying more for parts that improve what the user experiences.
   - He rejects savings that cost something the user would notice.
   - Expect a firm landed-cost target once the price is set. A useful frame: retail
     about 1.4–1.5× landed cost, as with SmokeBreak's $30 / $20–22.
7. **USB-C for charging and firmware.** He liked USB-C for updates and data export.
   - Likely wants: ID/serial setup over USB or a simple web page instead of a heavy app;
     firmware updatable for rule changes (FAA/EASA).
8. **Small-team manufacturing.**
   - PCBWay-ready: BOM with manufacturer part numbers, pick-and-place file, Gerbers.
   - SMD on one side; through-hole parts he hand-solders.
   - 3D-printed enclosure for the first batch.
   - Generated by script with verification gates, open hardware (CERN-OHL-S), repo
     conventions followed.
9. **How to present the work to him:**
   - Spec first, with a "decisions needed" table, each row with a recommendation.
   - Cost-breakdown table with a "what we give up" column.
   - Numbered visuals.
   - Then build without supervision, and show the finished result.
