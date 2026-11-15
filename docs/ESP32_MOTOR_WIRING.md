# Grassroot — confirmed XIAO ESP32-S3 motor pins

The team confirmed this pin assignment. Electrical inspection, motor rating, polarity and
motion calibration remain pending. The disabled default firmware does not energize outputs.
Use the [Mac hardware runbook](MAC_HARDWARE_SETUP.md) for calibration and upload profiles.

| Position | Driver/channel | IN1: XIAO / GPIO | IN2: XIAO / GPIO | Motor output pair |
| --- | --- | --- | --- | --- |
| Left front (LF) | 1 / A | D0 / GPIO1 | D1 / GPIO2 | AOUT1, AOUT2 |
| Left rear (LR) | 1 / B | D2 / GPIO3 | D3 / GPIO4 | BOUT1, BOUT2 |
| Right front (RF) | 2 / A | D4 / GPIO5 | D5 / GPIO6 | AOUT1, AOUT2 |
| Right rear (RR) | 2 / B | D6 / GPIO43 | D7 / GPIO44 | BOUT1, BOUT2 |

D6 and D7 refer to GPIO43 and GPIO44, not GPIO6 and GPIO7.
The existing sketch orders motors **LF, RF, LR, RR**, unlike the table's **LF, LR, RF, RR**.
The calibration and measured-run profiles use IN1 `{1, 5, 3, 43}` and IN2 `{2, 6, 4, 44}`
in sketch order LF, RF, LR, RR. Both driver SLP pins are tied to 3V3.

The motor supply is 6 V; the motor's voltage/current specification is still unverified.
Use a common ground and separate controller power; never feed motor current through GPIO.
The joystick is a second XIAO ESP32-S3: 3V3, GND, X GPIO1, Y GPIO2, button GPIO3.
The cell width is 22 cm. No wheel polarity or motion timing is supplied as a measured value.
