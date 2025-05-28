"""
    flask server
"""
from flask import Flask, request, jsonify
from flask_cors import CORS

from tile_acceptance_calculator import analyze_hand_from_string

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
        return jsonify({'result': analyze_hand_from_string(user_hand, display_all)})
    except Exception as e: # pylint: disable=broad-exception-caught
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
