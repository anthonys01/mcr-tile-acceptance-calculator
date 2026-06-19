"""
    flask server
"""
from flask import Flask, request, jsonify
from flask_cors import CORS

from mcr_scorer import get_won_hand_yakus, print_yakus
from tile_acceptance_calculator import analyze_hand_from_string_and_print
from tiles_utils import parse_hand

app = Flask(__name__)
CORS(app)

@app.route('/calculate-tile-acceptance', methods=['POST'])
def calculate_tile_acceptance():
    """
    REST POST API to analyze a hand
    :return: REST response json
    """
    data = request.json
    user_hand = data.get('input')
    display_all = data.get('checkbox')

    try:
        return jsonify({'result': analyze_hand_from_string_and_print(user_hand, display_all)})
    except Exception as e: # pylint: disable=broad-exception-caught
        return jsonify({'error': str(e)}), 500

@app.route('/calculate-value', methods=['POST'])
def calculate_value():
    """
    REST POST API to analyze a hand
    :return: REST response json
    """
    data = request.json
    user_hand = data.get('input')
    self_drawn = data.get('self_drawn')
    last_tile = data.get('last_tile')
    prevalent_wind = data.get('prevalent_wind')
    seat_wind = data.get('seat_wind')

    try:
        acceptance, hand, yakus = get_won_hand_yakus(parse_hand(user_hand), self_drawn, last_tile, prevalent_wind, seat_wind)
        return jsonify({'result': print_yakus(yakus)})
    except Exception as e: # pylint: disable=broad-exception-caught
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
