from game_model import Game

class GameController:
    def __init__(self):
        self.game = Game()

    def add_player(self, player_id=None):
        return self.game.add_player(player_id)

    def start_game(self):
        return self.game.start_game()

    def make_move(self, player_id, x, y):
        return self.game.make_move(player_id, x, y)

    def get_game_state(self):
        return {
            'players': self.game.players,
            'boards': self.game.boards,
            'current_player': self.game.get_current_player(),
            'game_started': self.game.is_game_started()
        }

    def reset_game(self):
        self.game.reset_game()
