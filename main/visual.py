import pygame


import engine.chess_engine as chess_engine
import engine.chess_hash as chess_hash
import engine.chess_algorithm as chess_algorithm

from visual_helpers import *

piece_images = {}

def visualize(engine):
    '''
    This function runs the chess game.
    '''

    # initiate pygame
    pygame.init()

    # create screen
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    screen.fill(pygame.Color("white"))

    # create game state
    game_state = chess_engine.GameState()

    # load images
    piece_images = load_images()

    # load zobrist keys
    chess_hash.load_zobrist()

    if engine != "stockfish":
        chess_algorithm.import_transposition_table()

    # get valid moves
    valid_moves = game_state.get_valid_moves()

    # variables
    made_move = False
    animate = True
    game_over = False

    square_selected = ()
    player_clicks = []

    running = True

    # player_one, player_two = True, False
    player_one, player_two = True, False

    # main loop
    while running:

        # human is player one if white is playing
        human = (game_state.white and player_one) or (not game_state.white and player_two)

        # event handler
        for event in pygame.event.get():

            # event handler for quit
            if event.type == pygame.QUIT:

                # save transpositional table
                chess_hash.save_zobrist()
                chess_algorithm.export_transposition_table()

                running = False

            # event handler for mouse click (mouse button down)
            elif event.type == pygame.MOUSEBUTTONDOWN:

                # if game is not over and human is playing
                if not game_over and human:

                    # get location of mouse click
                    location = pygame.mouse.get_pos()
                    col = location[0] // SQUARESIZE
                    row = location[1] // SQUARESIZE

                    # if square is selected twice, deselect it
                    if square_selected == (row, col):
                        square_selected = ()
                        player_clicks = []
                    
                    # else select the square
                    else:
                        square_selected = (row, col)
                        player_clicks.append((row, col))

                    # if two squares are selected, make a move
                    if len(player_clicks) == 2:

                        # create move object
                        move = chess_engine.Move(player_clicks[0], player_clicks[1], game_state.board)

                        # check if move is valid
                        for x in range(len(valid_moves)):
                            if move == valid_moves[x]:
                                move = valid_moves[x]
                                game_state.make_move(move)
                                made_move = True
                                animate = True
                                square_selected = ()
                                player_clicks = []

                        # if move is not valid, select the square again
                        if not made_move:
                            player_clicks = [square_selected]

            # event handler for key press (key down)
            elif event.type == pygame.KEYDOWN:

                # event handler for undo move
                if event.key == pygame.K_z:
                    game_state.undo_move()
                    made_move = True
                    animate = False
                    game_over = False

                # event handler for reset game
                if event.key == pygame.K_r:
                    game_state = chess_engine.GameState()
                    valid_moves = game_state.get_valid_moves()
                    square_selected = ()
                    player_clicks = []
                    made_move = False
                    game_over = False
                    animate = False

        # if game is not over and human is not playing
        if not game_over and not human:

            # get best move for AI
            temp_gs = game_state
            ai_move = chess_algorithm.find_best_move(temp_gs, valid_moves, engine)
            print (ai_move)
            game_state.make_move(ai_move)
            made_move = True
            animate = True

        if made_move:
            if animate:
                animate_move(game_state.move_log[-1], screen, game_state.board, piece_images, clock) # type: ignore
            valid_moves = game_state.get_valid_moves()
            made_move = False
            animate = False

        if game_state.square_under_attack(game_state.black_king[0],game_state.black_king[1]):
            print ("Check on Black King")


        if game_state.check_mate:
            game_over = True
            if game_state.white:
                draw_text(screen, "Black wins: Checkmate")
            else:
                draw_text(screen, "White wins: Checkmate")

        if game_state.stale_mate:
            game_over = True
            draw_text(screen, "Stalemate")

        draw_game_state(screen, game_state, valid_moves, square_selected, piece_images) # type: ignore
        clock.tick(200)
        pygame.display.flip()