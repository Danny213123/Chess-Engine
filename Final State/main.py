import pygame as py
import ChessEngine
import Zobrist_keys
import ChessAlgorithm

width = height = 512
dimension = 8
square_size = height // dimension

chess_images = {}


def load_images():
    pieces = ['wP', 'wR', 'wN', 'wB', 'wK', 'wQ', 'bP', 'bR', 'bN', 'bB', 'bK', 'bQ']
    for piece in pieces:
        chess_images[piece] = py.transform.scale(py.image.load("images/" + piece + ".png"), (square_size, square_size))


def main():
    py.init()
    screen = py.display.set_mode((width, height))
    clock = py.time.Clock()
    screen.fill(py.Color("white"))
    gs = ChessEngine.GameState()
    load_images()
    Zobrist_keys.init_zobrist()
    valid_moves = gs.get_valid_moves()
    made_move = False
    animate = True
    gameOver = False

    square_selected = ()
    player_clicks = []

    running = True

    player_one, player_two = True, False

    while running:

        human = (gs.white and player_one) or (not gs.white and player_two)

        for e in py.event.get():
            # print (e)
            if e.type == py.QUIT:
                running = False
            elif e.type == py.MOUSEBUTTONDOWN:
                if not gameOver and human:
                    location = py.mouse.get_pos()
                    col = location[0] // square_size
                    row = location[1] // square_size
                    if square_selected == (row, col):
                        square_selected = ()
                        player_clicks = []
                    else:
                        square_selected = (row, col)
                        player_clicks.append((row, col))
                    if len(player_clicks) == 2:
                        move = ChessEngine.Move(player_clicks[0], player_clicks[1], gs.board)
                        for x in range(len(valid_moves)):
                            if move == valid_moves[x]:
                                move = valid_moves[x]
                                gs.make_move(move)
                                made_move = True
                                animate = True
                                square_selected = ()
                                player_clicks = []
                        if not made_move:
                            player_clicks = [square_selected]

            elif e.type == py.KEYDOWN:
                if e.key == py.K_z:
                    gs.undo_move()
                    made_move = True
                    animate = False
                    gameOver = False
                if e.key == py.K_r:
                    gs = ChessEngine.GameState()
                    valid_moves = gs.get_valid_moves()
                    square_selected = ()
                    player_clicks = []
                    made_move = False
                    gameOver = False
                    animate = False

        if not gameOver and not human:
            temp_gs = gs
            ai_move = ChessAlgorithm.find_best_move(temp_gs, valid_moves)
            gs.make_move(ai_move)
            made_move = True
            animate = True

        if made_move:
            if animate:
                animate_move(gs.move_log[-1], screen, gs.board, clock)
            valid_moves = gs.get_valid_moves()
            made_move = False
            animate = False

        if gs.square_under_attack(gs.black_king[0],gs.black_king[1]):
            print ("Check on Black King")


        if gs.check_mate:
            gameOver = True
            if gs.white:
                draw_text(screen, "Black wins: Checkmate")
            else:
                draw_text(screen, "White wins: Checkmate")

        if gs.stale_mate:
            gameOver = True
            draw_text(screen, "Stalemate")

        draw_game_state(screen, gs, valid_moves, square_selected)
        clock.tick(200)
        py.display.flip()


def draw_game_state(screen, gs, valid_moves, square_selected):
    draw_board(screen)
    draw_pieces(screen, gs.board)
    highlight(screen, gs, valid_moves, square_selected)


def highlight(screen, gs, valid_moves, square_selected):
    s = py.Surface((square_size, square_size))
    s.set_alpha(50)  # transparency
    if square_selected != ():
        row, col = square_selected
        if gs.board[row][col][0] == ("w" if gs.white else "b"):
            s.fill(py.Color("blue"))
            screen.blit(s, (col * square_size, row * square_size))

            s.fill(py.Color("yellow"))
            for move in valid_moves:

                if move.start_row == row and move.start_col == col:
                    screen.blit(s, (square_size * move.end_col, square_size * move.end_row))

            s.fill(py.Color("red"))
            if gs.square_under_attack(row, col):
                screen.blit(s, (col * square_size, row * square_size))


def draw_board(screen):
    global colours
    colours = [py.Color("white"), py.Color("gray")]
    for x in range(dimension):
        for y in range(dimension):
            colour = colours[((x + y) % 2)]
            py.draw.rect(screen, colour, py.Rect(y * square_size, x * square_size, square_size, square_size))


def draw_pieces(screen, board):
    for x in range(dimension):
        for y in range(dimension):
            piece = board[x][y]
            if piece != "--":
                screen.blit(chess_images[piece], py.Rect(y * square_size, x * square_size, square_size, square_size))


def animate_move(move, screen, board, click):
    global colours
    dR = move.end_row - move.start_row
    dC = move.end_col - move.start_col
    fps = 30
    frame_count = (abs(dR) + abs(dC)) * fps
    for frame in range(frame_count + 1):
        row, col = (move.start_row + dR * frame / frame_count, move.start_col + dC * frame / frame_count)
        draw_board(screen)
        draw_pieces(screen, board)
        color = colours[(move.end_row + move.end_col) % 2]
        end_square = py.Rect(move.end_col * square_size, move.end_row * square_size, square_size, square_size)
        py.draw.rect(screen, color, end_square)
        if move.pieceEnd != "--":
            screen.blit(chess_images[move.pieceEnd], end_square)
        screen.blit(chess_images[move.pieceMoved],
                    py.Rect(col * square_size, row * square_size, square_size, square_size))
        py.display.flip()
        click.tick(266)


def draw_text(screen, text):
    font = py.font.SysFont("Helvetica", 32, True, False)
    text_object = font.render(text, False, py.Color("Black"))
    textLocation = py.Rect(0, 0, width, height).move(width / 2 - text_object.get_width() / 2,
                                                     height / 2 - text_object.get_height() / 2)
    screen.blit(text_object, textLocation)
    text_object = font.render(text, False, py.Color("Gray"))
    screen.blit(text_object, textLocation.move(2, 2))


main()
