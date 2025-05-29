document.addEventListener('DOMContentLoaded', function() {
    const diaryContent = `
    <div class="container">
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Сегодня</span>
                <span class="badge bg-primary">1850 ккал</span>
            </div>
            <div class="card-body">
                <div class="meal-item mb-3 pb-3 border-bottom">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Завтрак</h5>
                            <p class="text-muted small mb-0">08:30</p>
                        </div>
                        <span class="badge bg-light text-dark">450 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Овсянка на молоке</span>
                            <span class="text-muted">250 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span>Банан</span>
                            <span class="text-muted">105 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Кофе с молоком</span>
                            <span class="text-muted">95 ккал</span>
                        </div>
                    </div>
                </div>
                
                <div class="meal-item mb-3 pb-3 border-bottom">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Обед</h5>
                            <p class="text-muted small mb-0">13:15</p>
                        </div>
                        <span class="badge bg-light text-dark">680 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Куриный суп с вермишелью</span>
                            <span class="text-muted">320 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span>Гречка с курицей</span>
                            <span class="text-muted">310 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Салат из свежих овощей</span>
                            <span class="text-muted">50 ккал</span>
                        </div>
                    </div>
                </div>
                
                <div class="meal-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Ужин</h5>
                            <p class="text-muted small mb-0">19:00</p>
                        </div>
                        <span class="badge bg-light text-dark">720 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Запеченная рыба</span>
                            <span class="text-muted">350 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span>Рис</span>
                            <span class="text-muted">200 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1">
                            <span>Овощи на пару</span>
                            <span class="text-muted">120 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Чай с медом</span>
                            <span class="text-muted">50 ккал</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Вчера</span>
                <span class="badge bg-primary">1720 ккал</span>
            </div>
            <div class="card-body">
                <div class="meal-item mb-3 pb-3 border-bottom">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Завтрак</h5>
                            <p class="text-muted small mb-0">09:00</p>
                        </div>
                        <span class="badge bg-light text-dark">420 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Творог с ягодами</span>
                            <span class="text-muted">280 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Зеленый чай</span>
                            <span class="text-muted">140 ккал</span>
                        </div>
                    </div>
                </div>
                
                <div class="meal-item mb-3 pb-3 border-bottom">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Обед</h5>
                            <p class="text-muted small mb-0">14:00</p>
                        </div>
                        <span class="badge bg-light text-dark">650 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Борщ</span>
                            <span class="text-muted">300 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Котлета с пюре</span>
                            <span class="text-muted">350 ккал</span>
                        </div>
                    </div>
                </div>
                
                <div class="meal-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1">Ужин</h5>
                            <p class="text-muted small mb-0">18:30</p>
                        </div>
                        <span class="badge bg-light text-dark">650 ккал</span>
                    </div>
                    <div class="mt-2">
                        <div class="d-flex justify-content-between mb-1">
                            <span>Тушеная капуста с мясом</span>
                            <span class="text-muted">450 ккал</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>Кефир</span>
                            <span class="text-muted">200 ккал</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="d-grid gap-2">
            <button class="btn btn-primary mb-4" type="button">
                <i class="fas fa-plus-circle me-2"></i>Добавить приём пищи
            </button>
        </div>
    </div>
    `;
    
    document.getElementById('diary-content').innerHTML = diaryContent;
});
