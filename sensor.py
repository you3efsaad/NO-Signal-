from flask import Flask, render_template, jsonify, request
import sqlite3
import time

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from device_identifier import determineDeviceName
from datetime import datetime, timedelta, date

app = Flask(__name__)
DB_PATH = 'usage_hourly.db'

latest_data = {
    "voltage": 0,
    "current": 0,
    "power": 0,
    "energy": 0,
    "frequency": 0,
    "pf": 0
}

power_limit = 100
latest_command = ""


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        if data.get('sensor_status') == 'offline':
            latest_data = {
                "voltage": 0,
                "current": 0,
                "power": 0,
                "energy": 0,
                "frequency": 0,
                "pf": 0
            }
            return jsonify({"status": "sensor-offline"})

        required_fields = [
            'device', 'power', 'voltage', 'current',
            'energy_consumption', 'active_power',
            'frequency', 'power_factor', 'active_energy'
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing field: {field}', 'status': 'error'}), 400

        latest_data = {
            "voltage": float(data['voltage']),
            "current": float(data['current']),
            "power": float(data['power']),
            "energy": float(data['energy_consumption']),
            "frequency": float(data['frequency']),
            "pf": float(data['power_factor'])
        }

        return jsonify({"status": "received"})

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}", "status": "error"}), 500


@app.route('/latest')
def latest():
    return jsonify({
        **latest_data,
        "power_limit": power_limit
    })


@app.route('/historical')
def historical_data():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"message": "Start date and end date are required."}), 400

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid date format"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m-%d %H:00:00', Timestamp) AS hour,
               "Power(W)",
               "Energy Consumption(kWh)",
               "Voltage",
               "Current",
               "Active Power (kW)",
               "Frequency (Hz)",
               "Power Factor",
               "Active Energy (kWh)"
        FROM energy_usage_hourly
        WHERE Timestamp BETWEEN ? AND ?
        ORDER BY hour
    """, (start + " 00:00:00", end + " 23:59:59"))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({
            "labels": [],
            "power": [],
            "energy": [],
            "message": "No data found for selected range."
        })

    result = {
        "labels": [],
        "power": [],
        "energy": [],
        "table_data": []
    }

    for row in rows:
        hour, power, energy, voltage, current, active_power, frequency, power_factor, active_energy = row
        result["labels"].append(hour)
        result["power"].append(round(power, 2))
        result["energy"].append(round(energy, 2))
        result["table_data"].append({
            "hour": hour,
            "power": round(power, 2),
            "energy": round(energy, 2),
            "voltage": round(voltage, 2),
            "current": round(current, 2),
            "active_power": round(active_power, 2),
            "frequency": round(frequency, 2),
            "power_factor": round(power_factor, 2),
            "active_energy": round(active_energy, 2)
        })

    return jsonify(result)


@app.route('/control', methods=['POST'])
def control():
    global latest_command
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON data provided'}), 400

    command = data.get('command')
    if command in ['on', 'off']:
        latest_command = command
        return jsonify({'message': f'Command {command} received'})

    return jsonify({'message': 'Invalid command'}), 400
@app.route('/reset_command', methods=['POST'])
def reset_command():
    global latest_command
    latest_command = ""  
    return jsonify({'message': 'Command reset to empty'})

@app.route('/esp_command', methods=['GET'])
def esp_command():
    return jsonify({"command": latest_command})


@app.route('/set_limit', methods=['POST'])
def set_limit():
    global power_limit
    data = request.get_json()
    if not data or 'limit' not in data:
        return jsonify({'message': 'Invalid data'}), 400

    try:
        power_limit = float(data['limit'])
        return jsonify({'message': f'Power limit set to {power_limit}W'})
    except ValueError:
        return jsonify({'message': 'Invalid number format'}), 400


@app.route('/esp_limit', methods=['GET'])
def esp_setlimit():
    return jsonify({"power_limit": power_limit})


def save_hourly_snapshot():
    try:
        if (latest_data['voltage'] == 0 and
            latest_data['current'] == 0 and
            latest_data['power'] == 0 and
            latest_data['energy'] == 0):
            return

        voltage = float(latest_data['voltage'])
        current = float(latest_data['current'])
        power = float(latest_data['power'])
        energy = float(latest_data['energy'])

        if (voltage > 0 and current == 0) or (current > 0 and power == 0):
            print(f"Skipped saving: Invalid sensor reading. "
                  f"Readings - V: {voltage}, A: {current}, W: {power}, kWh: {energy}")
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        device_name = determineDeviceName(voltage, current, power)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO energy_usage_hourly (
                "Timestamp", "Device", "Power(W)", "Energy Consumption(kWh)", "Voltage",
                "Current", "Active Power (kW)", "Frequency (Hz)", "Power Factor", "Active Energy (kWh)"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, device_name, power, energy, voltage, current,
            power / 1000, float(latest_data['frequency']),
            float(latest_data['pf']), energy
        ))
        conn.commit()
        conn.close()

        print(f"[{timestamp}] Hourly snapshot saved for {device_name} - Power: {power}W, Current: {current}A")

    except Exception as e:
        print(f"Error saving hourly snapshot: {e}")






@app.route('/report/daily')
def daily_report():
    try:
        today = datetime.today().strftime('%Y-%m-%d')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT strftime('%H:00', Timestamp) AS hour,
                   SUM("Energy Consumption(kWh)") AS total_energy,
                   AVG("Power(W)") AS avg_power,
                   MAX("Power(W)") AS peak_power
            FROM energy_usage_hourly
            WHERE Timestamp BETWEEN ? AND ?
            GROUP BY hour
            ORDER BY hour
        """, (today + " 00:00:00", today + " 23:59:59"))
        
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"message": "No data found for today."}), 400

        total_consumption = sum(row[1] for row in rows)
        avg_consumption = total_consumption / len(rows) if rows else 0
        peak_consumption = max(row[2] for row in rows)

        labels = [row[0] for row in rows]
        data = [row[1] for row in rows]

        report_data = {
            "total_consumption": round(total_consumption, 2),
            "avg_consumption": round(avg_consumption, 2),
            "peak_consumption": round(peak_consumption, 2),
            "labels": labels,
            "data": data
        }

        return jsonify(report_data)

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/report/weekly')
def weekly_report():
    try:
        # Calculate the start and end of the week (from Monday to Sunday)
        today = datetime.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Create a list of all days of the week
        days_of_week = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date(Timestamp) AS day,
                   SUM("Energy Consumption(kWh)") AS total_energy,
                   AVG("Power(W)") AS avg_power,
                   MAX("Power(W)") AS peak_power
            FROM energy_usage_hourly
            WHERE Timestamp BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
        """, (week_start.strftime('%Y-%m-%d') + " 00:00:00", week_end.strftime('%Y-%m-%d') + " 23:59:59"))

        rows = cursor.fetchall()
        conn.close()

        # Convert the results to a dictionary for fast access by date
        data_map = {row[0]: row for row in rows}

        labels = []
        data = []
        total_consumption = 0
        avg_power_list = []
        peak_power_list = []

        for day in days_of_week:
            labels.append(day)
            if day in data_map:
                total_energy = data_map[day][1]
                avg_power = data_map[day][2]
                peak_power = data_map[day][3]
            else:
                total_energy = 0
                avg_power = 0
                peak_power = 0

            data.append(total_energy)
            total_consumption += total_energy
            avg_power_list.append(avg_power)
            peak_power_list.append(peak_power)

        avg_consumption = total_consumption / 7
        peak_consumption = max(peak_power_list)

        report_data = {
            "total_consumption": round(total_consumption, 2),
            "avg_consumption": round(avg_consumption, 2),
            "peak_consumption": round(peak_consumption, 2),
            "labels": labels,
            "data": data
        }

        return jsonify(report_data)

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/report/monthly')
def monthly_report():
    try:
        today = datetime.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(seconds=1)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT Timestamp,
                   "Energy Consumption(kWh)",
                   "Power(W)"
            FROM energy_usage_hourly
            WHERE Timestamp BETWEEN ? AND ?
        """, (month_start.strftime('%Y-%m-%d %H:%M:%S'), month_end.strftime('%Y-%m-%d %H:%M:%S')))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"message": "No data found for this month."}), 400

        weekly_data = {
            "Week 1": {"total_energy": 0, "power_list": []},
            "Week 2": {"total_energy": 0, "power_list": []},
            "Week 3": {"total_energy": 0, "power_list": []},
            "Week 4": {"total_energy": 0, "power_list": []}
        }

        for row in rows:
            timestamp = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            week_number = ((timestamp - month_start).days // 7) + 1
            week_key = f"Week {week_number}"
            if week_key in weekly_data:
                weekly_data[week_key]["total_energy"] += row[1]
                weekly_data[week_key]["power_list"].append(row[2])

        labels = []
        data = []
        all_avg_powers = []
        all_peak_powers = []

        for week in ["Week 1", "Week 2", "Week 3", "Week 4"]:
            values = weekly_data[week]
            labels.append(week)
            data.append(round(values["total_energy"], 2))
            if values["power_list"]:
                avg_power = sum(values["power_list"]) / len(values["power_list"])
                peak_power = max(values["power_list"])
            else:
                avg_power = 0
                peak_power = 0
            all_avg_powers.append(avg_power)
            all_peak_powers.append(peak_power)

        total_consumption = sum(data)
        avg_consumption = total_consumption / 4
        peak_consumption = max(all_peak_powers)

        report_data = {
            "total_consumption": round(total_consumption, 2),
            "avg_consumption": round(avg_consumption, 2),
            "peak_consumption": round(peak_consumption, 2),
            "labels": labels,
            "data": data
        }

        return jsonify(report_data)

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

timer_data = {
    "end_time": 0 
}

@app.route('/set_timer', methods=['POST'])
def set_timer():
    data = request.get_json()
    duration_minutes = data.get("duration_minutes", 0)

    if duration_minutes > 0:
        timer_data["end_time"] = int(time.time()) + duration_minutes * 60
        return jsonify({"message": "Timer set successfully", "end_time": timer_data["end_time"]}), 200
    else:
        return jsonify({"error": "Invalid duration"}), 400

@app.route('/get_timer', methods=['GET'])
def get_timer():
    current_time = int(time.time())
    remaining = timer_data["end_time"] - current_time

    if remaining > 0:
        return jsonify({"remaining_seconds": remaining})
    else:
        timer_data["end_time"] = 0
        return jsonify({"remaining_seconds": 0})


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=save_hourly_snapshot, trigger='interval', seconds=20)
    scheduler.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
