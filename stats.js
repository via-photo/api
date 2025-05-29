document.addEventListener('DOMContentLoaded', function() {
    const statsContent = `
    <div class="container">
        <!-- Общая статистика -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Общая статистика</h5>
            </div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-6">
                        <div class="p-3 border rounded text-center">
                            <h3 class="mb-1">1820</h3>
                            <p class="text-muted mb-0">Средние ккал/день</p>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="p-3 border rounded text-center">
                            <h3 class="mb-1">14</h3>
                            <p class="text-muted mb-0">Дней в трекере</p>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="p-3 border rounded text-center">
                            <h3 class="mb-1">82%</h3>
                            <p class="text-muted mb-0">Соблюдение нормы</p>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="p-3 border rounded text-center">
                            <h3 class="mb-1">-1.5 кг</h3>
                            <p class="text-muted mb-0">Изменение веса</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- График калорий -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Потребление калорий</h5>
            </div>
            <div class="card-body">
                <div class="text-center mb-3">
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-primary active">Неделя</button>
                        <button type="button" class="btn btn-outline-primary">Месяц</button>
                        <button type="button" class="btn btn-outline-primary">Год</button>
                    </div>
                </div>
                
                <div class="chart-container" style="position: relative; height:200px;">
                    <canvas id="caloriesChart"></canvas>
                </div>
                
                <div class="d-flex justify-content-between mt-3">
                    <small class="text-muted">23 мая</small>
                    <small class="text-muted">29 мая</small>
                </div>
            </div>
        </div>

        <!-- Распределение БЖУ -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Распределение БЖУ</h5>
            </div>
            <div class="card-body">
                <div class="chart-container" style="position: relative; height:200px;">
                    <canvas id="macroChart"></canvas>
                </div>
                
                <div class="row g-2 mt-3">
                    <div class="col-4">
                        <div class="p-2 border rounded text-center">
                            <h5 class="mb-0">25%</h5>
                            <small class="text-muted">Белки</small>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="p-2 border rounded text-center">
                            <h5 class="mb-0">30%</h5>
                            <small class="text-muted">Жиры</small>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="p-2 border rounded text-center">
                            <h5 class="mb-0">45%</h5>
                            <small class="text-muted">Углеводы</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Топ продуктов -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Часто употребляемые продукты</h5>
            </div>
            <div class="card-body">
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>Куриная грудка</span>
                        <span class="badge bg-primary rounded-pill">12 раз</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>Гречка</span>
                        <span class="badge bg-primary rounded-pill">9 раз</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>Творог</span>
                        <span class="badge bg-primary rounded-pill">8 раз</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>Яблоки</span>
                        <span class="badge bg-primary rounded-pill">7 раз</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>Овсянка</span>
                        <span class="badge bg-primary rounded-pill">6 раз</span>
                    </li>
                </ul>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // График калорий
        const caloriesCtx = document.getElementById('caloriesChart').getContext('2d');
        const caloriesChart = new Chart(caloriesCtx, {
            type: 'bar',
            data: {
                labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                datasets: [{
                    label: 'Калории',
                    data: [1750, 1820, 1650, 1920, 1780, 2100, 1850],
                    backgroundColor: '#4d6073',
                    borderRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            font: {
                                size: 10
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                size: 10
                            }
                        }
                    }
                }
            }
        });

        // График БЖУ
        const macroCtx = document.getElementById('macroChart').getContext('2d');
        const macroChart = new Chart(macroCtx, {
            type: 'doughnut',
            data: {
                labels: ['Белки', 'Жиры', 'Углеводы'],
                datasets: [{
                    data: [25, 30, 45],
                    backgroundColor: [
                        '#4d6073',
                        '#6c8fb3',
                        '#9db5cd'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            font: {
                                size: 12
                            }
                        }
                    }
                },
                cutout: '70%'
            }
        });
    </script>
    `;
    
    document.getElementById('stats-content').innerHTML = statsContent;
});
