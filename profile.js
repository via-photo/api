/**
 * Расширение клиента API для работы с профилем пользователя
 */
TelegramBotApiClient.prototype.getUserProfile = async function(userId) {
    try {
        const response = await this._fetchWithAuth(`${this.apiBaseUrl}/profile/${userId}`);
        return response.data;
    } catch (error) {
        console.error('Ошибка при получении данных профиля:', error);
        throw error;
    }
};

TelegramBotApiClient.prototype.updateUserProfile = async function(userId, profileData) {
    try {
        const response = await this._fetchWithAuth(`${this.apiBaseUrl}/profile/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(profileData)
        });
        return response;
    } catch (error) {
        console.error('Ошибка при обновлении профиля:', error);
        throw error;
    }
};

TelegramBotApiClient.prototype.recalculateTargets = async function(userId) {
    try {
        const response = await this._fetchWithAuth(`${this.apiBaseUrl}/profile/${userId}/recalculate`, {
            method: 'POST'
        });
        return response;
    } catch (error) {
        console.error('Ошибка при пересчете целевых значений:', error);
        throw error;
    }
};

/**
 * Функция для загрузки данных профиля
 */
async function loadProfileData(userId) {
    const profileContent = document.getElementById('profile-content');
    
    try {
        profileContent.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mt-2">Загрузка данных профиля...</p>
            </div>
        `;
        
        const apiClient = new TelegramBotApiClient();
        const profileData = await apiClient.getUserProfile(userId);
        
        renderProfileData(profileData);
    } catch (error) {
        console.error('Ошибка при загрузке профиля:', error);
        profileContent.innerHTML = `
            <div class="error-message">
                <p><i class="fas fa-exclamation-circle"></i> Не удалось загрузить данные. Пожалуйста попробуйте позже.</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="loadProfileData('${userId}')">
                    <i class="fas fa-sync-alt"></i> Попробовать снова
                </button>
            </div>
        `;
    }
}

/**
 * Функция для отображения данных профиля
 */
function renderProfileData(profileData) {
    const profileContent = document.getElementById('profile-content');
    
    // Форматирование целевых значений
    const targetKcal = profileData.target_kcal || 0;
    const targetProtein = profileData.target_protein || 0;
    const targetFat = profileData.target_fat || 0;
    const targetCarb = profileData.target_carb || 0;
    const targetFiber = profileData.target_fiber || 0;
    
    // Определение уровня активности в текстовом виде
    let activityText = "Не указано";
    switch(profileData.activity) {
        case "низкий":
            activityText = "Минимальная";
            break;
        case "средний":
            activityText = "Средняя";
            break;
        case "высокий":
            activityText = "Высокая";
            break;
    }
    
    // Определение пола в текстовом виде
    const genderText = profileData.gender === "муж" ? "Мужской" : 
                       profileData.gender === "жен" ? "Женский" : "Не указано";
    
    profileContent.innerHTML = `
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Личные данные</span>
                <button class="btn btn-sm btn-outline-primary edit-profile-btn" data-section="personal">
                    <i class="fas fa-pencil-alt"></i> Изменить
                </button>
            </div>
            <div class="card-body">
                <div class="row mb-2">
                    <div class="col-6 text-muted">Пол:</div>
                    <div class="col-6">${genderText}</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Возраст:</div>
                    <div class="col-6">${profileData.age || "Не указано"} лет</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Рост:</div>
                    <div class="col-6">${profileData.height || "Не указано"} см</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Текущий вес:</div>
                    <div class="col-6">${profileData.weight || "Не указано"} кг</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Желаемый вес:</div>
                    <div class="col-6">${profileData.goal || "Не указано"} кг</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Активность:</div>
                    <div class="col-6">${activityText}</div>
                </div>
                ${profileData.gender === "жен" ? `
                <div class="row mb-2">
                    <div class="col-6 text-muted">Беременность/ГВ:</div>
                    <div class="col-6">${profileData.pregnant ? "Да" : "Нет"}</div>
                </div>` : ''}
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Целевые значения</span>
                <button class="btn btn-sm btn-outline-primary recalculate-targets-btn">
                    <i class="fas fa-calculator"></i> Пересчитать
                </button>
            </div>
            <div class="card-body">
                <div class="row mb-2">
                    <div class="col-6 text-muted">Калории:</div>
                    <div class="col-6">${targetKcal} ккал</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Белки:</div>
                    <div class="col-6">${targetProtein} г</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Жиры:</div>
                    <div class="col-6">${targetFat} г</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Углеводы:</div>
                    <div class="col-6">${targetCarb} г</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Клетчатка:</div>
                    <div class="col-6">${targetFiber} г</div>
                </div>
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Настройки</span>
                <button class="btn btn-sm btn-outline-primary edit-profile-btn" data-section="settings">
                    <i class="fas fa-cog"></i> Изменить
                </button>
            </div>
            <div class="card-body">
                <div class="row mb-2">
                    <div class="col-6 text-muted">Часовой пояс:</div>
                    <div class="col-6">UTC ${profileData.utc_offset >= 0 ? '+' : ''}${profileData.utc_offset}</div>
                </div>
                <div class="row mb-2">
                    <div class="col-6 text-muted">Утренние напоминания:</div>
                    <div class="col-6">${profileData.morning_reminded !== undefined ? (profileData.morning_reminded ? "Включены" : "Выключены") : "Не настроено"}</div>
                </div>
            </div>
        </div>
        
        <button id="logoutBtn" class="btn btn-outline-danger w-100 mb-4">
            <i class="fas fa-sign-out-alt"></i> Выйти из приложения
        </button>
    `;
    
    // Добавляем обработчики событий для кнопок редактирования
    document.querySelectorAll('.edit-profile-btn').forEach(button => {
        button.addEventListener('click', function() {
            const section = this.getAttribute('data-section');
            showEditProfileForm(section, profileData);
        });
    });
    
    // Обработчик для кнопки пересчета целевых значений
    document.querySelector('.recalculate-targets-btn').addEventListener('click', function() {
        recalculateTargets(profileData);
    });
    
    // Обработчик для кнопки выхода
    document.getElementById('logoutBtn').addEventListener('click', function() {
        // Очищаем локальное хранилище
        localStorage.removeItem('telegramUser');
        // Закрываем WebApp
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.close();
        } else {
            alert('Функция доступна только в Telegram');
        }
    });
}

/**
 * Функция для отображения формы редактирования профиля
 */
function showEditProfileForm(section, profileData) {
    const profileContent = document.getElementById('profile-content');
    
    if (section === 'personal') {
        profileContent.innerHTML = `
            <div class="card mb-4">
                <div class="card-header">
                    <span>Редактирование личных данных</span>
                </div>
                <div class="card-body">
                    <form id="personalDataForm">
                        <div class="mb-3">
                            <label for="gender" class="form-label">Пол</label>
                            <select class="form-select" id="gender" required>
                                <option value="муж" ${profileData.gender === "муж" ? "selected" : ""}>Мужской</option>
                                <option value="жен" ${profileData.gender === "жен" ? "selected" : ""}>Женский</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label for="age" class="form-label">Возраст (лет)</label>
                            <input type="number" class="form-control" id="age" value="${profileData.age || ""}" min="12" max="100" required>
                        </div>
                        
                        <div class="mb-3">
                            <label for="height" class="form-label">Рост (см)</label>
                            <input type="number" class="form-control" id="height" value="${profileData.height || ""}" min="100" max="250" required>
                        </div>
                        
                        <div class="mb-3">
                            <label for="weight" class="form-label">Текущий вес (кг)</label>
                            <input type="number" class="form-control" id="weight" value="${profileData.weight || ""}" min="30" max="250" step="0.1" required>
                        </div>
                        
                        <div class="mb-3">
                            <label for="goal" class="form-label">Желаемый вес (кг)</label>
                            <input type="number" class="form-control" id="goal" value="${profileData.goal || ""}" min="30" max="250" step="0.1" required>
                        </div>
                        
                        <div class="mb-3">
                            <label for="activity" class="form-label">Уровень активности</label>
                            <select class="form-select" id="activity" required>
                                <option value="низкий" ${profileData.activity === "низкий" ? "selected" : ""}>Минимальная</option>
                                <option value="средний" ${profileData.activity === "средний" ? "selected" : ""}>Средняя</option>
                                <option value="высокий" ${profileData.activity === "высокий" ? "selected" : ""}>Высокая</option>
                            </select>
                            <div class="form-text">
                                <small>
                                    <strong>Минимальная</strong> — сидячая работа, почти нет движения в течение дня, нет тренировок.<br>
                                    <strong>Средняя</strong> — немного двигаешься в течение дня, бывают лёгкие тренировки 1–2 раза в неделю.<br>
                                    <strong>Высокая</strong> — активный образ жизни или регулярные тренировки 3–5 раз в неделю.
                                </small>
                            </div>
                        </div>
                        
                        ${profileData.gender === "жен" ? `
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="pregnant" ${profileData.pregnant ? "checked" : ""}>
                            <label class="form-check-label" for="pregnant">Беременность или грудное вскармливание</label>
                        </div>` : ''}
                        
                        <div class="d-flex justify-content-between">
                            <button type="button" class="btn btn-outline-secondary cancel-edit-btn">Отмена</button>
                            <button type="submit" class="btn btn-primary">Сохранить</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    } else if (section === 'settings') {
        profileContent.innerHTML = `
            <div class="card mb-4">
                <div class="card-header">
                    <span>Редактирование настроек</span>
                </div>
                <div class="card-body">
                    <form id="settingsForm">
                        <div class="mb-3">
                            <label for="timezone" class="form-label">Часовой пояс (UTC)</label>
                            <select class="form-select" id="timezone" required>
                                ${generateTimezoneOptions(profileData.utc_offset)}
                            </select>
                        </div>
                        
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="morningReminders" ${profileData.morning_reminded !== undefined ? (profileData.morning_reminded ? "checked" : "") : ""}>
                            <label class="form-check-label" for="morningReminders">Утренние напоминания</label>
                            <div class="form-text">Бот будет напоминать о необходимости записать завтрак</div>
                        </div>
                        
                        <div class="d-flex justify-content-between">
                            <button type="button" class="btn btn-outline-secondary cancel-edit-btn">Отмена</button>
                            <button type="submit" class="btn btn-primary">Сохранить</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    }
    
    // Обработчик для кнопки отмены
    document.querySelector('.cancel-edit-btn').addEventListener('click', function() {
        const userId = getUserId();
        loadProfileData(userId);
    });
    
    // Обработчик для формы личных данных
    if (section === 'personal') {
        document.getElementById('personalDataForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userId = getUserId();
            const updatedData = {
                gender: document.getElementById('gender').value,
                age: parseInt(document.getElementById('age').value),
                height: parseInt(document.getElementById('height').value),
                weight: parseFloat(document.getElementById('weight').value),
                goal: parseFloat(document.getElementById('goal').value),
                activity: document.getElementById('activity').value
            };
            
            if (profileData.gender === "жен") {
                updatedData.pregnant = document.getElementById('pregnant').checked;
            }
            
            updateProfileData(userId, updatedData);
        });
    }
    
    // Обработчик для формы настроек
    if (section === 'settings') {
        document.getElementById('settingsForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userId = getUserId();
            const updatedData = {
                utc_offset: parseInt(document.getElementById('timezone').value),
                morning_reminded: document.getElementById('morningReminders').checked
            };
            
            updateProfileData(userId, updatedData);
        });
    }
}

/**
 * Функция для обновления данных профиля
 */
async function updateProfileData(userId, updatedData) {
    const profileContent = document.getElementById('profile-content');
    
    try {
        profileContent.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mt-2">Обновление данных профиля...</p>
            </div>
        `;
        
        const apiClient = new TelegramBotApiClient();
        await apiClient.updateUserProfile(userId, updatedData);
        
        // Если обновление прошло успешно, загружаем обновленные данные
        const profileData = await apiClient.getUserProfile(userId);
        renderProfileData(profileData);
        
        // Показываем уведомление об успешном обновлении
        showToast('Профиль успешно обновлен');
    } catch (error) {
        console.error('Ошибка при обновлении профиля:', error);
        profileContent.innerHTML = `
            <div class="error-message">
                <p><i class="fas fa-exclamation-circle"></i> Не удалось обновить данные. Пожалуйста попробуйте позже.</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="loadProfileData('${userId}')">
                    <i class="fas fa-sync-alt"></i> Вернуться к профилю
                </button>
            </div>
        `;
    }
}

/**
 * Функция для пересчета целевых значений
 */
async function recalculateTargets(profileData) {
    const userId = getUserId();
    const profileContent = document.getElementById('profile-content');
    
    try {
        profileContent.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mt-2">Пересчет целевых значений...</p>
            </div>
        `;
        
        const apiClient = new TelegramBotApiClient();
        await apiClient.recalculateTargets(userId);
        
        // Если пересчет прошел успешно, загружаем обновленные данные
        const updatedProfileData = await apiClient.getUserProfile(userId);
        renderProfileData(updatedProfileData);
        
        // Показываем уведомление об успешном пересчете
        showToast('Целевые значения успешно пересчитаны');
    } catch (error) {
        console.error('Ошибка при пересчете целевых значений:', error);
        profileContent.innerHTML = `
            <div class="error-message">
                <p><i class="fas fa-exclamation-circle"></i> Не удалось пересчитать целевые значения. Пожалуйста попробуйте позже.</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="loadProfileData('${userId}')">
                    <i class="fas fa-sync-alt"></i> Вернуться к профилю
                </button>
            </div>
        `;
    }
}

/**
 * Функция для генерации опций часовых поясов
 */
function generateTimezoneOptions(currentOffset) {
    let options = '';
    for (let i = -12; i <= 14; i++) {
        options += `<option value="${i}" ${i === currentOffset ? 'selected' : ''}>UTC ${i >= 0 ? '+' : ''}${i}</option>`;
    }
    return options;
}

/**
 * Функция для отображения уведомления
 */
function showToast(message) {
    // Создаем элемент уведомления
    const toastContainer = document.createElement('div');
    toastContainer.style.position = 'fixed';
    toastContainer.style.bottom = '20px';
    toastContainer.style.left = '50%';
    toastContainer.style.transform = 'translateX(-50%)';
    toastContainer.style.zIndex = '9999';
    
    const toast = document.createElement('div');
    toast.className = 'toast show';
    toast.style.minWidth = '250px';
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto">Уведомление</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);
    
    // Удаляем уведомление через 3 секунды
    setTimeout(() => {
        document.body.removeChild(toastContainer);
    }, 3000);
}

// Добавляем загрузку профиля в основную функцию загрузки данных
function loadAllData() {
    const userId = getUserId();
    
    if (!userId) {
        showError('diary-content', 'Не удалось получить ID пользователя. Пожалуйста, откройте приложение через Telegram.');
        showError('stats-content', 'Не удалось получить ID пользователя. Пожалуйста, откройте приложение через Telegram.');
        showError('recipes-content', 'Не удалось получить ID пользователя. Пожалуйста, откройте приложение через Telegram.');
        showError('profile-content', 'Не удалось получить ID пользователя. Пожалуйста, откройте приложение через Telegram.');
        return;
    }
    
    // Загружаем данные для всех разделов
    loadDiaryData(userId);
    loadStatsData(userId);
    loadRecipesData(userId);
    loadProfileData(userId);
}
