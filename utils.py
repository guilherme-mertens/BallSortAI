import string

def parse_ball_sort_file(file_path):
    
    # Map letters to numbers (A -> 1, B -> 2, ..., Z -> 26)
    letter_to_number = {letter: i + 1 for i, letter in enumerate(string.ascii_uppercase)}
    
    
    raw_tube_data = []
    
    with open(file_path, 'r') as file:
        lines = file.readlines()
        num_tubes = int(lines[0].strip())  # Total Number of tubes
        
        for line in lines[1:]:
            tube = [letter_to_number[char] for char in line.strip()]
            raw_tube_data.append(tube)
        
        raw_tube_data += [[] for _ in range(num_tubes - len(raw_tube_data))]

    return raw_tube_data

color_mapping = {
        1: (255, 0, 0),    # Red
        2: (0, 255, 0),    # Green
        3: (0, 0, 255),    # Blue
        4: (255, 255, 0),  # Yellow
        5: (255, 165, 0),  # Orange
        6: (128, 0, 128),  # Purple
        7: (0, 255, 255),  # Cyan
        8: (255, 192, 203),# Pink
        9: (165, 42, 42),  # Brown
        10: (0, 128, 0),    # Dark Green
        11: (75, 0, 130),   # Indigo
        12: (60, 255, 255), # Light Cyan
        13: (192, 192, 192),# Silver
        14: (255, 20, 147), # Deep Pink
        15: (255, 69, 0),   # Red-Orange
        16: (60, 179, 113), # Medium Sea Green
        17: (30, 144, 255), # Dodger Blue
        18: (218, 112, 214),# Orchid
        19: (0, 255, 127),  # Spring Green
        20: (139, 69, 19),   # Saddle Brown
        21: (10, 50, 120),
        22: (100, 0, 255),
        23: (25, 30, 80),
        24: (0, 150, 127),
        25: (139, 355, 19),
}

file_path = r"tests/L56.txt"
raw_tube_data = parse_ball_sort_file(file_path)

# Exibir os dados
print("raw_tube_data:", raw_tube_data)