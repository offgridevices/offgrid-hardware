# Print Hub v1: port events (ngspice)

Computed by `sim/port_events.py`; the model and its pessimistic choices are in its docstring.

| | value |
|---|---|
| rail before any port | 5.16 V |
| rail, lowest, while every port switches on together | 5.13 V |
| port voltages with fan, light, two filters and a 1 A phone | 5.09 / 5.07 / 5.05 / 5.05 / 5.03 V |
| rail, lowest, when port 5 is shorted | 4.76 V |
| ports 1-4, lowest, during the short's first microseconds | 4.77 V |
| ports 1-4, from 1 ms after the short on | 5.05 V |

The firmware then switches port 5 off on the switch's FAULT line (8 ms deglitch); the model leaves it on, current-limited, to show the steady case.

## Checks

- PASS all five ports on together: the rail dips to 5.13 V (logic needs > 3.6 V)
- PASS port 5 shorted: the other ports dip to 4.77 V for the 2 us before the limiter acts
- PASS port 5 shorted, after 1 ms: the other ports hold 5.05 V
