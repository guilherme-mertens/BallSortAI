import pygame
import sys
import os
import time
import sqlite3
import ast
from collections import deque
from typing import List, Tuple, Dict, Optional
from ortools.sat.python import cp_model

# ------------------------------------------------------------------------------
# Global constants for visual representation and puzzle settings
# ------------------------------------------------------------------------------
MAX_CAPACITY = 6
BALL_RADIUS = 20
TUBE_WIDTH = 60
TUBE_SPACING = 80
MOVE_SPEED = 10
ANIMATION_DELAY = 0.02

# ------------------------------------------------------------------------------
# Domain Classes
# ------------------------------------------------------------------------------

class BallSortState:
    """
    Represents an immutable puzzle state.
    Each state is a tuple of tubes (each tube is a tuple of ball colors).
    """
    def __init__(self, tubes: Tuple[Tuple[int, ...], ...]):
        self.tubes = tubes

    def __hash__(self):
        return hash(self.tubes)

    def __eq__(self, other):
        return isinstance(other, BallSortState) and self.tubes == other.tubes

    def __str__(self):
        return str(self.tubes)

    def __repr__(self):
        return f"BallSortState({self.tubes})"


class Move:
    """
    Represents a legal move: moving the top ball from tube 'src' to tube 'dst'.
    """
    def __init__(self, src: int, dst: int, color: int):
        self.src = src
        self.dst = dst
        self.color = color

    def __str__(self):
        return f"Move: ball color {self.color} from tube {self.src} to tube {self.dst}"

    def __repr__(self):
        return f"Move(src={self.src}, dst={self.dst}, color={self.color})"


class BallSortPuzzle:
    """
    Encapsulates the puzzle rules and the initial configuration.
    """
    def __init__(self, tube_data: List[List[int]]):
        # tube_data: each inner list represents a tube from bottom to top.
        self.initial_state = BallSortState(tuple(tuple(tube) for tube in tube_data))
        self.num_tubes = len(tube_data)

    def is_solved(self, state: BallSortState) -> bool:
        """
        The puzzle is solved when each non‑empty tube is "pure"
        (i.e., all balls in that tube are of the same color).
        (It is allowed that two or more tubes contain the same color.)
        """
        for tube in state.tubes:
            if tube and not all(ball == tube[0] for ball in tube):
                return False
        return True

    def get_legal_moves(self, state: BallSortState) -> List[Move]:
        """
        Returns a list of legal moves from the given state.
        A move is legal if:
          - The source tube is non‑empty.
          - The destination tube is not full.
          - Either the destination is empty or its top ball matches the moving ball.
          - Source and destination are different.
        """
        moves = []
        for src in range(self.num_tubes):
            tube_src = state.tubes[src]
            if not tube_src:
                continue  # nothing to move
            ball = tube_src[-1]
            for dst in range(self.num_tubes):
                if src == dst:
                    continue
                tube_dst = state.tubes[dst]
                if len(tube_dst) >= MAX_CAPACITY:
                    continue
                if tube_dst and tube_dst[-1] != ball:
                    continue
                moves.append(Move(src, dst, ball))
        return moves

    def apply_move(self, state: BallSortState, move: Move) -> BallSortState:
        """
        Returns a new state after applying the given move.
        """
        new_tubes = [list(tube) for tube in state.tubes]
        ball = new_tubes[move.src].pop()
        new_tubes[move.dst].append(ball)
        return BallSortState(tuple(tuple(tube) for tube in new_tubes))


# ------------------------------------------------------------------------------
# Disk-Based State Graph Storage (using SQLite)
# ------------------------------------------------------------------------------

class StateGraphDB:
    """
    Stores the state graph on disk using SQLite.
    Two tables are used:
      - 'states' stores each unique state (as a string) and its id.
      - 'transitions' stores transitions (edges) with details of the move.
    """
    def __init__(self, db_filename: str, puzzle: BallSortPuzzle):
        self.db_filename = db_filename
        self.puzzle = puzzle
        self.conn = sqlite3.connect(self.db_filename)
        self.create_tables()
    
    def create_tables(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        state TEXT UNIQUE
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS transitions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        from_state INTEGER,
                        to_state INTEGER,
                        src_tube INTEGER,
                        dst_tube INTEGER,
                        ball_color INTEGER
                     )''')
        self.conn.commit()
    
    def insert_state(self, state: BallSortState) -> int:
        """
        Inserts a state into the DB (if not already present) and returns its id.
        """
        state_str = str(state.tubes)
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO states (state) VALUES (?)", (state_str,))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # already exists
        c.execute("SELECT id FROM states WHERE state=?", (state_str,))
        row = c.fetchone()
        return row[0]
    
    def insert_transition(self, from_id: int, to_id: int, move: Move):
        """
        Inserts a transition (edge) into the DB.
        """
        c = self.conn.cursor()
        c.execute("INSERT INTO transitions (from_state, to_state, src_tube, dst_tube, ball_color) VALUES (?, ?, ?, ?, ?)",
                  (from_id, to_id, move.src, move.dst, move.color))
        self.conn.commit()
    
    def build_graph(self, max_depth: int):
        """
        Performs a BFS from the initial state up to max_depth moves.
        States and transitions are stored on disk.
        """
        queue = deque()
        initial_state = self.puzzle.initial_state
        initial_id = self.insert_state(initial_state)
        queue.append((initial_id, 0))
        visited = {initial_id}
        c = self.conn.cursor()
        
        while queue:
            state_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            c.execute("SELECT state FROM states WHERE id=?", (state_id,))
            row = c.fetchone()
            if row is None:
                continue
            state_str = row[0]
            tubes = ast.literal_eval(state_str)
            current_state = BallSortState(tubes)
            moves = self.puzzle.get_legal_moves(current_state)
            for move in moves:
                new_state = self.puzzle.apply_move(current_state, move)
                new_state_id = self.insert_state(new_state)
                self.insert_transition(state_id, new_state_id, move)
                if new_state_id not in visited:
                    visited.add(new_state_id)
                    queue.append((new_state_id, depth + 1))
    
    def get_num_states(self) -> int:
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM states")
        row = c.fetchone()
        return row[0]
    
    def get_initial_state_id(self) -> int:
        initial_state_str = str(self.puzzle.initial_state.tubes)
        c = self.conn.cursor()
        c.execute("SELECT id FROM states WHERE state=?", (initial_state_str,))
        row = c.fetchone()
        return row[0] if row else -1
    
    def get_allowed_transitions(self) -> List[List[int]]:
        """
        Returns a list of pairs [from_state, to_state] representing allowed transitions.
        """
        c = self.conn.cursor()
        c.execute("SELECT from_state, to_state FROM transitions")
        transitions = []
        for row in c.fetchall():
            transitions.append([row[0], row[1]])
        return transitions
    
    def get_transition_move(self, from_state: int, to_state: int) -> Optional[Move]:
        """
        Returns the move details for a transition from 'from_state' to 'to_state'.
        """
        c = self.conn.cursor()
        c.execute("SELECT src_tube, dst_tube, ball_color FROM transitions WHERE from_state=? AND to_state=? LIMIT 1",
                  (from_state, to_state))
        row = c.fetchone()
        if row:
            return Move(row[0], row[1], row[2])
        return None

    def get_state_by_id(self, state_id: int) -> Optional[BallSortState]:
        c = self.conn.cursor()
        c.execute("SELECT state FROM states WHERE id=?", (state_id,))
        row = c.fetchone()
        if row:
            tubes = ast.literal_eval(row[0])
            return BallSortState(tubes)
        return None

    def get_db_size(self):
        """Returns the size of the database file in bytes."""
        if os.path.exists(self.db_filename):
            return os.path.getsize(self.db_filename)
        return None

    def cleanup(self):
        """
        Drops the tables so that no ghost data remains.
        """
        c = self.conn.cursor()
        c.execute("DROP TABLE IF EXISTS transitions")
        c.execute("DROP TABLE IF EXISTS states")
        self.conn.commit()

    def close(self):
        self.conn.close()


# ------------------------------------------------------------------------------
# CP Model Solver using the Disk-Based Graph with Mapping
# ------------------------------------------------------------------------------

class CPPathSolver:
    """
    Uses OR-Tools CP-SAT to select a valid sequence of states over time.
    This version builds a mapping between the database's state IDs and a dense
    range of indices [0, num_states-1] used for the CP model.
    """
    def __init__(self, graph_db: StateGraphDB, horizon: int):
        self.graph_db = graph_db
        self.horizon = horizon
        self.model = cp_model.CpModel()
        self.state_vars = []  # List of cp_model.IntVar (indices)
        self.solver = cp_model.CpSolver()
        self.db_state_ids = []  # List of DB state IDs (ordered)
        self.id_to_index: Dict[int, int] = {}

    def build_model(self):
        # Build mapping from DB state IDs to dense indices.
        c = self.graph_db.conn.cursor()
        c.execute("SELECT id FROM states ORDER BY id")
        self.db_state_ids = [row[0] for row in c.fetchall()]
        num_states = len(self.db_state_ids)
        self.id_to_index = {db_id: idx for idx, db_id in enumerate(self.db_state_ids)}
        
        # Create CP state variables that range over these indices.
        self.state_vars = [
            self.model.NewIntVar(0, num_states - 1, f"X_{t}")
            for t in range(self.horizon + 1)
        ]
        # (1) Fix the initial state.
        init_db_state_id = self.graph_db.get_initial_state_id()
        if init_db_state_id not in self.id_to_index:
            raise ValueError("Initial state not found in DB mapping.")
        init_index = self.id_to_index[init_db_state_id]
        self.model.Add(self.state_vars[0] == init_index)
        
        # (2) Constrain the final state to be solved.
        solved_indices = []
        for db_id in self.db_state_ids:
            state = self.graph_db.get_state_by_id(db_id)
            if state and self.graph_db.puzzle.is_solved(state):
                solved_indices.append(self.id_to_index[db_id])
        if not solved_indices:
            self.model.Add(self.state_vars[self.horizon] == -1)
        else:
            self.model.AddAllowedAssignments([self.state_vars[self.horizon]], [[i] for i in solved_indices])
        
        # (3) Allowed transitions.
        allowed_transitions_db = self.graph_db.get_allowed_transitions()
        allowed_transitions = []
        for (from_state, to_state) in allowed_transitions_db:
            if from_state in self.id_to_index and to_state in self.id_to_index:
                allowed_transitions.append([self.id_to_index[from_state], self.id_to_index[to_state]])
        for t in range(self.horizon):
            self.model.AddAllowedAssignments([self.state_vars[t], self.state_vars[t+1]], allowed_transitions)

    def solve(self) -> Optional[List[int]]:
        self.build_model()
        status = self.solver.Solve(self.model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            sol_indices = [self.solver.Value(var) for var in self.state_vars]
            # Convert CP indices back to actual DB state IDs.
            sol_db_ids = [self.db_state_ids[i] for i in sol_indices]
            return sol_db_ids
        return None


# ------------------------------------------------------------------------------
# CP Model Interpreter: Recover the move sequence from the state path.
# ------------------------------------------------------------------------------

class CPModelInterpreter:
    """
    Given the sequence of state IDs from the CP model, recovers the sequence of moves.
    """
    def __init__(self, graph_db: StateGraphDB):
        self.graph_db = graph_db

    def extract_moves(self, state_path: List[int]) -> Optional[List[Move]]:
        moves = []
        for i in range(len(state_path) - 1):
            move = self.graph_db.get_transition_move(state_path[i], state_path[i+1])
            if move is None:
                return None
            moves.append(move)
        return moves


# ------------------------------------------------------------------------------
# Visual Representation with Pygame
# ------------------------------------------------------------------------------

class Visualizer:
    """
    Provides a simple Pygame visualization to animate the solution moves.
    """
    def __init__(self, tube_data: List[List[int]], color_mapping: Dict[int, Tuple[int, int, int]]):
        pygame.init()
        self.tube_data = tube_data  # initial tube configuration
        self.color_mapping = color_mapping
        self.tubes = []  # list of dicts holding tube position and current ball list
        self.width = max(800, len(tube_data) * TUBE_SPACING + 100)
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Ball Sort Puzzle CP Solution")
        self.clock = pygame.time.Clock()
        # Initialize tube positions.
        for i in range(len(tube_data)):
            x = i * TUBE_SPACING + 50
            y = 100
            self.tubes.append({'x': x, 'y': y, 'balls': list(tube_data[i])})

    def draw(self):
        self.screen.fill((0, 0, 0))
        for tube in self.tubes:
            x = tube['x']
            y = tube['y']
            pygame.draw.rect(self.screen, (255, 255, 255),
                             (x, y, TUBE_WIDTH, MAX_CAPACITY * 2 * BALL_RADIUS), 2)
            for i, ball in enumerate(tube['balls']):
                ball_x = x + TUBE_WIDTH // 2
                ball_y = y + MAX_CAPACITY * 2 * BALL_RADIUS - (i * 40) - BALL_RADIUS
                pygame.draw.circle(self.screen, self.color_mapping.get(ball, (200, 200, 200)),
                                   (ball_x, ball_y), BALL_RADIUS)
        pygame.display.flip()

    def animate_move(self, move: Move):
        """
        Animates moving the top ball from tube[move.src] to tube[move.dst].
        """
        if not self.tubes[move.src]['balls']:
            return
        ball = self.tubes[move.src]['balls'].pop()
        src_tube = self.tubes[move.src]
        dst_tube = self.tubes[move.dst]
        start_x = src_tube['x'] + TUBE_WIDTH // 2
        start_y = src_tube['y'] + MAX_CAPACITY * 2 * BALL_RADIUS - (len(src_tube['balls']) * 40) - BALL_RADIUS
        dst_ball_count = len(dst_tube['balls'])
        target_x = dst_tube['x'] + TUBE_WIDTH // 2
        target_y = dst_tube['y'] + MAX_CAPACITY * 2 * BALL_RADIUS - (dst_ball_count * 40) - BALL_RADIUS
        current_x, current_y = start_x, start_y

        # Animate upward.
        peak_y = src_tube['y'] - 3 * BALL_RADIUS
        while current_y > peak_y:
            current_y -= MOVE_SPEED
            self.draw()
            pygame.draw.circle(self.screen, self.color_mapping.get(ball, (200, 200, 200)),
                               (current_x, current_y), BALL_RADIUS)
            pygame.display.flip()
            self.clock.tick(60)
            time.sleep(ANIMATION_DELAY)
        # Animate horizontal.
        while current_x != target_x:
            if current_x < target_x:
                current_x = min(current_x + MOVE_SPEED, target_x)
            else:
                current_x = max(current_x - MOVE_SPEED, target_x)
            self.draw()
            pygame.draw.circle(self.screen, self.color_mapping.get(ball, (200, 200, 200)),
                               (current_x, current_y), BALL_RADIUS)
            pygame.display.flip()
            self.clock.tick(60)
            time.sleep(ANIMATION_DELAY)
        # Animate downward.
        while current_y < target_y:
            current_y += MOVE_SPEED
            self.draw()
            pygame.draw.circle(self.screen, self.color_mapping.get(ball, (200, 200, 200)),
                               (current_x, current_y), BALL_RADIUS)
            pygame.display.flip()
            self.clock.tick(60)
            time.sleep(ANIMATION_DELAY)
        dst_tube['balls'].append(ball)
        self.draw()

    def animate_solution(self, solution_moves: List[Move], delay: float = 0.5):
        """
        Replays the solution by animating each move.
        """
        self.draw()
        time.sleep(delay)
        for move in solution_moves:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            self.animate_move(move)
            time.sleep(delay)
        time.sleep(2)
        pygame.quit()


# ------------------------------------------------------------------------------
# Main: Integrate disk-based state graph, CP, iterative deepening, and visualization.
# ------------------------------------------------------------------------------
if __name__ == "__main__":

    # # Each tube is given as a list (from bottom to top) of integers representing ball colors.
    # raw_tube_data = [
    #     [1, 2, 3, 4],
    #     [5, 1, 2, 3],
    #     [4, 5, 1, 2],
    #     [3, 4, 5, 1],
    #     [2, 3, 4, 5],
    #     []
    # ]
    # # Define a mapping from ball color (integer) to an RGB tuple.
    # color_mapping = {
    #     1: (255, 0, 0),      # red
    #     2: (0, 255, 0),      # green
    #     3: (0, 0, 255),      # blue
    #     4: (255, 255, 0),    # yellow
    #     5: (255, 165, 0)     # orange
    # }

    raw_tube_data = [
        [1, 2, 5, 3, 3],
        [3, 1, 2, 5, 4],
        [5, 4, 2, 3, 1],
        [4, 1, 3, 5],
        [],
        []
    ]
    color_mapping = {
        1: (255, 0, 0),    # red
        2: (0, 255, 0),    # green
        3: (0, 0, 255),     # blue
        4: (255, 255, 0),
        5: (0, 255, 255)
    }

    # Create the puzzle instance.
    puzzle = BallSortPuzzle(raw_tube_data)
    
    # Create the disk-based state graph.
    db_filename = "state_graph.db"
    max_moves = 20  # maximum planning horizon
    graph_db = StateGraphDB(db_filename, puzzle)
    print("Building state graph on disk...")
    graph_db.build_graph(max_moves)
    num_states = graph_db.get_num_states()
    print(f"State graph built with {num_states} states (stored in {db_filename}).")
    
    # Iterative deepening: try horizons from 1 to max_moves until a solution is found.
    solution_state_path = None
    solution_moves = None
    for horizon in range(1, max_moves + 1):
        print(f"Trying horizon: {horizon}")
        cp_solver = CPPathSolver(graph_db, horizon)
        state_path = cp_solver.solve()
        if state_path is not None:
            interpreter = CPModelInterpreter(graph_db)
            solution_moves = interpreter.extract_moves(state_path)
            if solution_moves is not None:
                print(f"Solution found with horizon {horizon}.")
                solution_state_path = state_path
                break

    if solution_moves is None:
        print("No solution found within", max_moves, "moves.")
        
        # Print the database size before dropping tables
        size_before = graph_db.get_db_size()
        print(f"\nDatabase size before cleanup: {size_before / 1024 / 1024:.2f} MB")
        # Clean up: drop the tables and close the DB.
        graph_db.cleanup()
        graph_db.close()
        print(f"Table Dropped - Freed up disk space\n")

        sys.exit(1)

    # Print the solution moves.
    print("Solution moves:")
    for i, move in enumerate(solution_moves):
        print(f"Move {i+1}: {move}")

    # Visualize the solution using Pygame.
    visualizer = Visualizer(raw_tube_data, color_mapping)
    visualizer.animate_solution(solution_moves, delay=0.8)
    
    # Print the database size before dropping tables
    size_before = graph_db.get_db_size()
    print(f"\nDatabase size before cleanup: {size_before / 1024 / 1024:.2f} MB")

    # Clean up: drop the tables and close the DB.
    graph_db.cleanup()
    graph_db.close()
    print(f"Table Dropped - Freed up disk space\n")