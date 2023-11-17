from random import choice

pieces_val = {"wP": 1, "wB": 2, "wR": 3, "wN": 4, "wQ": 5, "wK": 6, "bP": 7, "bB": 8, "bR": 9, "bN": 10, "bQ": 11, "bK": 12}


def init_zobrist():
    global table
    table = []
    pieces = ["wP", "wB", "wR", "wN", "wQ", "wK", "bP", "bB", "bR", "bN", "bQ", "bK"]
    for x in range(len(pieces)):
        temp = []
        for y in range(64):
            temp.append(''.join(choice('01') for _ in range(64)))
        table.append(temp)
    table.append([''.join(choice('01') for _ in range(64))])


def zobrist_key(gs):
    global table
    hash_key = 0

    if gs.white:
        hash_key = hash_key ^ int(table[-1][0])
    for x in range(8):
        for y in range (8):
            if gs.board[x][y] != "--":
                j = pieces_val[gs.board[x][y]] - 1
                hash_key = hash_key ^ int(table[x][j])

    return hash_key

def save_zobrist():
    global table
    with open("main/Zobrist_keys.txt", "w") as f:
        for x in range(len(table)):
            for y in range(len(table[x])):
                f.write(table[x][y] + "\n")

def load_zobrist():
    global table
    table = []
    pieces = ["wP", "wB", "wR", "wN", "wQ", "wK", "bP", "bB", "bR", "bN", "bQ", "bK"]

    with open("main/Zobrist_keys.txt", "r") as f:
        for x in range(len(pieces)):
            temp = []
            for y in range(64):
                temp.append(f.readline().strip())
            table.append(temp)
        temp = []
        temp.append(f.readline().strip())
        table.append(temp)

