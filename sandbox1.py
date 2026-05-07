import tkinter as tk
import random
import time
import math

WIDTH = 800
HEIGHT = 600

# Simulation constants
CELL_SIZE = 5 # Size of grid cells and particles

# --- Element Classes ---

class Particle:
    """Base class for all grid-based particles (Sand, Soil, etc.)."""
    def __init__(self, canvas, x, y, color, flammable=False):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.color = color
        self.size = CELL_SIZE
        self.id = canvas.create_rectangle(x, y, x + self.size, y + self.size, fill=color, outline="")
        self.flammable = flammable
        self.is_burning = False
        self.burn_time = 100

    def update_visuals(self):
        """Syncs the canvas object's position with the particle's internal x, y."""
        self.canvas.coords(self.id, self.x, self.y, self.x + self.size, self.y + self.size)

    def ignite(self):
        if self.flammable and not self.is_burning:
            self.is_burning = True
            self.canvas.itemconfig(self.id, fill="orange")

    def burn_damage(self):
        self.burn_time -= 1
        if random.random() < 0.1:
            self.canvas.itemconfig(self.id, fill=random.choice(["red", "orange", "#FF4500"]))
        if self.burn_time <= 0:
            self.destroy()

    def destroy(self):
        self.canvas.delete(self.id)

# Subclasses of Particle
class Sand(Particle):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y, random.choice(["#F4A460", "#DEB887"]))

class Soil(Particle):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y, "#8B4513")

class Water(Particle):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y, "#1E90FF")

class Wood(Particle):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y, "#A0522D", flammable=True)


class Bomb:
    """A non-grid object for explosions."""
    def __init__(self, canvas, x, y, bomb_type='obliterate'):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.radius = 8
        self.bomb_type = bomb_type
        color = "#404040" if bomb_type == 'obliterate' else "#800000"
        self.id = canvas.create_oval(x-self.radius, y-self.radius, x+self.radius, y+self.radius, fill=color)
        self.fuse_time = 3.0
        self.exploded = False
        self.fuse_id = self.canvas.create_line(x, y-self.radius, x, y-self.radius-5, fill="red", width=2)
    
    def update(self, dt):
        self.vy += 900 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y + self.radius > HEIGHT:
            self.y = HEIGHT - self.radius
            self.vy = 0
        self.canvas.coords(self.id, self.x-self.radius, self.y-self.radius, self.x+self.radius, self.y+self.radius)
        
        self.fuse_time -= dt
        fuse_length = max(0, (self.fuse_time / 3.0) * 5)
        self.canvas.coords(self.fuse_id, self.x, self.y - self.radius, self.x, self.y - self.radius - fuse_length)
        if self.fuse_time <= 0 and not self.exploded:
            self.exploded = True
            if self.fuse_id in self.canvas.find_all(): self.canvas.delete(self.fuse_id)
            
    def destroy(self):
        self.canvas.delete(self.id)
        if self.fuse_id in self.canvas.find_all(): self.canvas.delete(self.fuse_id)


class Ball:
    """A non-grid object for standard physics."""
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = random.randint(10, 20)
        self.vx = (random.random() - 0.5) * 300
        self.vy = (random.random() - 0.5) * 300
        self.color = f"#{random.randint(50, 255):02x}{random.randint(50, 255):02x}{random.randint(50, 255):02x}"
        self.id = canvas.create_oval(x-self.radius, y-self.radius, x+self.radius, y+self.radius, fill=self.color)
    
    def update(self, dt):
        self.vy += 900 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x - self.radius < 0 or self.x + self.radius > WIDTH: self.vx *= -0.75
        if self.y - self.radius < 0 or self.y + self.radius > HEIGHT: self.vy *= -0.75
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(HEIGHT - self.radius, self.y))
        self.canvas.coords(self.id, self.x-self.radius, self.y-self.radius, self.x+self.radius, self.y+self.radius)

    def destroy(self):
        self.canvas.delete(self.id)

# --- Main Application ---

class PhysicsSandbox:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#87CEEB")
        self.canvas.pack(side=tk.LEFT)

        self.grid_width = WIDTH // CELL_SIZE
        self.grid_height = HEIGHT // CELL_SIZE
        self.grid = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        self.elements = []
        self.tool = "sand"
        self.running = True
        self.last_time = time.time()
        
        # --- NEW: Variables for continuous spawning ---
        self.is_mouse_down = False
        self.mouse_x = 0
        self.mouse_y = 0
        
        self.setup_ui()
        self.bind_controls()
        self.update_loop()

    def setup_ui(self):
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(frame, text="Tools", font=("Arial", 12, "bold")).pack(anchor="w")
        tools = ["sand", "soil", "water", "wood", "ball", "bomb", "fire_bomb"]
        for tool in tools:
            tk.Button(frame, text=tool.replace("_", " ").title(), command=lambda t=tool: self.set_tool(t)).pack(fill=tk.X, pady=2)
        tk.Label(frame, text="\nControls", font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(frame, text="p - Pause/Play\nc - Clear All\nq - Quit", justify=tk.LEFT).pack(anchor="w")

    def bind_controls(self):
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        # --- NEW: Bind mouse release to stop continuous spawning ---
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.root.bind("p", lambda e: self.toggle_pause())
        self.root.bind("c", lambda e: self.clear_all())
        self.root.bind("q", lambda e: self.root.quit())

    def set_tool(self, tool_name):
        self.tool = tool_name

    def on_mouse_down(self, event):
        self.is_mouse_down = True
        self.mouse_x, self.mouse_y = event.x, event.y
        # Spawn one element on the initial click
        self.spawn_element(event.x, event.y)

    def on_mouse_drag(self, event):
        # Update mouse position for continuous spawning while dragging
        self.mouse_x, self.mouse_y = event.x, event.y

    def on_mouse_up(self, event):
        self.is_mouse_down = False

    def spawn_element(self, x, y):
        grid_x, grid_y = x // CELL_SIZE, y // CELL_SIZE
        if not (0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height): return
        if self.grid[grid_y][grid_x] is not None: return

        tool_map = {"sand": Sand, "soil": Soil, "water": Water, "wood": Wood}
        if self.tool in tool_map:
            elem = tool_map[self.tool](self.canvas, grid_x * CELL_SIZE, grid_y * CELL_SIZE)
            self.elements.append(elem)
            self.grid[grid_y][grid_x] = elem
        elif self.tool == "ball":
            self.elements.append(Ball(self.canvas, x, y))
        elif self.tool == "bomb":
            self.elements.append(Bomb(self.canvas, x, y, 'obliterate'))
        elif self.tool == "fire_bomb":
            self.elements.append(Bomb(self.canvas, x, y, 'incendiary'))

    def clear_all(self):
        for element in self.elements:
            element.destroy()
        self.elements.clear()
        self.grid = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]

    def toggle_pause(self):
        self.running = not self.running

    def update_particles(self):
        for y in range(self.grid_height - 1, -1, -1):
            for x in range(self.grid_width - 1, -1, -1):
                particle = self.grid[y][x]
                if not particle: continue
                
                if hasattr(particle, 'is_burning') and particle.is_burning:
                    particle.burn_damage()
                    continue

                # --- NEW: Water has special sideways "flow" logic ---
                is_water = isinstance(particle, Water)

                # 1. Check directly below
                if y + 1 < self.grid_height and self.grid[y + 1][x] is None:
                    self.grid[y][x], self.grid[y + 1][x] = None, particle
                    particle.y += CELL_SIZE
                else:
                    # 2. Check diagonals
                    can_go_left = x > 0 and y + 1 < self.grid_height and self.grid[y + 1][x - 1] is None
                    can_go_right = x + 1 < self.grid_width and y + 1 < self.grid_height and self.grid[y + 1][x + 1] is None
                    
                    move_dir = 0
                    if can_go_left and can_go_right: move_dir = random.choice([-1, 1])
                    elif can_go_left: move_dir = -1
                    elif can_go_right: move_dir = 1
                    
                    if move_dir != 0:
                        self.grid[y][x], self.grid[y + 1][x + move_dir] = None, particle
                        particle.y += CELL_SIZE
                        particle.x += move_dir * CELL_SIZE
                    # 3. --- WATER ONLY: Try to flow sideways ---
                    elif is_water:
                        side_can_go_left = x > 0 and self.grid[y][x - 1] is None
                        side_can_go_right = x + 1 < self.grid_width and self.grid[y][x + 1] is None

                        side_move_dir = 0
                        if side_can_go_left and side_can_go_right: side_move_dir = random.choice([-1, 1])
                        elif side_can_go_left: side_move_dir = -1
                        elif side_can_go_right: side_move_dir = 1
                        
                        if side_move_dir != 0:
                            self.grid[y][x], self.grid[y][x + side_move_dir] = None, particle
                            particle.x += side_move_dir * CELL_SIZE

    def handle_explosions(self, dt):
        bombs_to_detonate = [b for b in self.elements if isinstance(b, Bomb) and b.exploded]
        for bomb in bombs_to_detonate:
            # Blast particles
            for y in range(self.grid_height):
                for x in range(self.grid_width):
                    particle = self.grid[y][x]
                    if particle:
                        dist = math.hypot(particle.x - bomb.x, particle.y - bomb.y)
                        if dist < 80:
                            if bomb.bomb_type == 'obliterate' and dist < 50:
                                particle.destroy()
                                self.grid[y][x] = None
                            elif bomb.bomb_type == 'incendiary' and particle.flammable:
                                particle.ignite()
            # Blast balls
            for elem in self.elements:
                if isinstance(elem, Ball):
                    dist = math.hypot(elem.x - bomb.x, elem.y - bomb.y)
                    if dist < 150:
                        angle = math.atan2(elem.y - bomb.y, elem.x - bomb.x)
                        force = 4000 * (1 - dist / 150)
                        elem.vx += math.cos(angle) * force
                        elem.vy += math.sin(angle) * force
            
            bomb.destroy()
        self.elements = [e for e in self.elements if not (isinstance(e, Bomb) and e.exploded)]

    def update_loop(self):
        if self.running:
            current = time.time()
            dt = min(current - self.last_time, 0.05)
            self.last_time = current

            # --- NEW: Continuous spawning on mouse hold ---
            if self.is_mouse_down and self.tool in ["sand", "soil", "water", "wood"]:
                # Add a bit of randomness to make the stream look more natural
                self.spawn_element(self.mouse_x + random.randint(-4, 4), self.mouse_y + random.randint(-4, 4))

            # Update non-particle elements
            for elem in self.elements:
                if not isinstance(elem, Particle): elem.update(dt)

            self.update_particles()
            
            # Update visuals after physics
            for elem in self.elements:
                if hasattr(elem, 'update_visuals'): elem.update_visuals()

            self.handle_explosions(dt)
            self.elements = [e for e in self.elements if e.id in self.canvas.find_all()]

        self.root.after(16, self.update_loop)

def main():
    root = tk.Tk()
    root.title("Flowing Sandbox")
    app = PhysicsSandbox(root)
    root.mainloop()

if __name__ == "__main__":
    main()