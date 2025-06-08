/**
 * Модуль для работы с разделом "Статистика"
 * Отображает статистику питания пользователя, включая итоги дня, распределение БЖУ и топ продуктов
 */

// Инициализация раздела статистики
function initStatsSection() {
    console.log('Инициализация раздела статистики');
    
    // Получаем userId
    const userId = getUserId();
    if (!userId) {
        showStatsError('Не удалось определить ID пользователя');
        return;
    }
    
    // Загружаем данные статистики
    loadStatsData(userId);
}

// Загрузка данных статистики
async function loadStatsData(userId) {
    try {
        const statsContent = document.getElementById('stats-content');
        statsContent.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mt-2">Загрузка статистики...</p>
            </div>
        `;
        
        // Получаем данные статистики через API
        const statsData = await apiClient.getStats(userId);
        
        // Получаем данные дневника для итогов дня
        const diaryData = await apiClient.getDiary(userId);
        
        // Отображаем данные
        renderStatsData(statsData, diaryData);
    } catch (error) {
        console.error('Ошибка при загрузке данных статистики:', error);
        showStatsError('Не удалось загрузить данные статистики. Пожалуйста, попробуйте позже.');
    }
}

// Отображение данных статистики
function renderStatsData(statsData, diaryData) {
    const statsContent = document.getElementById('stats-content');
    
    // Получаем текущую дату для отображения итогов дня
    const today = new Date();
    const todayStr = today.toISOString().split('T')[0]; // YYYY-MM-DD
    
    // Находим данные за сегодня в дневнике
    const todayData = diaryData.days.find(day => {
        const dayDate = new Date(day.date.split('.').reverse().join('-'));
        return dayDate.toISOString().split('T')[0] === todayStr;
    });
    
    // Формируем HTML для раздела статистики
    let html = `
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>📅 Итоги дня</span>
                        <div class="btn-group">
                            <button id="prev-day-btn" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-chevron-left"></i>
                            </button>
                            <button id="today-btn" class="btn btn-sm btn-primary">Сегодня</button>
                            <button id="next-day-btn" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body" id="daily-summary">
                        ${renderDailySummary(todayData, statsData.user_targets)}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">📊 Общая статистика</div>
                    <div class="card-body">
                        ${renderGeneralStats(statsData.general)}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">🥩 Распределение БЖУ</div>
                    <div class="card-body">
                        ${renderNutritionDistribution(statsData.nutrition_distribution)}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">🍎 Топ продукты</div>
                    <div class="card-body">
                        ${renderTopProducts(statsData.top_products)}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    statsContent.innerHTML = html;
    
    // Инициализация обработчиков событий для кнопок навигации по дням
    initDayNavigation(diaryData, statsData.user_targets);
    
    // Инициализация графиков и визуализаций
    initCharts(statsData);
}

// Отображение итогов дня
function renderDailySummary(dayData, targets) {
    if (!dayData) {
        return `
            <div class="text-center py-4">
                <div class="mb-3">
                    <i class="fas fa-calendar-day fa-3x text-muted"></i>
                </div>
                <h5>Нет данных за сегодня</h5>
                <p class="text-muted">Добавьте приемы пищи в дневник, чтобы увидеть итоги дня</p>
            </div>
        `;
    }
    
    // Расчет процента от целевых значений
    const caloriesPercent = Math.min(100, Math.round((dayData.total_calories / targets.calories) * 100));
    
    // Расчет БЖУ из приемов пищи
    let totalProtein = 0;
    let totalFat = 0;
    let totalCarb = 0;
    let totalFiber = 0;
    
    dayData.meals.forEach(meal => {
        // Примерное распределение калорий по БЖУ, если нет точных данных
        const mealCalories = meal.calories;
        totalProtein += Math.round(mealCalories * 0.25 / 4); // 25% белков, 4 ккал/г
        totalFat += Math.round(mealCalories * 0.3 / 9);      // 30% жиров, 9 ккал/г
        totalCarb += Math.round(mealCalories * 0.45 / 4);    // 45% углеводов, 4 ккал/г
        totalFiber += 2; // Примерное значение
    });
    
    // Расчет процентов от целевых значений
    const proteinPercent = Math.min(100, Math.round((totalProtein / targets.protein) * 100));
    const fatPercent = Math.min(100, Math.round((totalFat / targets.fat) * 100));
    const carbPercent = Math.min(100, Math.round((totalCarb / targets.carb) * 100));
    const fiberPercent = Math.min(100, Math.round((totalFiber / targets.fiber) * 100));
    
    return `
        <h5 class="mb-3">${formatDate(dayData.date)}</h5>
        
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span>Калории</span>
                <span>${dayData.total_calories} / ${targets.calories} ккал</span>
            </div>
            <div class="progress" style="height: 10px;">
                <div class="progress-bar bg-primary" role="progressbar" style="width: ${caloriesPercent}%" 
                    aria-valuenow="${caloriesPercent}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
        
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span>Белки</span>
                <span>${totalProtein} / ${targets.protein} г</span>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-success" role="progressbar" style="width: ${proteinPercent}%" 
                    aria-valuenow="${proteinPercent}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
        
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span>Жиры</span>
                <span>${totalFat} / ${targets.fat} г</span>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-warning" role="progressbar" style="width: ${fatPercent}%" 
                    aria-valuenow="${fatPercent}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
        
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span>Углеводы</span>
                <span>${totalCarb} / ${targets.carb} г</span>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-info" role="progressbar" style="width: ${carbPercent}%" 
                    aria-valuenow="${carbPercent}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
        
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span>Клетчатка</span>
                <span>${totalFiber} / ${targets.fiber} г</span>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-secondary" role="progressbar" style="width: ${fiberPercent}%" 
                    aria-valuenow="${fiberPercent}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
        
        <div class="mt-3">
            <h6>Приемы пищи:</h6>
            <ul class="list-group">
                ${dayData.meals.map(meal => `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="fw-bold">${meal.name}</span>
                            <small class="text-muted d-block">${meal.time}</small>
                        </div>
                        <span class="badge bg-primary rounded-pill">${meal.calories} ккал</span>
                    </li>
                `).join('')}
            </ul>
        </div>
    `;
}

// Отображение общей статистики
function renderGeneralStats(generalStats) {
    return `
        <div class="row">
            <div class="col-6 col-md-3 mb-3">
                <div class="text-center">
                    <h3>${generalStats.avg_calories}</h3>
                    <small class="text-muted">Средние ккал/день</small>
                </div>
            </div>
            <div class="col-6 col-md-3 mb-3">
                <div class="text-center">
                    <h3>${generalStats.days_tracked}</h3>
                    <small class="text-muted">Дней отслежено</small>
                </div>
            </div>
            <div class="col-6 col-md-3 mb-3">
                <div class="text-center">
                    <h3>${generalStats.adherence_percent}%</h3>
                    <small class="text-muted">Соблюдение нормы</small>
                </div>
            </div>
            <div class="col-6 col-md-3 mb-3">
                <div class="text-center">
                    <h3>${generalStats.weight_change > 0 ? '+' : ''}${generalStats.weight_change} кг</h3>
                    <small class="text-muted">Изменение веса</small>
                </div>
            </div>
        </div>
    `;
}

// Отображение распределения БЖУ
function renderNutritionDistribution(distribution) {
    // Создаем данные для круговой диаграммы
    const chartData = {
        protein: distribution.protein,
        fat: distribution.fat,
        carb: distribution.carb
    };
    
    return `
        <div class="row align-items-center">
            <div class="col-md-6 mb-3">
                <div id="nutrition-chart" style="height: 200px;"></div>
            </div>
            <div class="col-md-6">
                <div class="mb-2">
                    <div class="d-flex justify-content-between">
                        <span><i class="fas fa-circle text-success"></i> Белки</span>
                        <span>${distribution.protein}%</span>
                    </div>
                </div>
                <div class="mb-2">
                    <div class="d-flex justify-content-between">
                        <span><i class="fas fa-circle text-warning"></i> Жиры</span>
                        <span>${distribution.fat}%</span>
                    </div>
                </div>
                <div class="mb-2">
                    <div class="d-flex justify-content-between">
                        <span><i class="fas fa-circle text-info"></i> Углеводы</span>
                        <span>${distribution.carb}%</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Отображение топ продуктов
function renderTopProducts(products) {
    if (!products || products.length === 0) {
        return `
            <div class="text-center py-3">
                <p class="text-muted">Нет данных о продуктах</p>
            </div>
        `;
    }
    
    return `
        <ul class="list-group">
            ${products.map((product, index) => `
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <span class="fw-bold">${index + 1}. ${product.name}</span>
                    </div>
                    <span class="badge bg-primary rounded-pill">${product.count} раз</span>
                </li>
            `).join('')}
        </ul>
    `;
}

// Инициализация навигации по дням
function initDayNavigation(diaryData, targets) {
    const prevDayBtn = document.getElementById('prev-day-btn');
    const nextDayBtn = document.getElementById('next-day-btn');
    const todayBtn = document.getElementById('today-btn');
    const dailySummary = document.getElementById('daily-summary');
    
    // Текущий индекс дня в массиве дней
    let currentDayIndex = 0;
    
    // Обработчик для кнопки "Предыдущий день"
    prevDayBtn.addEventListener('click', () => {
        if (currentDayIndex < diaryData.days.length - 1) {
            currentDayIndex++;
            updateDailySummary();
        }
    });
    
    // Обработчик для кнопки "Следующий день"
    nextDayBtn.addEventListener('click', () => {
        if (currentDayIndex > 0) {
            currentDayIndex--;
            updateDailySummary();
        }
    });
    
    // Обработчик для кнопки "Сегодня"
    todayBtn.addEventListener('click', () => {
        currentDayIndex = 0;
        updateDailySummary();
    });
    
    // Функция обновления итогов дня
    function updateDailySummary() {
        const dayData = diaryData.days[currentDayIndex];
        dailySummary.innerHTML = renderDailySummary(dayData, targets);
        
        // Обновляем состояние кнопок
        prevDayBtn.disabled = currentDayIndex >= diaryData.days.length - 1;
        nextDayBtn.disabled = currentDayIndex <= 0;
    }
}

// Инициализация графиков
function initCharts(statsData) {
    // Проверяем, загружена ли библиотека Chart.js
    if (typeof Chart === 'undefined') {
        // Если Chart.js не загружен, добавляем его
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        script.onload = () => createNutritionChart(statsData.nutrition_distribution);
        document.head.appendChild(script);
    } else {
        // Если Chart.js уже загружен, создаем график
        createNutritionChart(statsData.nutrition_distribution);
    }
}

// Создание круговой диаграммы распределения БЖУ
function createNutritionChart(distribution) {
    const chartElement = document.getElementById('nutrition-chart');
    if (!chartElement) return;
    
    // Создаем canvas для графика
    chartElement.innerHTML = '<canvas></canvas>';
    const ctx = chartElement.querySelector('canvas').getContext('2d');
    
    // Создаем круговую диаграмму
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Белки', 'Жиры', 'Углеводы'],
            datasets: [{
                data: [distribution.protein, distribution.fat, distribution.carb],
                backgroundColor: ['#28a745', '#ffc107', '#17a2b8'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Отображение ошибки в разделе статистики
function showStatsError(message) {
    const statsContent = document.getElementById('stats-content');
    statsContent.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-circle"></i> ${message}
        </div>
    `;
}

// Форматирование даты (DD.MM.YYYY -> "DD месяц YYYY")
function formatDate(dateStr) {
    const months = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ];
    
    const parts = dateStr.split('.');
    if (parts.length !== 3) return dateStr;
    
    const day = parseInt(parts[0]);
    const month = parseInt(parts[1]) - 1;
    const year = parseInt(parts[2]);
    
    return `${day} ${months[month]} ${year}`;
}
