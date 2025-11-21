import sys
import os
import random
import chess
import pygame
from stockfish import Stockfish

# ---------------- Paths ----------------
BASE_PATH = os.path.dirname(os.path.abspath(__file__))  # folder containing this script
ASSETS_PATH = os.path.join(BASE_PATH, "assets")
STOCKFISH_PATH = os.path.join(BASE_PATH, "stockfish", "stockfish-windows-x86-64-avx2.exe")

# ---------------- Config ----------------
pygame.init()
WIDTH = 800
HEIGHT = 800
SQUARE = WIDTH // 8
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Impossible Chess")
clock = pygame.time.Clock()

# ---------------- Load assets ----------------
board_img = pygame.transform.scale(pygame.image.load(os.path.join(ASSETS_PATH, "board.png")), (WIDTH, HEIGHT))
LOGO = pygame.image.load(os.path.join(ASSETS_PATH, "wk.png"))
pygame.display.set_icon(LOGO)

pieces = {}
piece_names = ["p", "r", "n", "b", "q", "k"]
for color in ["w", "b"]:
    for p in piece_names:
        img = pygame.image.load(os.path.join(ASSETS_PATH, f"{color}{p}.png"))
        img = pygame.transform.scale(img, (SQUARE, SQUARE))
        pieces[color + p] = img

# ---------------- Chess logic ----------------
board = chess.Board()
stockfish = Stockfish(STOCKFISH_PATH)

# ---------------- Game state ----------------
dragging = False
drag_piece = None
drag_origin = None
drag_pos = (0, 0)
legal_moves_for_piece = []

status_message = ""
played_check_sound = False

font = pygame.font.SysFont("arial", 56, bold=True)
small_font = pygame.font.SysFont("arial", 20)

# AI non-blocking delay
ai_thinking = False
ai_start_time = 0
ai_delay = 0  # in milliseconds

# ---------------- Sound effects ----------------
pygame.mixer.init()
sounds = {
    "move": pygame.mixer.Sound(os.path.join(ASSETS_PATH, "move.mp3")),
    "ai_move": pygame.mixer.Sound(os.path.join(ASSETS_PATH, "move.mp3")),
    "capture": pygame.mixer.Sound(os.path.join(ASSETS_PATH, "attack.mp3")),
    "check": pygame.mixer.Sound(os.path.join(ASSETS_PATH, "check.mp3")),
}

# ---------------- Helper functions ----------------
def clamp_square_indices(file, rank):
    file = max(0, min(7, file))
    rank = max(0, min(7, rank))
    return file, rank

def get_square_from_mouse(pos):
    x, y = pos
    file = x // SQUARE
    rank = 7 - (y // SQUARE)
    file, rank = clamp_square_indices(file, rank)
    return chess.square(file, rank)

def draw_text_centered(text):
    if not text:
        return
    outline = font.render(text, True, (0, 0, 0))
    msg = font.render(text, True, (255, 255, 255))
    x = WIDTH // 2 - msg.get_width() // 2
    y = HEIGHT // 2 - msg.get_height() // 2
    for dx, dy in ((2,0), (-2,0), (0,2), (0,-2)):
        screen.blit(outline, (x+dx, y+dy))
    screen.blit(msg, (x, y))

def is_game_over():
    return board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition()

def update_game_state():
    global status_message, played_check_sound

    # Reset check flag if not in check
    if not board.is_check():
        played_check_sound = False

    if board.is_checkmate():
        status_message = "YOU LOSE" if board.turn else "YOU WIN"
        return
    if board.is_stalemate():
        status_message = "STALEMATE"
        return
    if board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        status_message = "DRAW"
        return
    if board.is_check():
        status_message = "CHECK!"
        if not played_check_sound:
            sounds["check"].play()
            played_check_sound = True
        return
    status_message = ""

def draw_board():
    screen.blit(board_img, (0, 0))
    # highlight legal moves
    for sq in legal_moves_for_piece:
        file = chess.square_file(sq)
        rank = 7 - chess.square_rank(sq)
        pygame.draw.rect(screen, (0, 200, 0), pygame.Rect(file*SQUARE, rank*SQUARE, SQUARE, SQUARE), 5)

    # draw pieces
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece:
            continue
        if dragging and sq == drag_origin:
            continue
        color = "w" if piece.color else "b"
        name = piece.symbol().lower()
        img = pieces.get(color + name)
        if img:
            file = chess.square_file(sq)
            rank = 7 - chess.square_rank(sq)
            screen.blit(img, (file*SQUARE, rank*SQUARE))

    # draw dragged piece
    if dragging and drag_piece:
        color = "w" if drag_piece.color else "b"
        name = drag_piece.symbol().lower()
        img = pieces.get(color + name)
        if img:
            screen.blit(img, (drag_pos[0]-SQUARE//2, drag_pos[1]-SQUARE//2))

    # turn indicator
    turn_text = "White to move" if board.turn else "Black to move"
    screen.blit(small_font.render(turn_text, True, (255,255,255)), (8, 8))

    # status message
    draw_text_centered(status_message)

# ---------------- Main loop ----------------
running = True
while running:
    update_game_state()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # drag start
        elif event.type == pygame.MOUSEBUTTONDOWN and not is_game_over():
            sq = get_square_from_mouse(event.pos)
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn:
                dragging = True
                drag_piece = piece
                drag_origin = sq
                drag_pos = event.pos
                legal_moves_for_piece = [m.to_square for m in board.legal_moves if m.from_square==sq]

        # dragging
        elif event.type == pygame.MOUSEMOTION:
            if dragging:
                drag_pos = event.pos

        # drop
        elif event.type == pygame.MOUSEBUTTONUP and dragging:
            if not is_game_over():
                sq = get_square_from_mouse(event.pos)
                move = chess.Move(drag_origin, sq)
                if move in board.legal_moves:
                    # play sound
                    if board.is_capture(move):
                        sounds["capture"].play()
                    else:
                        sounds["move"].play()
                    # push player move
                    board.push(move)
                    update_game_state()
                    # start AI thinking (non-blocking)
                    ai_thinking = True
                    ai_start_time = pygame.time.get_ticks()
                    ai_delay = random.randint(500, 1500)  # milliseconds
            dragging = False
            drag_piece = None
            drag_origin = None
            legal_moves_for_piece = []

        # keys
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_r:
                board = chess.Board()
                status_message = ""
                dragging = False
                drag_piece = None
                drag_origin = None
                legal_moves_for_piece = []
                played_check_sound = False
                ai_thinking = False

    # AI non-blocking move
    if ai_thinking and not is_game_over():
        current_time = pygame.time.get_ticks()
        if current_time - ai_start_time >= ai_delay:
            stockfish.set_fen_position(board.fen())
            ai_move_uci = stockfish.get_best_move()
            if ai_move_uci:
                move_obj = chess.Move.from_uci(ai_move_uci)
                if move_obj in board.legal_moves:
                    if board.is_capture(move_obj):
                        sounds["capture"].play()
                    else:
                        sounds["ai_move"].play()
                    board.push(move_obj)
                    update_game_state()
            ai_thinking = False

    draw_board()
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
