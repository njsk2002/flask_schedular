document.addEventListener('DOMContentLoaded', function() {
    const data = JSON.parse(document.getElementById('chart-data').textContent);
    
    const labels = data.labels;
    const datasets = [
        {
            label: 'CO2 Electricity',
            data: data.co2_elec,
            borderColor: 'rgba(75, 192, 192, 1)',
            backgroundColor: 'rgba(75, 192, 192, 1)',
            fill: false
        },
        {
            label: 'CO2 Water',
            data: data.co2_water,
            borderColor: 'rgba(54, 162, 235, 1)',
            backgroundColor: 'rgba(54, 162, 235, 1)',
            fill: false
        },
        {
            label: 'CO2 Vehicle',
            data: data.co2_vehicle,
            borderColor: 'rgba(255, 99, 132, 1)',
            backgroundColor: 'rgba(255, 99, 132, 1)',
            fill: false
        },
        {
            label: 'CO2 Waste',
            data: data.co2_waste,
            borderColor: 'rgba(153, 102, 255, 1)',
            backgroundColor: 'rgba(153, 102, 255, 1)',
            fill: false
        },
        {
            label: 'CO2 Gas',
            data: data.co2_gas,
            borderColor: 'rgba(255, 159, 64, 1)',
            backgroundColor: 'rgba(255, 159, 64, 1)',
            fill: false
        }
    ];

    // Calculate "전체" (total) values and round them to 2 decimal places
    var totalData = labels.map((_, index) => {
        return datasets.reduce((sum, dataset) => sum + (dataset.data[index] || 0), 0).toFixed(2);
    });

    // Convert the rounded string values back to numbers (if needed)
    totalData = totalData.map(value => parseFloat(value));

    // Add "전체" dataset
    datasets.push({
        label: '전체',
        data: totalData,
        borderColor: '#6f42c1',
        backgroundColor: 'rgba(111, 66, 193, 0.2)',
        fill: true
    });

    // Create stacked bar chart
    var stackedBarCtx = document.getElementById('stackedBarChart');
    var stackedBarChart = new Chart(stackedBarCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets.slice(0, -1) // Exclude "전체"

        },
        options: {
            scales: {
                xAxes: [{
                    stacked: true,
                    gridLines: {
                        display: false
                    }
                }],
                yAxes: [{
                    stacked: true,
                    ticks: {
                        beginAtZero: true
                    },
                    gridLines: {
                        display: true
                    }
                }]
            },
            legend: {
                display: true
            },
            layout: {
                padding: {
                    left: 0,
                    right: 0,
                    top: 0,
                    bottom: 0
                }
            }
        }
    });

    // Create line chart
    var ctx = document.getElementById('myChart');
    var myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets.map(dataset => ({
                label: dataset.label,
                data: dataset.data,
                lineTension: 0,
                borderColor: dataset.borderColor,
                borderWidth: 2,
                pointBackgroundColor: dataset.borderColor,
                fill: dataset.fill
            }))
        },
        options: {
            scales: {
                xAxes: [{
                    gridLines: {
                        display: true
                    }
                }],
                yAxes: [{
                    gridLines: {
                        display: true
                    },
                    ticks: {
                        beginAtZero: false
                    }
                }]
            },
            legend: {
                display: true
            }
        }
    });

    // Insert table data
    var tableBody = document.getElementById('table-body');
    labels.forEach((month, index) => {
        var row = document.createElement('tr');

        var cell = document.createElement('td');
        cell.textContent = month;
        row.appendChild(cell);

        datasets.slice(0, -1).forEach(dataset => { // Exclude "전체" for table rows
            var dataCell = document.createElement('td');
            dataCell.textContent = dataset.data[index] || 0;
            row.appendChild(dataCell);
        });

        var totalCell = document.createElement('td');
        totalCell.textContent = totalData[index];
        row.appendChild(totalCell);

        tableBody.appendChild(row);
    });
});
