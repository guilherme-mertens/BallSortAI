import pygame
import sys
import time

# Constants
MAX_CAPACITY = 4
BALL_RADIUS = 20
TUBE_SPACING = 80
MOVE_SPEED = 10
ANIMATION_DELAY = 0.02

COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 165, 0),
    (128, 0, 128), (0, 255, 255), (255, 192, 203), (165, 42, 42), (0, 128, 0),
    (75, 0, 130), (0, 0, 0), (192, 192, 192), (255, 20, 147), (255, 69, 0),
    (60, 179, 113), (30, 144, 255), (218, 112, 214), (0, 255, 127), (139, 69, 19)
]

class Ball:
    def __init__(self, color):
        self.color = color
        self.x = 0
        self.y = 0

class Tube:
    def __init__(self, x, y, balls):
        self.x = x
        self.y = y
        self.width = 60
        self.height = 4 * 2 * BALL_RADIUS
        self.balls = [Ball(color) for color in balls]

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), (self.x, self.y, self.width, self.height), 2)
        for i, ball in enumerate(self.balls):
            ball.x = self.x + self.width // 2
            ball.y = self.y + self.height - (i * 40) - BALL_RADIUS
            pygame.draw.circle(screen, ball.color, (ball.x, ball.y), BALL_RADIUS)

class BallSortGame:
    def __init__(self, tube_data):
        pygame.init()
        self.tubes = [Tube(i * TUBE_SPACING + 50, 100, tube) for i, tube in enumerate(tube_data)]
        self.width = max(800, len(self.tubes) * TUBE_SPACING + 100)
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.selected_tube = None
        self.selected_ball = None
        self.running = True

    def draw(self):
        self.screen.fill((0, 0, 0))
        for tube in self.tubes:
            tube.draw(self.screen)
        if self.selected_ball:
            pygame.draw.circle(self.screen, self.selected_ball.color, (self.selected_ball.x, self.selected_ball.y), BALL_RADIUS)
        pygame.display.flip()

    def animate_selection(self, tube):
        if not tube.balls:
            return
        self.selected_ball = tube.balls.pop()
        peak_height = tube.y - 3 * BALL_RADIUS

        while self.selected_ball.y > peak_height:
            self.selected_ball.y -= MOVE_SPEED
            self.draw()
            time.sleep(ANIMATION_DELAY)

    def move_ball(self, from_tube, to_tube):
        if not self.selected_ball or len(to_tube.balls) >= 4:
            return
        
        target_x = to_tube.x + to_tube.width // 2
        target_y = to_tube.y + to_tube.height - len(to_tube.balls) * 40 - BALL_RADIUS

        while self.selected_ball.x != target_x:
            self.selected_ball.x += MOVE_SPEED if self.selected_ball.x < target_x else -MOVE_SPEED
            self.draw()
            time.sleep(ANIMATION_DELAY)

        while self.selected_ball.y < target_y:
            self.selected_ball.y += MOVE_SPEED
            self.draw()
            time.sleep(ANIMATION_DELAY)

        to_tube.balls.append(self.selected_ball)
        self.selected_ball = None  

    def check_win(self):
        if self.selected_ball:
            return False

        color_tubes = {}
        for tube in self.tubes:
            if tube.balls:
                colors = set(ball.color for ball in tube.balls)
                if len(colors) > 1:
                    return False  
                color = tube.balls[0].color
                color_tubes[color] = color_tubes.get(color, 0) + 1

        return all(count == 1 for count in color_tubes.values())

    def handle_click(self, x, y):
        for tube in self.tubes:
            if tube.x < x < tube.x + tube.width and tube.y < y < tube.y + tube.height:
                if self.selected_tube:
                    self.move_ball(self.selected_tube, tube)
                    self.selected_tube = None
                else:
                    if tube.balls:
                        self.selected_tube = tube
                        self.animate_selection(tube)
                break

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(*event.pos)
            self.draw()
            if self.check_win():
                print("Congratulations! You won!")
                self.running = False
        pygame.quit()
        sys.exit()


tube_data = [
    [COLORS[0], COLORS[0], COLORS[0], COLORS[0]],
    [COLORS[1], COLORS[1], COLORS[1], COLORS[2]],
    [COLORS[2], COLORS[2], COLORS[2], COLORS[1]],
    []
]

game = BallSortGame(tube_data)
game.run()
