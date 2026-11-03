"""
main.py -- Smart Delivery Robot (Pygame)

Run:  python main.py        (needs:  pip install pygame)

How it works:
  1. Pick an algorithm, press "Start Simulation".
  2. The search is animated cell by cell (light blue = visited).
  3. The final path turns yellow, then the robot drives along it.
     The robot slows down on expensive terrain (mud / water).
Mouse: left-click/drag = paint the selected brush, right-click/drag = erase.
"""
import sys
import pygame

from core.grid_model import Grid, ROAD, WALL, GRASS, MUD, WATER, TERRAIN_COST
from algorithms import ALGORITHMS
from utils.metrics import run_algorithm
from gui.buttons import Button

# ---------------- layout ----------------
ROWS, COLS, CELL = 20, 30, 28
GRID_X, GRID_Y = 20, 20
PANEL_X = GRID_X + COLS * CELL + 20          # right-hand control panel
WIN_W, WIN_H = PANEL_X + 290, ROWS * CELL + 100

# ---------------- colors (dark theme) ----------------
BG = (20, 22, 28)
PANEL_BG = (30, 33, 42)
TEXT = (235, 238, 245)
MUTED = (140, 148, 165)
TERRAIN_COLOR = {ROAD: (52, 58, 72), WALL: (8, 8, 10), GRASS: (58, 105, 70),
                 MUD: (122, 84, 52), WATER: (44, 100, 170)}
VISITED_COLOR = (125, 195, 245)
PATH_COLOR = (250, 215, 60)
START_COLOR = (50, 200, 90)
GOAL_COLOR = (230, 60, 60)
ROBOT_COLOR = (30, 60, 210)


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Smart Delivery Robot - AI Pathfinding")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font = self._font(16)
        self.small = self._font(13)
        self.big = self._font(22, bold=True)

        self.grid = Grid(ROWS, COLS)
        self.algorithm = "A*"
        self.brush = WALL            # WALL / ROAD / GRASS / MUD / WATER / "start" / "goal"
        self.history = {}            # algorithm -> metrics (for comparison on the same map)
        self.message = "Choose an algorithm and press Start."
        self._build_buttons()
        self.reset_simulation()

    @staticmethod
    def _font(size, bold=False):
        return pygame.font.SysFont("segoeui,arial,helvetica", size, bold=bold)

    # ---------------- buttons ----------------
    def _build_buttons(self):
        x, w, h, gap = PANEL_X, 130, 26, 6
        self.algo_buttons, self.brush_buttons, self.action_buttons = {}, {}, {}

        y = 62
        for i, name in enumerate(ALGORITHMS):
            r = (x + (i % 2) * (w + gap), y + (i // 2) * (h + gap), w, h)
            self.algo_buttons[name] = Button(r, name)
        y += 3 * (h + gap) + 20

        brushes = [("Wall", WALL), ("Road (1)", ROAD), ("Grass (2)", GRASS),
                   ("Mud (5)", MUD), ("Water (8)", WATER), ("Set Start", "start"), ("Set Goal", "goal")]
        for i, (label, key) in enumerate(brushes):
            r = (x + (i % 2) * (w + gap), y + (i // 2) * (h + gap), w, h)
            self.brush_buttons[key] = Button(r, label)
        y += 4 * (h + gap) + 20

        actions = ["Start Simulation", "Reset", "Clear Map", "Random Map"]
        for i, label in enumerate(actions):
            r = (x + (i % 2) * (w + gap), y + (i // 2) * (h + gap), w, h)
            color = (40, 150, 85) if label == "Start Simulation" else (58, 64, 82)
            self.action_buttons[label] = Button(r, label, color=color)
        self.metrics_y = y + 2 * (h + gap) + 12

    # ---------------- simulation state ----------------
    def reset_simulation(self):
        """Clear search overlay, put the robot back at the start."""
        self.state = "idle"          # idle -> search -> move -> done
        self.result = None
        self.visited_shown = set()
        self.shown_count = 0
        self.path_visible = False
        self.robot_pos = self.grid.start       # (row, col) as floats while moving
        self.path_index = 0
        self.step_t = 0.0
        self.current_metrics = None

    def map_changed(self):
        self.history.clear()
        self.reset_simulation()

    def start_simulation(self):
        if self.state in ("search", "move"):
            return
        self.reset_simulation()
        self.result = run_algorithm(self.algorithm, self.grid)   # search itself is instant,
        self.state = "search"                                    # we only ANIMATE it
        self.message = f"Running {self.algorithm}..."

    # ---------------- update ----------------
    def update(self, dt):
        if self.state == "search":
            order = self.result["visited_order"]
            for _ in range(3):                       # cells revealed per frame
                if self.shown_count < len(order):
                    self.visited_shown.add(order[self.shown_count])
                    self.shown_count += 1
            if self.shown_count >= len(order):
                self.history[self.algorithm] = self.result["metrics"]
                self.current_metrics = self.result["metrics"]
                if self.result["found"]:
                    self.path_visible = True
                    self.state = "move"
                    self.message = "Path found! Robot is delivering..."
                else:
                    self.state = "done"
                    self.message = "No path exists."
        elif self.state == "move":
            path = self.result["path"]
            if self.path_index >= len(path) - 1:
                self.state = "done"
                self.message = "Delivered!"
                return
            a, b = path[self.path_index], path[self.path_index + 1]
            step_time = 0.06 + 0.03 * self.grid.cost(b)     # slower on mud/water
            self.step_t += dt / step_time
            while self.step_t >= 1 and self.path_index < len(path) - 1:
                self.step_t -= 1
                self.path_index += 1
                if self.path_index < len(path) - 1:
                    a, b = path[self.path_index], path[self.path_index + 1]
            if self.path_index >= len(path) - 1:
                self.robot_pos = path[-1]
            else:
                t = self.step_t
                self.robot_pos = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    # ---------------- input ----------------
    def cell_at(self, pos):
        c = (pos[0] - GRID_X) // CELL
        r = (pos[1] - GRID_Y) // CELL
        if pos[0] >= GRID_X and pos[1] >= GRID_Y and 0 <= r < ROWS and 0 <= c < COLS:
            return (r, c)
        return None

    def paint(self, pos, erase=False):
        if self.state in ("search", "move"):
            return
        cell = self.cell_at(pos)
        if cell is None:
            return
        brush = ROAD if erase else self.brush
        if brush == "start":
            self.grid.set_start(cell)
        elif brush == "goal":
            self.grid.set_goal(cell)
        else:
            self.grid.set_cell(cell, brush)
        self.map_changed()

    def handle_click(self, pos):
        for name, b in self.algo_buttons.items():
            if b.hit(pos) and self.state not in ("search", "move"):
                self.algorithm = name
        for key, b in self.brush_buttons.items():
            if b.hit(pos):
                self.brush = key
        a = self.action_buttons
        if a["Start Simulation"].hit(pos):
            self.start_simulation()
        elif a["Reset"].hit(pos):
            self.reset_simulation()
            self.message = "Reset. Choose an algorithm and press Start."
        elif a["Clear Map"].hit(pos) and self.state not in ("search", "move"):
            self.grid.clear()
            self.map_changed()
            self.message = "Map cleared."
        elif a["Random Map"].hit(pos) and self.state not in ("search", "move"):
            self.grid.randomize()
            self.map_changed()
            self.message = "Random map generated."
        else:
            self.paint(pos)

    # ---------------- drawing ----------------
    def cell_rect(self, r, c, inset=1):
        return pygame.Rect(GRID_X + c * CELL + inset, GRID_Y + r * CELL + inset,
                           CELL - 2 * inset, CELL - 2 * inset)

    def draw_grid(self):
        g = self.grid
        pygame.draw.rect(self.screen, (14, 15, 19),
                         (GRID_X - 4, GRID_Y - 4, COLS * CELL + 8, ROWS * CELL + 8), border_radius=10)
        path_set = set(self.result["path"]) if (self.result and self.path_visible) else set()
        for r in range(ROWS):
            for c in range(COLS):
                p = (r, c)
                color = TERRAIN_COLOR[g.cells[r][c]]
                if p in path_set:
                    color = PATH_COLOR
                elif p in self.visited_shown:
                    color = VISITED_COLOR
                    # tint visited cells slightly by terrain so mud/water stay visible
                    t = TERRAIN_COLOR[g.cells[r][c]]
                    color = tuple((v * 3 + t_ * 1) // 4 for v, t_ in zip(color, t))
                pygame.draw.rect(self.screen, color, self.cell_rect(r, c), border_radius=4)
                if g.cells[r][c] in (MUD, WATER) and p not in path_set and p not in self.visited_shown:
                    cx, cy = self.cell_rect(r, c).center
                    pygame.draw.circle(self.screen, (230, 230, 230), (cx, cy), 2)
        self.draw_start_goal()
        self.draw_robot()

    def draw_start_goal(self):
        r, c = self.grid.start
        rect = self.cell_rect(r, c)
        pygame.draw.rect(self.screen, START_COLOR, rect, border_radius=6)
        txt = self.small.render("S", True, (10, 40, 20))
        self.screen.blit(txt, txt.get_rect(center=rect.center))
        r, c = self.grid.goal                       # destination: red flag
        rect = self.cell_rect(r, c)
        pygame.draw.rect(self.screen, GOAL_COLOR, rect, border_radius=6)
        x, y = rect.center
        pygame.draw.line(self.screen, (255, 255, 255), (x - 4, y + 8), (x - 4, y - 8), 2)
        pygame.draw.polygon(self.screen, (255, 255, 255), [(x - 4, y - 8), (x + 8, y - 4), (x - 4, y)])

    def draw_robot(self):
        r, c = self.robot_pos
        cx = GRID_X + c * CELL + CELL / 2
        cy = GRID_Y + r * CELL + CELL / 2
        pygame.draw.circle(self.screen, (10, 12, 40), (cx + 1, cy + 3), 11)      # shadow
        body = pygame.Rect(0, 0, 22, 20)
        body.center = (cx, cy)
        pygame.draw.rect(self.screen, ROBOT_COLOR, body, border_radius=6)
        pygame.draw.rect(self.screen, (170, 200, 255), body, width=2, border_radius=6)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(cx - 4), int(cy - 2)), 3)   # eyes
        pygame.draw.circle(self.screen, (255, 255, 255), (int(cx + 4), int(cy - 2)), 3)
        pygame.draw.line(self.screen, (170, 200, 255), (cx, body.top), (cx, body.top - 4), 2)  # antenna
        pygame.draw.circle(self.screen, (255, 120, 120), (int(cx), int(body.top - 5)), 2)

    def label(self, text, x, y, font=None, color=MUTED):
        self.screen.blit((font or self.small).render(text, True, color), (x, y))

    def draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_BG, (PANEL_X - 12, 12, WIN_W - PANEL_X, WIN_H - 24), border_radius=12)
        self.screen.blit(self.big.render("Delivery Robot AI", True, TEXT), (PANEL_X, 20))
        mouse = pygame.mouse.get_pos()

        self.label("ALGORITHM", PANEL_X, 46)
        for name, b in self.algo_buttons.items():
            b.active = (name == self.algorithm)
            b.draw(self.screen, self.font, mouse)

        first = next(iter(self.brush_buttons.values()))
        self.label("MAP BRUSH  (right-click = erase)", PANEL_X, first.rect.y - 18)
        for key, b in self.brush_buttons.items():
            b.active = (key == self.brush)
            b.draw(self.screen, self.font, mouse)

        for b in self.action_buttons.values():
            b.draw(self.screen, self.font, mouse)

        self.draw_metrics()

    def draw_metrics(self):
        x, y = PANEL_X, self.metrics_y
        self.label("RESULTS", x, y)
        y += 18
        self.label(self.message, x, y, color=(180, 215, 255))
        y += 22
        m = self.current_metrics
        if m:
            lines = [("Algorithm", m["algorithm"]), ("Nodes explored", m["nodes_explored"]),
                     ("Path length", m["path_length"]), ("Total cost", m["path_cost"]),
                     ("Time", f"{m['time_ms']} ms"), ("Path found", "Yes" if m["found"] else "No")]
            for k, v in lines:
                self.label(k, x, y)
                self.screen.blit(self.small.render(str(v), True, TEXT), (x + 140, y))
                y += 17
        if len(self.history) > 1:                    # comparison on the same map
            y += 6
            self.label("COMPARE (same map)", x, y)
            y += 17
            for name, hm in self.history.items():
                row = f"{name:<7}  expl {hm['nodes_explored']:<4} cost {hm['path_cost']}"
                self.screen.blit(self.small.render(row, True, TEXT), (x, y))
                y += 16

    def draw_legend(self):
        items = [("Road 1", TERRAIN_COLOR[ROAD]), ("Grass 2", TERRAIN_COLOR[GRASS]),
                 ("Mud 5", TERRAIN_COLOR[MUD]), ("Water 8", TERRAIN_COLOR[WATER]),
                 ("Wall", TERRAIN_COLOR[WALL]), ("Visited", VISITED_COLOR), ("Path", PATH_COLOR),
                 ("Start", START_COLOR), ("Goal", GOAL_COLOR)]
        x, y = GRID_X, GRID_Y + ROWS * CELL + 22
        for text, color in items:
            pygame.draw.rect(self.screen, color, (x, y, 16, 16), border_radius=4)
            pygame.draw.rect(self.screen, (90, 95, 110), (x, y, 16, 16), width=1, border_radius=4)
            self.label(text, x + 22, y)
            x += 22 + self.small.size(text)[0] + 16
        self.label("Robot slows down on mud and water. Left-click: paint | Right-click: erase", GRID_X, y + 26)

    def draw(self):
        self.screen.fill(BG)
        self.draw_grid()
        self.draw_legend()
        self.draw_panel()
        pygame.display.flip()

    # ---------------- main loop ----------------
    def run(self):
        dragging = None
        while True:
            dt = self.clock.tick(60) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button == 1:
                        dragging = "paint"
                        self.handle_click(e.pos)
                    elif e.button == 3:
                        dragging = "erase"
                        self.paint(e.pos, erase=True)
                elif e.type == pygame.MOUSEBUTTONUP:
                    dragging = None
                elif e.type == pygame.MOUSEMOTION and dragging:
                    if dragging == "paint" and self.brush not in ("start", "goal"):
                        self.paint(e.pos)
                    elif dragging == "erase":
                        self.paint(e.pos, erase=True)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    App().run()
