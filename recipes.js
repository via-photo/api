document.addEventListener('DOMContentLoaded', function() {
    const recipesContent = `
    <div class="container">
        <!-- Поиск рецептов -->
        <div class="mb-4">
            <div class="input-group">
                <input type="text" class="form-control" placeholder="Поиск рецептов...">
                <button class="btn btn-primary" type="button">
                    <i class="fas fa-search"></i>
                </button>
            </div>
        </div>
        
        <!-- Категории рецептов -->
        <div class="mb-4 pb-2 border-bottom">
            <div class="d-flex flex-nowrap overflow-auto pb-2" style="gap: 10px;">
                <button class="btn btn-sm btn-primary">Все</button>
                <button class="btn btn-sm btn-outline-primary">Завтраки</button>
                <button class="btn btn-sm btn-outline-primary">Обеды</button>
                <button class="btn btn-sm btn-outline-primary">Ужины</button>
                <button class="btn btn-sm btn-outline-primary">Салаты</button>
                <button class="btn btn-sm btn-outline-primary">Десерты</button>
                <button class="btn btn-sm btn-outline-primary">Напитки</button>
            </div>
        </div>
        
        <!-- Список рецептов -->
        <div class="row g-3">
            <!-- Рецепт 1 -->
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Овсянка с фруктами</h5>
                        <div class="d-flex mb-2">
                            <span class="badge bg-light text-dark me-2">Завтрак</span>
                            <span class="badge bg-light text-dark me-2">15 мин</span>
                            <span class="badge bg-light text-dark">320 ккал</span>
                        </div>
                        <p class="card-text">Питательная овсянка с яблоками, бананом и корицей. Идеальный вариант для здорового завтрака.</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-fire me-1"></i>320 ккал
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fas fa-utensils me-1"></i>1 порция
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary">Подробнее</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Рецепт 2 -->
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Греческий салат</h5>
                        <div class="d-flex mb-2">
                            <span class="badge bg-light text-dark me-2">Салат</span>
                            <span class="badge bg-light text-dark me-2">20 мин</span>
                            <span class="badge bg-light text-dark">250 ккал</span>
                        </div>
                        <p class="card-text">Классический греческий салат с огурцами, помидорами, оливками, сыром фета и оливковым маслом.</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-fire me-1"></i>250 ккал
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fas fa-utensils me-1"></i>2 порции
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary">Подробнее</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Рецепт 3 -->
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Куриная грудка с овощами</h5>
                        <div class="d-flex mb-2">
                            <span class="badge bg-light text-dark me-2">Обед</span>
                            <span class="badge bg-light text-dark me-2">40 мин</span>
                            <span class="badge bg-light text-dark">380 ккал</span>
                        </div>
                        <p class="card-text">Сочная куриная грудка, запеченная с сезонными овощами. Богатый белком и низкокалорийный обед.</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-fire me-1"></i>380 ккал
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fas fa-utensils me-1"></i>2 порции
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary">Подробнее</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Рецепт 4 -->
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Творожная запеканка</h5>
                        <div class="d-flex mb-2">
                            <span class="badge bg-light text-dark me-2">Десерт</span>
                            <span class="badge bg-light text-dark me-2">60 мин</span>
                            <span class="badge bg-light text-dark">290 ккал</span>
                        </div>
                        <p class="card-text">Нежная творожная запеканка с ванилью и изюмом. Полезный десерт, богатый кальцием и белком.</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-fire me-1"></i>290 ккал
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fas fa-utensils me-1"></i>4 порции
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary">Подробнее</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Рецепт 5 -->
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Рыба на пару с рисом</h5>
                        <div class="d-flex mb-2">
                            <span class="badge bg-light text-dark me-2">Ужин</span>
                            <span class="badge bg-light text-dark me-2">30 мин</span>
                            <span class="badge bg-light text-dark">340 ккал</span>
                        </div>
                        <p class="card-text">Диетическое блюдо из нежной рыбы на пару с отварным рисом и лимоном. Идеально для легкого ужина.</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-fire me-1"></i>340 ккал
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fas fa-utensils me-1"></i>2 порции
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary">Подробнее</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Пагинация -->
        <div class="d-flex justify-content-center mt-4 mb-4">
            <nav aria-label="Навигация по рецептам">
                <ul class="pagination">
                    <li class="page-item disabled">
                        <a class="page-link" href="#" tabindex="-1" aria-disabled="true">Назад</a>
                    </li>
                    <li class="page-item active"><a class="page-link" href="#">1</a></li>
                    <li class="page-item"><a class="page-link" href="#">2</a></li>
                    <li class="page-item"><a class="page-link" href="#">3</a></li>
                    <li class="page-item">
                        <a class="page-link" href="#">Вперед</a>
                    </li>
                </ul>
            </nav>
        </div>
    </div>
    `;
    
    document.getElementById('recipes-content').innerHTML = recipesContent;
});
