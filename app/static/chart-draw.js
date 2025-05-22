const ctx = document.getElementById("nutritionChart").getContext("2d");
const chart = new Chart(ctx, {
    type: "bar",
    data: {
        labels: ["Calories", "Protein", "Carbs", "Fat"],
        datasets: [{
            label: "Nutrition Summary",
            data: [
                summary.calories,
                summary.protein,
                summary.carbs,
                summary.fat
            ],
            backgroundColor: [
                "rgba(255, 99, 132, 0.6)",
                "rgba(54, 162, 235, 0.6)",
                "rgba(255, 206, 86, 0.6)",
                "rgba(75, 192, 192, 0.6)"
            ],
            borderColor: "rgba(0, 0, 0, 0.1)",
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});
