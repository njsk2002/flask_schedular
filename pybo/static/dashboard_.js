/* globals Chart:false, feather:false */

(function () {
  'use strict'

  feather.replace({ 'aria-hidden': 'true' })

  // 차트 데이터 설정
  var labels = [
    '1월', '2월', '3월', '4월', '5월', '6월',
    '7월', '8월', '9월', '10월', '11월', '12월'
  ];

  var datasets = [
    {
      label: '전기',
      data: [1585.858, 1135.487, 1029.827, 576.589, 544.078, 988.233, 0, 0, 0, 0, 0, 0],
      borderColor: '#007bff',
      backgroundColor: '#007bff',
      fill: true
    },
    {
      label: '수도',
      data: [0.234, 0, 0, 0.234, 0.468, 0.468, 0, 0, 0, 0, 0, 0],
      borderColor: '#17a2b8',
      backgroundColor: '#17a2b8',
      fill: true
    },
    {
      label: '폐기물',
      data: [0,0,0,0,0,0,0,0,0,0,0,0],
      borderColor: '#ffc107',
      backgroundColor: '#ffc107',
      fill: true
    },
    {
      label: '교통',
      data: [47.098, 20.69, 22.372, 70.311, 14.634, 17.998, 80.74, 0, 0, 0, 0, 0],
      borderColor: '#dc3545',
      backgroundColor: '#dc3545',
      fill: true
    },
    {
      label: '제조가스',
      data: [0,0,0,0,0,0,0,0,0,0,0,0],
      borderColor: '#28a745',
      backgroundColor: '#28a745',
      fill: true
    }
  ];

  // "전체" 값 계산
  var totalData = labels.map((_, index) => {
    return datasets.reduce((sum, dataset) => sum + dataset.data[index], 0);
  });

  // "전체" 데이터셋 추가
  datasets.push({
    label: '전체',
    data: totalData,
    borderColor: '#6f42c1',
    backgroundColor: '#6f42c1',
    fill: true
  });

  // 스택된 막대 그래프 생성
  var stackedBarCtx = document.getElementById('stackedBarChart');
  var stackedBarChart = new Chart(stackedBarCtx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: datasets.slice(0, -1) // "전체" 제외
    },
    options: {
      scales: {
        xAxes: [{
          stacked: true, // x축 스택 적용
          gridLines: {
            display: false
          }
        }],
        yAxes: [{
          stacked: true, // y축 스택 적용
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
      },
      backgroundColor: 'white'
    }
  });

   // 라인 차트 생성
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
             display: true // X축의 그리드 라인 숨기기
           }
         }],
         yAxes: [{
           gridLines: {
             display: true // Y축의 그리드 라인 숨기기
           },
           ticks: {
             beginAtZero: false
           }
         }]
       },
       legend: {
         display: true
       },
       backgroundColor: 'white'
     }
   });

  // 테이블 데이터 삽입
  var tableBody = document.getElementById('table-body');
  labels.forEach((month, index) => {
    var row = document.createElement('tr');

    // 년월 추가
    var cell = document.createElement('td');
    cell.textContent = '2024/' + (index + 1).toString().padStart(2, '0');
    row.appendChild(cell);

    // 각 데이터셋 값 추가
    datasets.slice(0, -1).forEach(dataset => { // "전체" 제외
      var dataCell = document.createElement('td');
      dataCell.textContent = dataset.data[index];
      row.appendChild(dataCell);
    });

    // "전체" 추가
    var totalCell = document.createElement('td');
    totalCell.textContent = totalData[index];
    row.appendChild(totalCell);

    tableBody.appendChild(row);
  });

})();
