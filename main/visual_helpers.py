import pygame

from visual_constants import *

def load_images():
    '''
    This function loads the chess images.
    '''

    pieces = ['wP', 'wR', 'wN', 'wB', 'wK', 'wQ', 'bP', 'bR', 'bN', 'bB', 'bK', 'bQ']
    piece_images = {}

    for piece in pieces:
        piece_images[piece] = pygame.transform.scale(pygame.image.load(IMAGE_LOCATION + piece + ".png"), (SQUARESIZE, SQUARESIZE)) # type: ignore

    return piece_images

def draw_game_state(screen, game_state, valid_moves, square_selected, piece_images: list):
    draw_board(screen)
    draw_pieces(screen, game_state.board, piece_images)
    highlight(screen, game_state, valid_moves, square_selected)


def highlight(screen, game_state, valid_moves, square_selected):
    s = pygame.Surface((SQUARESIZE, SQUARESIZE))
    s.set_alpha(50)  # transparency
    if square_selected != ():
        row, col = square_selected
        if game_state.board[row][col][0] == ("w" if game_state.white else "b"):
            s.fill(pygame.Color("blue"))
            screen.blit(s, (col * SQUARESIZE, row * SQUARESIZE))

            s.fill(pygame.Color("yellow"))
            for move in valid_moves:

                if move.start_row == row and move.start_col == col:
                    screen.blit(s, (SQUARESIZE * move.end_col, SQUARESIZE * move.end_row))

            s.fill(pygame.Color("red"))
            if game_state.square_under_attack(row, col):
                screen.blit(s, (col * SQUARESIZE, row * SQUARESIZE))


def draw_board(screen):
    global colours
    colours = [pygame.Color("white"), pygame.Color("gray")]
    for x in range(DIMENSION):
        for y in range(DIMENSION):
            colour = colours[((x + y) % 2)]
            pygame.draw.rect(screen, colour, pygame.Rect(y * SQUARESIZE, x * SQUARESIZE, SQUARESIZE, SQUARESIZE))

def draw_pieces(screen, board, chess_images: list) -> None:
    for x in range(DIMENSION):
        for y in range(DIMENSION):
            piece = board[x][y]
            if piece != "--":
                screen.blit(chess_images[piece], pygame.Rect(y * SQUARESIZE, x * SQUARESIZE, SQUARESIZE, SQUARESIZE))

def animate_move(move, screen, board, piece_images: list, click):
    global colours
    dR = move.end_row - move.start_row
    dC = move.end_col - move.start_col
    fps = 30
    frame_count = (abs(dR) + abs(dC)) * fps
    for frame in range(frame_count + 1):
        row, col = (move.start_row + dR * frame / frame_count, move.start_col + dC * frame / frame_count)
        draw_board(screen)
        draw_pieces(screen, board, piece_images)
        color = colours[(move.end_row + move.end_col) % 2]
        end_square = pygame.Rect(move.end_col * SQUARESIZE, move.end_row * SQUARESIZE, SQUARESIZE, SQUARESIZE)
        pygame.draw.rect(screen, color, end_square)
        if move.pieceEnd != "--":
            screen.blit(piece_images[move.pieceEnd], end_square)
        screen.blit(piece_images[move.pieceMoved],
                    pygame.Rect(col * SQUARESIZE, row * SQUARESIZE, SQUARESIZE, SQUARESIZE))
        pygame.display.flip()
        click.tick(266)


def draw_text(screen, text):
    font = pygame.font.SysFont("Helvetica", 32, True, False)
    text_object = font.render(text, False, pygame.Color("Black"))
    textLocation = pygame.Rect(0, 0, WIDTH, HEIGHT).move(WIDTH / 2 - text_object.get_width() / 2,
                                                     HEIGHT / 2 - text_object.get_height() / 2)
    screen.blit(text_object, textLocation)
    text_object = font.render(text, False, pygame.Color("Gray"))
    screen.blit(text_object, textLocation.move(2, 2))