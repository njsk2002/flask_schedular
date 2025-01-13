// // Conversions Chart
// var ctxConversions = document.getElementById('conversionsChart').getContext('2d');
// var conversionsChart = new Chart(ctxConversions, {
//     type: 'bar',
//     data: {
//         labels: ['Oct 1', 'Oct 2', 'Oct 3', 'Oct 4', 'Oct 5', 'Oct 6', 'Oct 7', 'Oct 8', 'Oct 9', 'Oct 10', 'Oct 11', 'Oct 12'],
//         datasets: [{
//             label: 'Conversions',
//             data: [20, 10, 30, 25, 15, 20, 18, 22, 25, 20, 18, 30],
//             backgroundColor: '#007bff'
//         }]
//     },
//     options: {
//         responsive: true,
//         maintainAspectRatio: false
//     }
// });

// Traffic Channels Chart
var ctxTraffic = document.getElementById('trafficChart').getContext('2d');
var trafficChart = new Chart(ctxTraffic, {
    type: 'doughnut',
    data: {
        labels: ['Direct', 'Organic', 'Referral'],
        datasets: [{
            label: 'Traffic Channels',
            data: [50, 30, 20],
            backgroundColor: ['#007bff', '#28a745', '#ffc107']
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});

// Sales Chart
var ctxSales = document.getElementById('salesChart').getContext('2d');
var salesChart = new Chart(ctxSales, {
    type: 'line',
    data: {
        labels: ['Oct 1', 'Oct 3', 'Oct 5', 'Oct 7', 'Oct 9', 'Oct 11', 'Oct 13', 'Oct 15', 'Oct 17', 'Oct 19', 'Oct 21', 'Oct 23', 'Oct 25', 'Oct 27', 'Oct 29'],
        datasets: [{
            label: 'Sales',
            data: [10, 15, 12, 18, 16, 22, 20, 24, 26, 28, 30, 32, 35, 37, 40],
            borderColor: '#007bff',
            fill: false
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});
