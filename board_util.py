"""
board_util.py
Utility functions for Go board.
"""

import numpy as np
import signal
import time
import random
# from gtp_connection import move_to_coord, format_point

"""
Encoding of colors on and off a Go board.
FLODDFILL is used internally for a temporary marker
"""
EMPTY = 0
BLACK = 1
WHITE = 2
BORDER = 3

"""
Infinity value for alpha veta
"""
INFINITY = 1000000

def is_black_white(color):
    return color == BLACK or color == WHITE
"""
Encoding of special pass move
"""
PASS = None

"""
Encoding of "not a real point", used as a marker
"""
NULLPOINT = 0

"""
The largest board we allow. 
To support larger boards the coordinate printing needs to be changed.
"""
MAXSIZE = 25

"""
where1d: Helper function for using np.where with 1-d arrays.
The result of np.where is a tuple which contains the indices 
of elements that fulfill the condition.
For 1-d arrays, this is a singleton tuple.
The [0] indexing is needed toextract the result from the singleton tuple.
"""
def where1d(condition):
    return np.where(condition)[0]

def coord_to_point(row, col, boardsize):
    """
    Transform two dimensional (row, col) representation to array index.

    Arguments
    ---------
    row, col: int
             coordinates of the point  1 <= row, col <= size

    Returns
    -------
    point
    
    Map (row, col) coordinates to array index
    Below is an example of numbering points on a 3x3 board.
    Spaces are added for illustration to separate board points 
    from BORDER points.
    There is a one point BORDER between consecutive rows (e.g. point 12).
    
    16   17 18 19   20

    12   13 14 15
    08   09 10 11
    04   05 06 07

    00   01 02 03

    File board_util.py defines the mapping of colors to integers,
    such as EMPTY = 0, BORDER = 3.
    For example, the empty 3x3 board is encoded like this:

    3  3  3  3  3
    3  0  0  0
    3  0  0  0
    3  0  0  0
    3  3  3  3

    This board is represented by the array
    [3,3,3,3,  3,0,0,0,  3,0,0,0,  3,0,0,0,  3,3,3,3,3]
    """
    assert 1 <= row
    assert row <= boardsize
    assert 1 <= col
    assert col <= boardsize
    NS = boardsize + 1
    return NS * row + col

def point_to_coord(point, boardsize):
    """
    Transform point given as board array index 
    to (row, col) coordinate representation.
    Special case: PASS is not transformed
    """
    if point == PASS:
        return PASS
    else:
        NS = boardsize + 1
        return divmod(point, NS)

def format_point(move):
    """
    Return move coordinates as a string such as 'a1', or 'pass'.
    """
    column_letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    #column_letters = "abcdefghjklmnopqrstuvwxyz"
    if move == PASS:
        return "pass"
    row, col = move
    if not 0 <= row < MAXSIZE or not 0 <= col < MAXSIZE:
        raise ValueError
    return column_letters[col - 1]+ str(row)

class TranspositionTable(object):
# Table is stored in a dictionary, with board code as key, 
# and minimax score as the value
#taken from cmput 455 sample code by Martin Mueller

    # Empty dictionary
    def __init__(self, size):
        self.table = {}
        self.zobrist = [[[random.randint(1,2**32 - 1) for i in range(2)]for j in range(size)]for k in range(size)]

    # Used to print the whole table with print(tt)
    def __repr__(self):
        return self.table.__repr__()
        
    def store(self, code, score):
        self.table[code] = score
        return score
    
    # Python dictionary returns 'None' if key not found by get()
    def lookup(self, code):
        return self.table.get(code)
    
    def index(self, player):
        ''' maps players to a number '''
        if player == BLACK:
            return 0
        elif player == WHITE:
            return 1
        else:
            return -1

    def getCode(self, board):
        hash = 0
        twoD_board = GoBoardUtil.get_twoD_board(board)
        for i in range (board.size):
            for j in range(board.size):
                if twoD_board[i][j] != 0:
                    player = self.index(twoD_board[i][j])
                    hash ^= self.zobrist[i][j][player]
        return hash
            
class GoBoardUtil(object):
    
    @staticmethod
    def generate_legal_moves(board, color):
        """
        generate a list of all legal moves on the board.
        Does not include the Pass move.

        Arguments
        ---------
        board : np.array
            a SIZExSIZE array representing the board
        color : {'b','w'}
            the color to generate the move for.
        """
        moves = board.get_empty_points()
        legal_moves = []
        for move in moves:
            if board.is_legal(move, color):
                legal_moves.append(move)
        return legal_moves

    @staticmethod       
    def generate_random_move(board, color, use_eye_filter):
        """
        Generate a random move.
        Return PASS if no move found

        Arguments
        ---------
        board : np.array
            a 1-d array representing the board
        color : BLACK, WHITE
            the color to generate the move for.
        """
        moves = board.get_empty_points()
        np.random.shuffle(moves)
        for move in moves:
            legal = not (use_eye_filter and board.is_eye(move, color)) \
                    and board.is_legal(move, color)
            if legal:
                return move
        return PASS

    @staticmethod
    def opponent(color):
        return WHITE + BLACK - color    

    @staticmethod
    def get_twoD_board(goboard):
        """
        Return: numpy array
        a two dimensional numpy array with the stones as the goboard.
        Does not pad with BORDER
        Rows 1..size of goboard are copied into rows 0..size - 1 of board2d
        """
        size = goboard.size
        board2d = np.zeros((size, size), dtype = np.int32)
        for row in range(size):
            start = goboard.row_start(row + 1)
            board2d[row, :] = goboard.board[start : start + size]
        return board2d

    @staticmethod
    def simulate(board, color, alpha, beta):

        code = board.tt.getCode(board)
        tt_lookup = board.tt.lookup(code)
        if tt_lookup:
            # print(tt_lookup)
            return tt_lookup
        endgame_query_result = board.evaluate_endgame()
        if (endgame_query_result != EMPTY):
            code = board.tt.getCode(board)
            value = 1 if endgame_query_result == color else -1
            return board.tt.store(code, value)
        legal_moves = GoBoardUtil.generate_legal_moves(board, color)
        opponent = GoBoardUtil.opponent(color)
        for move in legal_moves:
            board.play_move(move, color)
            value = -GoBoardUtil.simulate(board, opponent, -beta, -alpha)
            board.tt.store(code, value)
            if ( value > alpha and value > 0):
                alpha = value
            board.undoLastMove()
            if ( value >= beta ):
                return beta
        return alpha
