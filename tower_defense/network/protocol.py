import json

DELIMITER = b'\n'


def encode_message(msg_type, data=None):
    """Encode a message as JSON bytes + newline delimiter."""
    msg = {"type": msg_type, "data": data or {}}
    return json.dumps(msg).encode('utf-8') + DELIMITER


def decode_messages(buffer):
    """
    Decode all complete messages from a byte buffer.
    Returns (list_of_messages, remaining_buffer).
    """
    messages = []
    while DELIMITER in buffer:
        line, buffer = buffer.split(DELIMITER, 1)
        try:
            msg = json.loads(line.decode('utf-8'))
            messages.append(msg)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return messages, buffer


# Message types
# Client -> Server
MSG_PLACE_TOWER = "PLACE_TOWER"
MSG_SELL_TOWER = "SELL_TOWER"
MSG_UPGRADE_TOWER = "UPGRADE_TOWER"
MSG_SEND_ENEMY = "SEND_ENEMY"
MSG_READY = "READY"
MSG_DISCONNECT = "DISCONNECT"

# Server -> Client
MSG_WELCOME = "WELCOME"           # {player_id, map_data}
MSG_PLAYER_COUNT = "PLAYER_COUNT" # {count}
MSG_GAME_START = "GAME_START"     # {}
MSG_GAME_STATE = "GAME_STATE"     # {your_state, opponent_state, wave_number, phase}
MSG_EVENT = "EVENT"               # {event, ...}
MSG_GAME_OVER = "GAME_OVER"      # {winner}
