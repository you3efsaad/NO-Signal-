function updateData() {
    fetch('/latest')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            document.getElementById('voltage').innerHTML = data.voltage + '<span class="unit">V</span>';
            document.getElementById('current').innerHTML = data.current + '<span class="unit">A</span>';
            document.getElementById('power').innerHTML = data.power + '<span class="unit">W</span>';
            document.getElementById('energy').innerHTML = data.energy + '<span class="unit">kWh</span>';
            document.getElementById('frequency').innerHTML = data.frequency + '<span class="unit">Hz</span>';
            document.getElementById('pf').innerHTML = data.pf;
            const now = new Date();
            const formattedTime = now.toLocaleTimeString('en-US');
            document.getElementById('update-time').innerText = formattedTime;
            let alertShown = false;

            if (data.power > data.power_limit && !alertShown) {
                document.getElementById("alert").style.display = "block";
                alertShown = true;
            } else if (data.power <= data.power_limit) {
                document.getElementById("alert").style.display = "none";
                alertShown = false;
            }



        })
        .catch(error => {
            console.error('Error fetching data:', error);
            alert('Error fetching data, please check the connection.');
        });
}
setInterval(updateData, 2000);
window.onload = updateData;

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input[type='date']").forEach(input => {
        input.setAttribute("lang", "en");
    });
});

function renderChart(canvasId, label, data, color) {
    const canvas = document.getElementById(canvasId);
    if (canvas.chartInstance) {
        canvas.chartInstance.destroy();
    }

    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: label,
                data: data.values,
                borderColor: color,
                fill: false
            }]
        }
    });

    canvas.chartInstance = chart;
}

function updateChart(data) {
    renderChart('powerChart', 'Power (W)', { labels: data.labels, values: data.power }, 'rgba(255, 159, 64, 1)');
    renderChart('energyChart', 'Energy (kWh)', { labels: data.labels, values: data.energy }, 'rgba(75, 192, 192, 1)');
}

function updateTable(tableData) {
    const tableBody = document.getElementById("dataBody");
    tableBody.innerHTML = "";
    tableData.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${item.Timestamp}</td>
            <td>${item.device}</td>
            <td>${item.power}</td>
            <td>${item.energy}</td>
            <td>${item.voltage}</td>
            <td>${item.current}</td>
            <td>${item.active_power}</td>
            <td>${item.frequency}</td>
            <td>${item.pf}</td>
            <td>${item.active_energy}</td>
        `;
        tableBody.appendChild(row);
    });
}
function sendCommand(cmd) {
    fetch('/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
    })
        .then(res => res.json())
        .then(data => {
            console.log("Command sent:", cmd);
            updateButtons(cmd);
        })
        .catch(error => {
            console.error('Error sending command:', error);
        });
}
function resetCommand() {
    fetch('/reset_command', {
        method: 'POST'
    })
        .then(res => res.json())
}

function updateButtons(active) {
    const onBtn = document.getElementById('onBtn');
    const offBtn = document.getElementById('offBtn');

    if (active === 'on') {
        onBtn.style.backgroundColor = 'green';
        onBtn.style.color = 'white';

        offBtn.style.backgroundColor = 'lightgray';
        offBtn.style.color = 'black';
    } else if (active === 'off') {
        offBtn.style.backgroundColor = 'red';
        offBtn.style.color = 'white';

        onBtn.style.backgroundColor = 'lightgray';
        onBtn.style.color = 'black';
    }
}


document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('dateForm').addEventListener('submit', event => {
        event.preventDefault();

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (!startDate || !endDate) {
            alert('Please select both start and end dates.');
            return;
        }

        fetch(`/historical?start=${startDate}&end=${endDate}`)
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    alert(data.message);
                } else {
                    updateChart(data);
                    updateTable(data.table_data);
                }
            })
            .catch(error => {
                console.error('Error fetching historical data:', error);
                alert('Error fetching historical data.');
            });
        document.getElementById("resultsSection").style.display = "block";

        document.getElementById("resultsSection").scrollIntoView({ behavior: 'smooth' });
    });
});
function submitPowerLimit() {
    const input = document.getElementById('powerLimitInput');
    const powerLimit = parseFloat(input.value);

    if (isNaN(powerLimit)) {
        alert("Please enter a valid number.");
        return;
    }

    fetch('/set_limit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: powerLimit })  // <-- هنا استخدم "limit"
    })
        .then(res => res.json())
        .then(data => {
            console.log("Power limit sent:", powerLimit);
        })
        .catch(error => {
            console.error('Error sending power limit:', error);
        });
}
window.addEventListener('DOMContentLoaded', function () {

    const ctx = document.getElementById('liveChart').getContext('2d');
    const labels = ['Voltage (V)', 'Current (A)', 'Power (W)', 'Energy (kWh)', 'Frequency (Hz)', 'Power Factor'];

    const liveChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Live Data',
                data: [0, 0, 0, 0, 0, 0],
                borderColor: 'blue',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                tension: 0.3,
                borderWidth: 2
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    function updateLiveChart() {
        fetch('/latest')
            .then(response => response.json())
            .then(data => {
                liveChart.data.datasets[0].data = [
                    parseFloat(data.voltage || 0),
                    parseFloat(data.current || 0),
                    parseFloat(data.power || 0),
                    parseFloat(data.energy || 0),
                    parseFloat(data.frequency || 0),
                    parseFloat(data.pf || 0)
                ];
                liveChart.update();

            })
            .catch(error => console.error('Error fetching latest data:', error));
    }

    setInterval(updateLiveChart, 2000);
    updateLiveChart();
});
window.addEventListener('DOMContentLoaded', function () {

    function fetchPowerLimit() {
        fetch('/esp_limit')
            .then(res => res.json())
            .then(data => {
                if ('power_limit' in data) {
                    document.getElementById('ww').innerText = `${data.power_limit} W`;
                } else {
                    document.getElementById('ww').innerText = '--';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('ww').innerText = '--';
            });
    }

    window.addEventListener('DOMContentLoaded', fetchPowerLimit);

    setInterval(fetchPowerLimit, 2000);
});

// ###########################reports

function generateReport(reportType) {
    const url = `/report/${reportType}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                alert(data.message);
            } else {
                displayReport(data, reportType);
            }
        })
        .catch(error => console.error('Error fetching report:', error));
}
let reportChartInstance = null;

function displayReport(data, reportType) {
    document.getElementById("reportContainer").style.display = "block";

    let reportTitle = "";
    switch (reportType) {
        case 'daily':
            reportTitle = "Daily Report";
            break;
        case 'weekly':
            reportTitle = "Weekly Report";
            break;
        case 'monthly':
            reportTitle = "Monthly Report";
            break;
    }

    document.getElementById("reportTitle").textContent = reportTitle;
    document.getElementById("reportPeriod").textContent = `From ${data.labels[0]} to ${data.labels[data.labels.length - 1]}`;

    document.getElementById("totalConsumption").textContent = `${data.total_consumption} kWh`;
    document.getElementById("avgConsumption").textContent = `${data.avg_consumption} kWh`;
    document.getElementById("peakConsumption").textContent = `${data.peak_consumption} kWh`;

    if (reportChartInstance !== null) {
        reportChartInstance.destroy();
    }

    const ctx = document.getElementById("reportChart").getContext('2d');
    reportChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Energy Consumption (kWh)',
                data: data.data,
                backgroundColor: '#4CAF50',
                borderColor: '#388E3C',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                x: {
                    title: {
                        display: true,
                        text: reportType === 'monthly'
                            ? ` ${new Date().toLocaleString('en-US', { month: 'long' })}`
                            : 'Time'
                    }
                },

                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Energy Consumption (kWh)'
                    }
                }
            }
        }
    });
}
let countdownInterval;

function startTimer() {
    const minutes = document.getElementById("durationInput").value;
    if (!minutes || minutes <= 0) {
        alert("Enter minutes ");
        return;
    }

    document.querySelector("button").disabled = true;

    fetch('/set_timer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_minutes: parseInt(minutes) })
    })
        .then(res => res.text())
        .then(response => {
            console.log(response);
            startCountdown(minutes * 60);
        })
        .catch(err => {
            console.error("Erorr", err);
            document.querySelector("button").disabled = false;
        });
}

function startCountdown(seconds) {
    clearInterval(countdownInterval);

    countdownInterval = setInterval(() => {
        let mins = Math.floor(seconds / 60);
        let secs = seconds % 60;
        document.getElementById("timer").textContent =
            `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        if (seconds <= 0) {
            clearInterval(countdownInterval);
            document.getElementById("timer").textContent = "Finished Timer  ";

            setTimeout(() => {
                document.getElementById("timer").textContent = "--:--";
                document.getElementById("durationInput").value = "";
                document.querySelector("button").disabled = false;
            }, 2000);


            return;
        }

        seconds--;
    }, 1000);
}

