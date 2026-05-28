# Lights Up Arcade Button Game

A two-player reaction game built with an Arduino and a Python/Pygame front-end. The screen lights up LEFT or RIGHT — first player to hit the correct button wins the round.

## How It Works
The Arduino reads two physical buttons and plays buzzer feedback. The Python script handles the game logic, countdown, scoring, and neon-style visuals. Both sides communicate over USB serial at 115200 baud.

## Hardware
| Component | Pin |
|-----------|-----|
| Left button | D7 (INPUT_PULLUP) |
| Right button | D8 (INPUT_PULLUP) |
| Passive buzzer | D4 |

## Setup

**Arduino:** Flash `arcade_reaction/arcade_reaction.ino` to your board.

**Python:**
```bash
pip install pygame pyserial
python game.py
# or specify port manually:
python game.py /dev/cu.usbmodem1101
```

The port is auto-detected on macOS. If no Arduino is found, the game runs in keyboard-only mode (A = Left, D = Right).

## Game Rules
- 10 rounds per game
- React before **700 ms** or it counts as a miss
- Press too early → FAIL
- Press wrong side → FAIL
- Final screen shows average, best, worst reaction time and a grade (S → D)
