def determineDeviceName(voltage, current, power):
    
    if power >= 1500 and power <= 3000 and current >= 6 and current <= 12:
        return "Air Conditioner"
    elif power >= 100 and power <= 250 and current >= 0.5 and current <= 1.5:
        return "Refrigerator"
    elif power >= 300 and power <= 800 and current >= 1.5 and current <= 4:
        return "Washing Machine"
    elif power >= 700 and power <= 1200 and current >= 3 and current <= 6:
        return "Microwave"
    elif power >= 1000 and power <= 2500 and current >= 4 and current <= 10:
        return "Water Heater"
    elif power >= 150 and power <= 300 and current >= 0.8 and current <= 2:
        return "Computer"
    elif power >= 200 and power <= 800 and current >= 1 and current <= 4:
        return "Water Pump"
    elif power >= 5 and power <= 50 and current >= 0.05 and current <= 0.5:
        return "LED Light"
    elif power >= 500 and power <= 1500 and current >= 2 and current <= 7:
        return "Electric Heater"
    elif power >= 30 and power <= 150 and current >= 0.2 and current <= 1:
        return "Television/workstation-laptop"
    elif power >= 30 and power <= 100 and current >= 0.2 and current <= 0.8:
        return "Electric Fan"
    elif power >= 500 and power <= 900 and current >= 2 and current <= 4:
        return "Coffee Maker"
    elif power >= 800 and power <= 1800 and current >= 3 and current <= 8:
        return "Iron"
    elif power >= 100 and power <= 300 and current >= 0.5 and current <= 1.5:
        return "Mixer"
    elif power >= 200 and power <= 500 and current >= 1 and current <= 2.5:
        return "Vacuum Cleaner"
    elif power >= 50 and power <= 200 and current >= 0.3 and current <= 1:
        return "Router/Wi-Fi Modem"
    elif power >= 10 and power <= 30 and current >= 0.1 and current <= 0.2:
        return "Phone Charger"
    elif power >= 20 and power <= 100 and current >= 0.1 and current <= 0.5:
        return "Laptop Charger"
    elif power >= 800 and power <= 1400 and current >= 3 and current <= 6:
        return "Blender"
    elif power >= 1000 and power <= 2000 and current >= 4 and current <= 9:
        return "Hair Dryer"
    elif power >= 5 and power <= 20 and current >= 0.02 and current <= 0.1:
        return "Night Lamp"
    elif power >= 400 and power <= 800 and current >= 2 and current <= 4:
        return "Air Fryer"
    elif power >= 200 and power <= 400 and current >= 1 and current <= 2:
        return "Gaming Console"
    elif power >= 300 and power <= 600 and current >= 1.5 and current <= 3:
        return "Electric Kettle"
    elif power >= 150 and power <= 300 and current >= 0.7 and current <= 1.5:
        return "Printer"
    elif power >= 50 and power <= 150 and current >= 0.3 and current <= 0.8:
        return "Desktop Monitor"
    elif power >= 10 and power <= 50 and current >= 0.05 and current <= 0.3:
        return "Smart Speaker"
    else:
        return "Unknown Device"
