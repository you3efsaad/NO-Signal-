from flask import Flask, render_template, jsonify, request
import time
from datetime import datetime, timedelta
from collections import defaultdict

from dateutil import parser

from apscheduler.schedulers.background import BackgroundScheduler
from device_identifier import determineDeviceName
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)



app = Flask(__name__)

latest_data = {
    "voltage": 0,
    "current": 0,
    "power": 0,
    "energy": 0,
    "frequency": 0,
    "pf": 0
}

# import random

# while True:
#     latest_data = {
#         "voltage": round(random.uniform(210, 240), 2),     # Volts
#         "current": round(random.uniform(0, 30), 2),         # Amps
#         "power": round(random.uniform(0, 90), 2),         # Watts
#         "energy": round(random.uniform(0, 100), 2),         # kWh
#         "frequency": round(random.uniform(49.5, 50.5), 2),  # Hz
#         "pf": round(random.uniform(0.5, 1.0), 2)            # Power factor
#     }
#     time.sleep(2)
#     break



power_limit = 100
latest_command = ""

# Timer data storage
timer_data = {"end_time": 0}


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

    # Supabase expects ISO 8601 timestamps, and we want full-day range
    start_iso = start + "T00:00:00"
    end_iso = end + "T23:59:59"

    try:
        response = supabase.table("energy_usage_hourly") \
            .select("*") \
            .gte("Timestamp", start_iso) \
            .lte("Timestamp", end_iso) \
            .order("Timestamp", desc=False) \
            .execute()

        rows = response.data

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
            hour = parser.isoparse(row["Timestamp"]).strftime("%Y-%m-%d %H:00:00")
            power = round(row["Power(W)"], 2)
            energy = round(row["Energy Consumption(kWh)"], 2)
            voltage = round(row["Voltage"], 2)
            current = round(row["Current"], 2)
            active_power = round(row["Active Power (kW)"], 2)
            frequency = round(row["Frequency (Hz)"], 2)
            power_factor = round(row["Power Factor"], 2)
            active_energy = round(row["Active Energy (kWh)"], 2)

            result["labels"].append(hour)
            result["power"].append(power)
            result["energy"].append(energy)
            result["table_data"].append({
                "hour": hour,
                "power": power,
                "energy": energy,
                "voltage": voltage,
                "current": current,
                "active_power": active_power,
                "frequency": frequency,
                "power_factor": power_factor,
                "active_energy": active_energy
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"message": f"Supabase error: {str(e)}"}), 500
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

        timestamp = datetime.now().isoformat()
        device_name = determineDeviceName(voltage, current, power)

        data = {
            "Timestamp": timestamp,
            "Device": device_name,
            "Power(W)": power,
            "Energy Consumption(kWh)": energy,
            "Voltage": voltage,
            "Current": current,
            "Active Power (kW)": power / 1000,
            "Frequency (Hz)": float(latest_data['frequency']),
            "Power Factor": float(latest_data['pf']),
            "Active Energy (kWh)": energy
        }

        response = supabase.table("energy_usage_hourly").insert(data).execute()

        if response.error is None:
            print(f"[{timestamp}] Hourly snapshot saved for {device_name} - Power: {power}W, Current: {current}A")
        else:
            print(f"❌ Failed to save to Supabase: {response.error}")

    except Exception as e:
        print(f"❌ Error saving hourly snapshot: {e}")





@app.route('/report/daily')
def daily_report():
    try:
        today = datetime.today().strftime('%Y-%m-%d')
        start_iso = today + "T00:00:00"
        end_iso = today + "T23:59:59"

        # جلب البيانات من supabase خلال اليوم
        response = supabase.table("energy_usage_hourly") \
        .select('"Timestamp", "Power(W)", "Energy Consumption(kWh)"') \
        .gte("Timestamp", start_iso) \
        .lte("Timestamp", end_iso) \
        .order("Timestamp") \
        .execute()



        rows = response.data

        if not rows:
            return jsonify({"message": "No data found for today."}), 400

        # تجميع البيانات حسب الساعة
        from collections import defaultdict
        hourly_data = defaultdict(list)

        for row in rows:

            timestamp = parser.isoparse(row["Timestamp"])
            hour_str = timestamp.strftime("%H:00")

            energy = float(row["Energy Consumption(kWh)"])
            power = float(row["Power(W)"])

            hourly_data[hour_str].append({
                "energy": energy,
                "power": power
            })

        labels = []
        data = []
        all_avg_powers = []

        for hour in sorted(hourly_data.keys()):
            entries = hourly_data[hour]
            total_energy = sum(e["energy"] for e in entries)
            avg_power = sum(e["power"] for e in entries) / len(entries)
            peak_power = max(e["power"] for e in entries)

            labels.append(hour)
            data.append(round(total_energy, 2))
            all_avg_powers.append(avg_power)

        total_consumption = sum(data)
        avg_consumption = total_consumption / len(data)
        peak_consumption = max(all_avg_powers)

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
        today = datetime.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        start_of_week = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = week_end.replace(hour=23, minute=59, second=59, microsecond=0)

        start_iso = start_of_week.isoformat() + "+00:00"
        end_iso = end_of_week.isoformat() + "+00:00"


        # Fetch from Supabase
        response = supabase.table("energy_usage_hourly") \
            .select('"Timestamp", "Power(W)", "Energy Consumption(kWh)"') \
            .gte("Timestamp", start_iso) \
            .lte("Timestamp", end_iso) \
            .order("Timestamp") \
            .execute()

        rows = response.data

        if not rows:
            return jsonify({"message": "No data found for this week."}), 400

        # Prepare days of the week
        days_of_week = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        daily_data = defaultdict(list)

        for row in rows:
            ts = parser.isoparse(row["Timestamp"])  # ✅ يعالج +00:00 تلقائيًا
            day_str = ts.strftime('%Y-%m-%d')
            daily_data[day_str].append({
                "energy": float(row["Energy Consumption(kWh)"]),
                "power": float(row["Power(W)"])
            })

        labels = []
        data = []
        total_consumption = 0
        avg_power_list = []
        peak_power_list = []

        for day in days_of_week:
            labels.append(day)
            entries = daily_data.get(day, [])
            if entries:
                total_energy = sum(e["energy"] for e in entries)
                avg_power = sum(e["power"] for e in entries) / len(entries)
                peak_power = max(e["power"] for e in entries)
            else:
                total_energy = 0
                avg_power = 0
                peak_power = 0

            data.append(round(total_energy, 2))
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

        # استخدم isoformat() لإخراج "YYYY-MM-DDTHH:MM:SS"
        start_iso = month_start.isoformat()      # e.g. "2025-06-01T00:00:00"
        end_iso   = month_end.isoformat() + "+00:00"  # e.g. "2025-06-30T23:59:59+00:00"

        response = supabase.table("energy_usage_hourly") \
            .select('"Timestamp", "Power(W)", "Energy Consumption(kWh)"') \
            .gte("Timestamp", start_iso) \
            .lte("Timestamp", end_iso) \
            .order("Timestamp", desc=False) \
            .execute()

        rows = response.data
        if not rows:
            return jsonify({"message": "No data found for this month."}), 400

        # جمع البيانات أسبوعيًا
        weekly_data = {
            "Week 1": {"total_energy": 0, "power_list": []},
            "Week 2": {"total_energy": 0, "power_list": []},
            "Week 3": {"total_energy": 0, "power_list": []},
            "Week 4": {"total_energy": 0, "power_list": []}
        }

        for row in rows:
            # حل مشكلة الـ timezone باستخدام parser
            dt = parser.isoparse(row["Timestamp"])
            # احسب رقم الأسبوع داخل الشهر
            week_number = ((dt.day - 1) // 7) + 1
            week_key = f"Week {week_number}"

            energy = float(row["Energy Consumption(kWh)"])
            power  = float(row["Power(W)"])

            weekly_data[week_key]["total_energy"] += energy
            weekly_data[week_key]["power_list"].append(power)

        # تجهيز المخرجات
        labels = []
        data   = []
        all_avg_powers = []
        all_peak_powers = []

        for week in ["Week 1", "Week 2", "Week 3", "Week 4"]:
            wd = weekly_data[week]
            labels.append(week)
            data.append(round(wd["total_energy"], 2))

            if wd["power_list"]:
                avg_power  = sum(wd["power_list"]) / len(wd["power_list"])
                peak_power = max(wd["power_list"])
            else:
                avg_power  = 0
                peak_power = 0

            all_avg_powers.append(avg_power)
            all_peak_powers.append(peak_power)

        report_data = {
            "total_consumption": round(sum(data), 2),
            "avg_consumption":   round(sum(data) / 4, 2),
            "peak_consumption":  round(max(all_peak_powers), 2),
            "labels": labels,
            "data":   data
        }

        return jsonify(report_data)

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


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
