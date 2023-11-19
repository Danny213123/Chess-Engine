from random import choice

pieces_val = {"wP": 1, "wB": 2, "wR": 3, "wN": 4, "wQ": 5, "wK": 6, "bP": 7, "bB": 8, "bR": 9, "bN": 10, "bQ": 11, "bK": 12}

def init_zobrist():
    '''
    Initializes the zobrist keys for each piece on each square.
    '''

    global table
    table = []
    pieces = ["wP", "wB", "wR", "wN", "wQ", "wK", "bP", "bB", "bR", "bN", "bQ", "bK"]

    for piece in range(len(pieces)):
        temp = []
        for square in range(64):
            temp.append(''.join(choice('01') for _ in range(64)))
        table.append(temp)
    table.append([''.join(choice('01') for _ in range(64))])


def zobrist_key(game_state):
    '''
    Returns the zobrist key for the current game state.
    :param game_state: current game state
    '''

    global table
    hash_key = 0

    # if white to move, xor the last key
    if game_state.white:
        hash_key = hash_key ^ int(table[-1][0])

    # xor the key for each piece on each square
    for row in range(8):
        for col in range (8):
            if game_state.board[row][col] != "--":
                piece_hash = pieces_val[game_state.board[row][col]] - 1
                hash_key = hash_key ^ int(table[row][piece_hash])

    return hash_key

def save_zobrist():
    '''
    Saves the zobrist keys to a file.
    '''

    global table

    # save zobrist keys to file
    with open("main/Zobrist_keys.txt", "w") as file:

        for row in range(len(table)):

            for col in range(len(table[row])):

                file.write(table[row][col] + "\n")

def load_zobrist():
    '''
    Loads the zobrist keys from a file.
    '''

    global table
    table = []
    pieces = ["wP", "wB", "wR", "wN", "wQ", "wK", "bP", "bB", "bR", "bN", "bQ", "bK"]

    # load zobrist keys from file
    with open("main/Zobrist_keys.txt", "r") as file:

        for piece in range(len(pieces)):

            buffer = []

            for square in range(64):

                buffer.append(file.readline().strip())

            table.append(buffer)

        buffer = []

        buffer.append(file.readline().strip())
        
        table.append(buffer)

