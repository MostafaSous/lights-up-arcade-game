"""
Arcade Reaction Game — Python side
Connect Arduino via USB, then run: python game.py
If auto-detect fails: python game.py /dev/cu.usbmodem1101

Requirements: pip install pygame pyserial
"""

import sys
import time
import random
import math
import serial
import serial.tools.list_ports
import pygame

# Config
SCREEN_W, SCREEN_H = 900, 600
FPS = 60
SERIAL_BAUD = 115200
ROUNDS_TOTAL = 10
TIME_LIMIT_MS = 700  # max reaction time before FAIL

# Colors
BG_DARK      = (10, 10, 18)
BG_PANEL     = (18, 18, 30)
NEON_CYAN    = (0, 255, 240)
NEON_PINK    = (255, 40, 150)
NEON_YELLOW  = (255, 230, 50)
NEON_GREEN   = (50, 255, 120)
NEON_RED     = (255, 50, 70)
WHITE        = (255, 255, 255)
GRAY         = (100, 100, 120)
DIM_GRAY     = (40, 40, 55)


def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "usbmodem" in p.device or "usbserial" in p.device or "wchusbserial" in p.device:
            return p.device
    if ports:
        return ports[0].device
    return None


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 8)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(0.015, 0.04)
        self.color = color
        self.size = random.uniform(2, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1  # gravity
        self.life -= self.decay

    def draw(self, surf):
        if self.life <= 0:
            return
        r = max(1, int(self.size * self.life))
        c = lerp_color(self.color, BG_DARK, 1 - self.life)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), r)


class Shockwave:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.radius = 0
        self.max_radius = 180
        self.color = color
        self.life = 1.0

    def update(self):
        self.radius += 6
        self.life = max(0, 1 - self.radius / self.max_radius)

    def draw(self, surf):
        if self.life <= 0:
            return
        width = max(1, int(4 * self.life))
        c = lerp_color(self.color, BG_DARK, 1 - self.life)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), int(self.radius), width)


class FloatingText:
    def __init__(self, text, x, y, color, font):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.font = font
        self.life = 1.0
        self.decay = 0.02

    def update(self):
        self.y -= 1.2
        self.life -= self.decay

    def draw(self, surf):
        if self.life <= 0:
            return
        c = lerp_color(self.color, BG_DARK, 1 - self.life)
        txt = self.font.render(self.text, True, c)
        rect = txt.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(txt, rect)


class ArcadeReactionGame:
    def __init__(self, serial_port):
        global SCREEN_W, SCREEN_H
        pygame.init()
        pygame.display.set_caption("ARCADE REACTION")
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        SCREEN_W, SCREEN_H = self.screen.get_size()
        self.clock = pygame.time.Clock()

        self.font_huge  = pygame.font.SysFont("Menlo", 72, bold=True)
        self.font_big   = pygame.font.SysFont("Menlo", 42, bold=True)
        self.font_med   = pygame.font.SysFont("Menlo", 28)
        self.font_small = pygame.font.SysFont("Menlo", 20)
        self.font_tiny  = pygame.font.SysFont("Menlo", 16)

        self.ser = None
        try:
            self.ser = serial.Serial(serial_port, SERIAL_BAUD, timeout=0)
            time.sleep(2)  # wait for Arduino reset
        except Exception as e:
            print(f"Serial error: {e}")
            print("Running in keyboard-only mode (A = Left, D = Right)")

        self.state = "MENU"
        self.round_num = 0
        self.score = 0
        self.reaction_times = []
        self.prompt_side = None
        self.prompt_time = 0
        self.wait_until = 0
        self.countdown_val = 3
        self.countdown_time = 0
        self.result_text = ""
        self.result_color = WHITE
        self.result_time = 0
        self.flash_alpha = 0
        self.flash_color = WHITE
        self.bg_pulse = 0

        self.particles = []
        self.shockwaves = []
        self.floating_texts = []

        # CRT scanline overlay
        self.scanline_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for y in range(0, SCREEN_H, 3):
            pygame.draw.line(self.scanline_surf, (0, 0, 0, 25), (0, y), (SCREEN_W, y))

    def send_cmd(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd + "\n").encode())
            except:
                pass

    def read_serial(self):
        if not self.ser or not self.ser.is_open:
            return None
        try:
            if self.ser.in_waiting:
                line = self.ser.readline().decode().strip()
                if line in ("L", "R"):
                    return line
        except:
            pass
        return None

    def spawn_particles(self, x, y, color, count=30):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def spawn_shockwave(self, x, y, color):
        self.shockwaves.append(Shockwave(x, y, color))

    def spawn_floating_text(self, text, x, y, color):
        self.floating_texts.append(FloatingText(text, x, y, color, self.font_big))

    def flash(self, color):
        self.flash_alpha = 200
        self.flash_color = color

    def start_game(self):
        self.state = "COUNTDOWN"
        self.round_num = 0
        self.score = 0
        self.reaction_times = []
        self.countdown_val = 3
        self.countdown_time = time.time()

    def start_round(self):
        self.round_num += 1
        self.state = "WAIT"
        self.wait_until = time.time() + random.uniform(0.4, 1.8)
        self.send_cmd("START")

    def show_prompt(self):
        self.state = "PROMPT"
        self.prompt_side = random.choice(["L", "R"])
        self.prompt_time = time.time()
        self.bg_pulse = 1.0

    def handle_input(self, button):
        if self.state == "MENU":
            self.start_game()
            return

        if self.state == "SCOREBOARD":
            self.state = "MENU"
            return

        if self.state == "WAIT":
            self.result_text = "TOO EARLY!"
            self.result_color = NEON_RED
            self.result_time = time.time()
            self.state = "RESULT"
            self.send_cmd("FAIL")
            self.flash(NEON_RED)
            self.spawn_particles(SCREEN_W // 2, SCREEN_H // 2, NEON_RED, 20)
            return

        if self.state == "PROMPT":
            elapsed_ms = (time.time() - self.prompt_time) * 1000
            if elapsed_ms > TIME_LIMIT_MS:
                return

            if button == self.prompt_side:
                self.score += 1
                self.reaction_times.append(elapsed_ms)
                self.result_text = f"{elapsed_ms:.0f} ms"
                self.send_cmd("WIN")

                if elapsed_ms < 200:
                    self.result_color = NEON_CYAN
                    label = "INSANE!"
                elif elapsed_ms < 350:
                    self.result_color = NEON_GREEN
                    label = "GREAT!"
                elif elapsed_ms < 500:
                    self.result_color = NEON_YELLOW
                    label = "OK!"
                else:
                    self.result_color = NEON_PINK
                    label = "SLOW..."

                cx = SCREEN_W // 4 if self.prompt_side == "L" else 3 * SCREEN_W // 4
                cy = SCREEN_H // 2
                self.spawn_particles(cx, cy, self.result_color, 40)
                self.spawn_shockwave(cx, cy, self.result_color)
                self.spawn_floating_text(label, cx, cy - 60, self.result_color)
                self.flash(self.result_color)
            else:
                self.result_text = "WRONG SIDE!"
                self.result_color = NEON_RED
                self.send_cmd("FAIL")
                self.flash(NEON_RED)
                self.spawn_particles(SCREEN_W // 2, SCREEN_H // 2, NEON_RED, 25)

            self.result_time = time.time()
            self.state = "RESULT"

    def update(self):
        now = time.time()

        if self.state == "COUNTDOWN":
            elapsed = now - self.countdown_time
            if elapsed >= 1.0:
                self.countdown_val -= 1
                self.countdown_time = now
                if self.countdown_val <= 0:
                    self.start_round()

        if self.state == "WAIT" and now >= self.wait_until:
            self.show_prompt()

        if self.state == "PROMPT":
            elapsed_ms = (now - self.prompt_time) * 1000
            if elapsed_ms > TIME_LIMIT_MS:
                self.result_text = "TOO SLOW!"
                self.result_color = NEON_RED
                self.result_time = now
                self.state = "RESULT"
                self.send_cmd("FAIL")
                self.flash(NEON_RED)

        if self.state == "RESULT" and (now - self.result_time) > 1.8:
            if self.round_num >= ROUNDS_TOTAL:
                self.state = "SCOREBOARD"
                self.send_cmd("GAMEOVER")
            else:
                self.start_round()

        if self.flash_alpha > 0:
            self.flash_alpha = max(0, self.flash_alpha - 8)

        if self.bg_pulse > 0:
            self.bg_pulse = max(0, self.bg_pulse - 0.03)

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        for s in self.shockwaves:
            s.update()
        self.shockwaves = [s for s in self.shockwaves if s.life > 0]

        for ft in self.floating_texts:
            ft.update()
        self.floating_texts = [ft for ft in self.floating_texts if ft.life > 0]

    def draw(self):
        bg = lerp_color(BG_DARK, (30, 20, 50), self.bg_pulse * 0.5)
        self.screen.fill(bg)

        t = time.time()
        for x in range(0, SCREEN_W, 60):
            alpha = int(15 + 10 * math.sin(t * 2 + x * 0.05))
            c = (alpha, alpha, alpha + 10)
            pygame.draw.line(self.screen, c, (x, 0), (x, SCREEN_H))
        for y in range(0, SCREEN_H, 60):
            alpha = int(15 + 10 * math.sin(t * 2 + y * 0.05))
            c = (alpha, alpha, alpha + 10)
            pygame.draw.line(self.screen, c, (0, y), (SCREEN_W, y))

        if self.state == "MENU":
            self._draw_menu()
        elif self.state == "COUNTDOWN":
            self._draw_countdown()
        elif self.state == "WAIT":
            self._draw_wait()
        elif self.state == "PROMPT":
            self._draw_prompt()
        elif self.state == "RESULT":
            self._draw_result()
        elif self.state == "SCOREBOARD":
            self._draw_scoreboard()

        if self.state in ("WAIT", "PROMPT", "RESULT"):
            self._draw_hud()

        for s in self.shockwaves:
            s.draw(self.screen)
        for p in self.particles:
            p.draw(self.screen)
        for ft in self.floating_texts:
            ft.draw(self.screen)

        if self.flash_alpha > 0:
            flash_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash_surf.fill((*self.flash_color, int(self.flash_alpha * 0.4)))
            self.screen.blit(flash_surf, (0, 0))

        self.screen.blit(self.scanline_surf, (0, 0))
        pygame.display.flip()

    def _draw_menu(self):
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        title = "ARCADE REACTION"
        t = time.time()
        glow_c = lerp_color(NEON_CYAN, NEON_PINK, (math.sin(t * 2) + 1) / 2)

        glow_surf = self.font_huge.render(title, True, glow_c)
        glow_rect = glow_surf.get_rect(center=(cx, cy - 80))
        glow_alpha_surf = pygame.Surface(glow_surf.get_size(), pygame.SRCALPHA)
        glow_alpha_surf.blit(glow_surf, (0, 0))
        glow_alpha_surf.set_alpha(60)
        self.screen.blit(glow_alpha_surf, (glow_rect.x - 3, glow_rect.y + 3))

        txt = self.font_huge.render(title, True, WHITE)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy - 80)))

        sub = self.font_med.render("Press any button to start", True, GRAY)
        alpha = int(128 + 127 * math.sin(t * 3))
        sub.set_alpha(alpha)
        self.screen.blit(sub, sub.get_rect(center=(cx, cy + 10)))

        inst_lines = [
            "LEFT button when LEFT lights up",
            "RIGHT button when RIGHT lights up",
            f"{ROUNDS_TOTAL} rounds  —  react before {TIME_LIMIT_MS}ms",
        ]
        for i, line in enumerate(inst_lines):
            txt = self.font_small.render(line, True, DIM_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(cx, cy + 70 + i * 28)))

        kb = self.font_tiny.render("Keyboard: A = Left, D = Right", True, DIM_GRAY)
        self.screen.blit(kb, kb.get_rect(center=(cx, SCREEN_H - 30)))

    def _draw_countdown(self):
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        txt = self.font_huge.render(str(self.countdown_val), True, NEON_YELLOW)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))
        sub = self.font_med.render("GET READY", True, GRAY)
        self.screen.blit(sub, sub.get_rect(center=(cx, cy + 70)))

    def _draw_wait(self):
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        t = time.time()
        dots = "." * (int(t * 3) % 4)
        txt = self.font_big.render(f"WAIT{dots}", True, DIM_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))

    def _draw_prompt(self):
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        elapsed_ms = (time.time() - self.prompt_time) * 1000
        urgency = min(1.0, elapsed_ms / TIME_LIMIT_MS)

        if self.prompt_side == "L":
            color = lerp_color(NEON_CYAN, NEON_RED, urgency)
            arrow_x = SCREEN_W // 4
            glow_surf = pygame.Surface((SCREEN_W // 2, SCREEN_H), pygame.SRCALPHA)
            glow_surf.fill((*color, int(40 + 30 * urgency)))
            self.screen.blit(glow_surf, (0, 0))
            txt = self.font_huge.render("LEFT", True, color)
            self.screen.blit(txt, txt.get_rect(center=(arrow_x, cy)))
        else:
            color = lerp_color(NEON_PINK, NEON_RED, urgency)
            arrow_x = 3 * SCREEN_W // 4
            glow_surf = pygame.Surface((SCREEN_W // 2, SCREEN_H), pygame.SRCALPHA)
            glow_surf.fill((*color, int(40 + 30 * urgency)))
            self.screen.blit(glow_surf, (SCREEN_W // 2, 0))
            txt = self.font_huge.render("RIGHT", True, color)
            self.screen.blit(txt, txt.get_rect(center=(arrow_x, cy)))

        # Timer bar
        bar_w = int(SCREEN_W * (1 - urgency))
        bar_color = lerp_color(NEON_GREEN, NEON_RED, urgency)
        pygame.draw.rect(self.screen, bar_color, (0, SCREEN_H - 8, bar_w, 8))

    def _draw_result(self):
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        txt = self.font_big.render(self.result_text, True, self.result_color)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))

    def _draw_scoreboard(self):
        cx, cy = SCREEN_W // 2, 80
        title = self.font_big.render("GAME OVER", True, NEON_PINK)
        self.screen.blit(title, title.get_rect(center=(cx, cy)))

        score_txt = self.font_big.render(f"{self.score} / {ROUNDS_TOTAL}", True, NEON_CYAN)
        self.screen.blit(score_txt, score_txt.get_rect(center=(cx, cy + 70)))

        if self.reaction_times:
            avg = sum(self.reaction_times) / len(self.reaction_times)
            best = min(self.reaction_times)
            worst = max(self.reaction_times)

            stats = [
                f"Average:  {avg:.0f} ms",
                f"Best:     {best:.0f} ms",
                f"Worst:    {worst:.0f} ms",
            ]
            for i, line in enumerate(stats):
                txt = self.font_med.render(line, True, WHITE)
                self.screen.blit(txt, txt.get_rect(center=(cx, cy + 140 + i * 36)))

            if avg < 250:
                grade, gc = "S — LEGENDARY", NEON_CYAN
            elif avg < 350:
                grade, gc = "A — AMAZING", NEON_GREEN
            elif avg < 450:
                grade, gc = "B — GREAT", NEON_YELLOW
            elif avg < 600:
                grade, gc = "C — DECENT", NEON_PINK
            else:
                grade, gc = "D — KEEP TRYING", NEON_RED

            g_txt = self.font_big.render(grade, True, gc)
            self.screen.blit(g_txt, g_txt.get_rect(center=(cx, cy + 270)))
        else:
            no = self.font_med.render("No successful reactions!", True, NEON_RED)
            self.screen.blit(no, no.get_rect(center=(cx, cy + 140)))

        t = time.time()
        alpha = int(128 + 127 * math.sin(t * 3))
        restart = self.font_small.render("Press any button to return to menu", True, GRAY)
        restart.set_alpha(alpha)
        self.screen.blit(restart, restart.get_rect(center=(cx, SCREEN_H - 40)))

    def _draw_hud(self):
        r_txt = self.font_small.render(f"Round {self.round_num}/{ROUNDS_TOTAL}", True, GRAY)
        self.screen.blit(r_txt, (20, 15))
        s_txt = self.font_small.render(f"Score: {self.score}", True, NEON_GREEN)
        self.screen.blit(s_txt, (SCREEN_W - s_txt.get_width() - 20, 15))

    def _toggle_fullscreen(self):
        global SCREEN_W, SCREEN_H
        is_fullscreen = bool(self.screen.get_flags() & pygame.FULLSCREEN)
        if is_fullscreen:
            self.screen = pygame.display.set_mode((900, 600))
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        SCREEN_W, SCREEN_H = self.screen.get_size()
        self.scanline_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for y in range(0, SCREEN_H, 3):
            pygame.draw.line(self.scanline_surf, (0, 0, 0, 25), (0, y), (SCREEN_W, y))

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                    if event.key == pygame.K_a:
                        self.handle_input("L")
                    if event.key == pygame.K_d:
                        self.handle_input("R")

            btn = self.read_serial()
            if btn:
                self.handle_input(btn)

            self.update()
            self.draw()
            self.clock.tick(FPS)

        if self.ser and self.ser.is_open:
            self.ser.close()
        pygame.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_arduino_port()
        if port:
            print(f"Found Arduino on {port}")
        else:
            print("No Arduino detected — running in keyboard-only mode")
            port = None

    game = ArcadeReactionGame(port)
    game.run()
