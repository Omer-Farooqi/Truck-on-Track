from flask import Flask, request, jsonify, send_file, send_from_directory
import os
from truck_manager import TruckOnTrack, get_week_key

# Absolute path to the folder where app.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)

# Initialize the backend
fleet = TruckOnTrack(data_dir=os.path.join(BASE_DIR, 'data'))

# ─── Serve HTML pages ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), 'index_simple.html')

@app.route('/report')
def report():
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), 'report_full.html')

# ─── API: Trucks ───────────────────────────────────────────────────────────────

@app.route('/api/trucks', methods=['GET'])
def get_trucks():
    trucks = fleet.get_trucks()
    return jsonify({'success': True, 'trucks': trucks})

@app.route('/api/trucks', methods=['POST'])
def add_truck():
    data = request.get_json()
    truck_num = (data.get('truck_number') or '').strip()
    result = fleet.add_truck(truck_num)
    return jsonify(result), (200 if result['success'] else 400)

# ─── API: Expenses ─────────────────────────────────────────────────────────────

@app.route('/api/expenses', methods=['POST'])
def save_expenses():
    data = request.get_json()
    truck = data.get('truck', '').strip()
    week  = data.get('week', '').strip() or get_week_key()
    expenses = {
        'fuel':       str(data.get('fuel', 0)),
        'repair':     str(data.get('repair', 0)),
        'tolls':      str(data.get('tolls', 0)),
        'insurance':  str(data.get('insurance', 0)),
        'driver_pay': str(data.get('driver_pay', 0)),
        'other':      str(data.get('other', 0)),
    }
    result = fleet.enter_expenses(truck, week, expenses)
    return jsonify(result), (200 if result['success'] else 400)

# ─── API: Income ───────────────────────────────────────────────────────────────

@app.route('/api/income', methods=['POST'])
def save_income():
    data = request.get_json()
    truck  = data.get('truck', '').strip()
    week   = data.get('week', '').strip() or get_week_key()
    income = float(data.get('income', 0))
    result = fleet.enter_income(truck, week, income)
    return jsonify(result), (200 if result['success'] else 400)

# ─── API: Summary ──────────────────────────────────────────────────────────────

@app.route('/api/summary', methods=['GET'])
def get_summary():
    truck = request.args.get('truck', '').strip()
    week  = request.args.get('week', '').strip() or get_week_key()
    result = fleet.get_weekly_summary(truck, week)
    return jsonify(result), (200 if result['success'] else 400)

# ─── API: PDF Report ───────────────────────────────────────────────────────────

@app.route('/api/pdf', methods=['GET'])
def generate_pdf():
    truck = request.args.get('truck', '').strip()
    week  = request.args.get('week', '').strip() or get_week_key()
    reports_dir = os.path.join(BASE_DIR, 'reports')
    result = fleet.generate_weekly_pdf(truck, week, output_dir=reports_dir)
    if not result['success']:
        return jsonify(result), 400
    return send_file(
        result['filename'],
        as_attachment=True,
        download_name=os.path.basename(result['filename']),
        mimetype='application/pdf'
    )

# ─── API: Error / Problem Report ──────────────────────────────────────────────

@app.route('/api/report', methods=['POST'])
def submit_report():
    data  = request.get_json()
    name  = data.get('name', '').strip()
    email = data.get('email', '').strip()
    title = data.get('title', '').strip()
    desc  = data.get('description', '').strip()

    if not name or not email or not desc:
        return jsonify({'success': False, 'message': 'Name, email, and description are required.'}), 400

    trucks = fleet.get_trucks()
    truck  = trucks[0] if trucks else 'N/A'
    week   = get_week_key()
    full_desc = f"Title: {title}\n\n{desc}" if title else desc

    reports_dir = os.path.join(BASE_DIR, 'reports')
    result = fleet.generate_error_report_pdf(truck, week, name, email, full_desc, output_dir=reports_dir)
    return jsonify(result), (200 if result['success'] else 400)

# ─── Week helper ───────────────────────────────────────────────────────────────

@app.route('/api/current-week', methods=['GET'])
def current_week():
    return jsonify({'week': get_week_key()})

# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5000)
