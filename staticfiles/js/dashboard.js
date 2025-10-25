document.addEventListener("DOMContentLoaded", function () {
    let chartInstances = {}; // store active charts

    // =============== Fetch Dashboard Data ===============
    function fetchDashboardData(period = "all") {
        fetch(`/dashboard-data/?period=${period}`)
            .then(response => response.json())
            .then(data => {
                // ✅ Update Smart Suggestions
                const suggestionsBox = document.getElementById("suggestions");
                if (suggestionsBox) {
                    suggestionsBox.innerHTML = "";
                    data.suggestions.forEach(s => {
                        const li = document.createElement("li");
                        li.classList.add("list-group-item");
                        li.textContent = `💡 ${s}`;
                        suggestionsBox.appendChild(li);
                    });
                }

                // ✅ Update Alerts
                const alertsBox = document.getElementById("alerts");
                if (alertsBox) {
                    alertsBox.innerHTML = "";
                    if (data.alerts.length) {
                        data.alerts.forEach(a => {
                            const li = document.createElement("li");
                            li.textContent = `🔔 ${a}`;
                            alertsBox.appendChild(li);
                        });
                    } else {
                        alertsBox.innerHTML = '<li class="text-success">No unusual activity</li>';
                    }
                }

                // ✅ Update Transactions
                const txBox = document.getElementById("recent-transactions");
                if (txBox) {
                    txBox.innerHTML = "";
                    data.transactions.forEach(t => {
                        const li = document.createElement("li");
                        li.textContent = `${t.description} — ₹${t.amount.toFixed(2)} (${t.timestamp})`;
                        txBox.appendChild(li);
                    });
                }

                // ✅ Spending Graphs
                renderLineChart("spendingChart7d", data.labels_7d, data.spending_7d, "Spending (7 days)", "rgba(255,0,0,1)");
                renderLineChart("spendingChart30d", data.labels_30d, data.spending_30d, "Spending (30 days)", "rgba(0,128,0,1)");
                renderLineChart("spendingChartAll", data.labels_all, data.spending_all, "Spending (All time)", "rgba(0,0,255,1)");

                // ✅ Fraud Amount Graphs
                renderBarChart("fraudAmountChart7d", data.labels_7d, data.fraud_7d_amount, "Fraud Amount (7 days)", "rgba(255,0,0,0.7)");
                renderBarChart("fraudAmountChart30d", data.labels_30d, data.fraud_30d_amount, "Fraud Amount (30 days)", "rgba(128,0,128,0.7)");
                renderBarChart("fraudAmountChartAll", data.labels_all, data.fraud_all_amount, "Fraud Amount (All time)", "rgba(0,128,128,0.7)");

                // ✅ Fraud Count Graphs
                renderBarChart("fraudCountChart7d", data.labels_7d, data.fraud_7d_count, "Fraud Count (7 days)", "rgba(255,69,0,0.7)");
                renderBarChart("fraudCountChart30d", data.labels_30d, data.fraud_30d_count, "Fraud Count (30 days)", "rgba(255,165,0,0.7)");
                renderBarChart("fraudCountChartAll", data.labels_all, data.fraud_all_count, "Fraud Count (All time)", "rgba(0,0,0,0.7)");
            })
            .catch(err => console.error("Error loading dashboard data:", err));
    }

    // =============== Chart Helpers ===============
    function renderLineChart(canvasId, labels, dataArr, labelName, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // destroy old chart if exists
        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
        }

        chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: labelName,
                    data: dataArr,
                    borderColor: color,
                    backgroundColor: color.replace("1)", "0.2)").replace("0.7)", "0.2)"),
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: "top" } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    function renderBarChart(canvasId, labels, dataArr, labelName, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // destroy old chart if exists
        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
        }

        chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: labelName,
                    data: dataArr,
                    backgroundColor: color
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: "top" } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    // =============== Init ===============
    fetchDashboardData("all");

    // Optional: Hook filter buttons if you have them
    const btn7 = document.getElementById("filter7");
    const btn30 = document.getElementById("filter30");
    const btnAll = document.getElementById("filterAll");

    if (btn7) btn7.addEventListener("click", () => fetchDashboardData("7"));
    if (btn30) btn30.addEventListener("click", () => fetchDashboardData("30"));
    if (btnAll) btnAll.addEventListener("click", () => fetchDashboardData("all"));
});
