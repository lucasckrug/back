from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from game_model import Game
import os
import uuid

app = Flask(__name__)

CORS(app, origins="*", supports_credentials=True)

# Inicializando o SocketIO
socketio = SocketIO(app, cors_allowed_origins='*',  async_mode='gevent')

# Dicionário para armazenar as partidas ativas
games = {}  # Chave = sala_id, Valor = instância do jogo

# Evento de conexão
@socketio.on('connect')
def handle_connect():
    print("Novo cliente conectado")
    emit('connection_status', {'message': 'Conectado com sucesso'})

# Evento de desconexão
@socketio.on('disconnect')
def handle_disconnect():
    print("Cliente desconectado")
    emit('connection_status', {'message': 'Desconectado'})

@socketio.on('add_player')
def handle_add_player(data=None):
    try:
        room_id = None
        
        # Busca por uma sala existente com espaço
        for room in games:
            if len(games[room].players) < 2:
                room_id = room
                print(f"Jogador encontrado em sala existente: {room_id}")
                break
        
        # Cria uma nova sala apenas se nenhuma sala com espaço for encontrada
        if room_id is None:
            room_id = str(uuid.uuid4())  # Gera um ID único para a sala
            games[room_id] = Game()  # Cria uma nova instância do jogo para a sala
            print(f"Criando nova sala com ID: {room_id}")
        
        # Registra o jogador na sala
        player_sid = request.sid
        message, player_id = games[room_id].add_player(player_sid)  # Agora o retorno é desestruturado
        if player_id is None:
            emit('error', {'message': message})
            return
        
        print(f"Jogador {player_id + 1} se juntou à sala {room_id}")

        # Adiciona o jogador à sala do SocketIO
        join_room(room_id)

        # Emite a resposta de sucesso
        emit('player_added', {'message': message, 'player_id': player_id, 'room_id': room_id}, room=player_sid)

        # Verifica se a sala tem 2 jogadores
        if len(games[room_id].players) == 2:
            print(f"Sala {room_id} agora tem 2 jogadores. Iniciando o jogo...")
            # Inicia o jogo
            game_start_message = games[room_id].start_game()  # Chama o método para iniciar o jogo
            print(game_start_message)

            # Emite para todos na sala que o jogo começou
            emit('game_started', {'message': 'O jogo começou!'}, room=room_id)
    
    except Exception as e:
        print(f"Erro ao adicionar jogador: {str(e)}")
        emit('error', {'message': f"Erro ao adicionar jogador: {str(e)}"})



@socketio.on('start_game')
def handle_start_game(data):
    room_id = data['room_id']  # Recebe o room_id enviado pelo front-end
    game = games.get(room_id)  # Recupera a instância do jogo associada ao room_id

    if not game:
        emit('error', {'message': 'Sala não encontrada!'})
        return

    try:
        message = game.start_game()
        emit('game_started', {'message': message}, broadcast=True)
    except Exception as e:
        emit('error', {'message': f"Erro ao iniciar o jogo: {str(e)}"})


@socketio.on('place_ship')
def handle_place_ship(data):
    room_id = data['room_id']  # Certifique-se de enviar room_id no front-end
    game = games.get(room_id)  # Recupera a instância do jogo associada ao room_id

    if not game:
        emit('place_ship_response', {'message': 'Sala não encontrada!', 'success': False})
        return

    player_id = data['player_id']
    x = data['x']
    y = data['y']
    orientation = data['orientation']
    ship_name = data['shipName']
    
    # Verifica se o jogador está no jogo
    player_index = None
    for index, player in enumerate(game.players):
        if player == player_id:
            player_index = index
            break

    if player_index is None:
        # Emite a resposta de erro
        emit('place_ship_response', {'message': 'Jogador não encontrado', 'success': False})
        return

    # Coloca o navio
    result = game.place_ship(player_index, game.ships[ship_name]['size'], ship_name, x, y, orientation)

    # Se a colocação foi bem-sucedida
    if 'sucesso' in result:
        updated_board = game.boards[player_index]['board']  # Acessa o tabuleiro do jogador

        # Emite a resposta com o resultado e o tabuleiro atualizado
        emit('place_ship_response', {
            'message': result, 
            'success': True, 
            'updated_board': updated_board
        })
    else:
        # Caso contrário, emite um erro
        emit('place_ship_response', {'message': result, 'success': False})




@socketio.on('make_move')
def handle_make_move(data):
    try:
        player_id = data['player_id']
        room_id = data['room_id']  # Recebe o room_id
        x = data['x']
        y = data['y']
        
        # Certifique-se de que a sala existe antes de tentar fazer o movimento
        if room_id not in games:
            emit('error', {'message': 'Sala não encontrada!'})
            return
        
        game = games[room_id]  # Acessa o jogo pela sala
        result = game.make_move(player_id, x, y)

        emit('move_result', {
            'message': result['message'],
            'boards': result['boards'],
            'winner': result.get('winner'),
            'hit': result.get('hit'),
            'x': result.get('x'),
            'y': result.get('y'),
            'color': result.get('color')
        }, room=room_id, broadcast=True)

        # Se houver um vencedor, finalize o jogo
        if 'winner' in result:
            emit('game_over', {'winner': result['winner']}, room=room_id, broadcast=True)

    except Exception as e:
        emit('error', {'message': f"Erro ao fazer o movimento: {str(e)}"})

        
    

@socketio.on('leave_game')
def handle_leave_game(data):
    try:
        player_id = data['player_id']
        room_id = data['room_id']  # Recebe o room_id
        
        # Certifique-se de que a sala existe antes de tentar remover o jogador
        if room_id not in games:
            emit('error', {'message': 'Sala não encontrada!'})
            return
        
        game = games[room_id]  # Acessa o jogo pela sala
        message = game.remove_player(player_id)
        emit('player_left', {'message': message}, room=room_id, broadcast=True)

        # Notifica que o jogo foi reiniciado caso o jogador tenha saído
        emit('game_reset', {'message': 'O jogo foi reiniciado!'}, room=room_id, broadcast=True)

    except Exception as e:
        emit('error', {'message': f"Erro ao remover jogador: {str(e)}"})


# Rodando o servidor
if __name__ == '__main__':

    port = int(os.environ.get('PORT', 5000))
    
    # Roda o servidor Flask com o SocketIO
    socketio.run(app, host='0.0.0.0', port=port, ping_timeout=60)