// Файл для интеграции с Telegram WebApp API
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, доступен ли Telegram WebApp API
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        
        // Расширяем WebApp на весь экран
        tg.expand();
        
        // Получаем данные пользователя
        const user = tg.initDataUnsafe?.user;
        if (user) {
            console.log('Telegram user:', user);
            // Здесь можно использовать данные пользователя для персонализации
            // Например, отображать имя пользователя в профиле
            localStorage.setItem('telegramUser', JSON.stringify(user));
        }
        
        // Устанавливаем цвета темы из Telegram
        document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor || '#ffffff');
        document.documentElement.style.setProperty('--tg-theme-text-color', tg.textColor || '#222222');
        document.documentElement.style.setProperty('--tg-theme-button-color', tg.buttonColor || '#4d6073');
        document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.buttonTextColor || '#ffffff');
        
        // Настраиваем кнопку "Назад"
        tg.BackButton.onClick(() => {
            // Получаем текущую активную секцию
            const activeSection = document.querySelector('.section.active');
            const activeSectionId = activeSection.id;
            
            // Если мы не на главной странице (дневник), возвращаемся к ней
            if (activeSectionId !== 'diary-section') {
                // Скрываем все секции
                document.querySelectorAll('.section').forEach(section => section.classList.remove('active'));
                
                // Показываем дневник
                document.getElementById('diary-section').classList.add('active');
                
                // Обновляем активный элемент навигации
                document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
                document.querySelector('[data-section="diary-section"]').classList.add('active');
                
                // Скрываем кнопку "Назад"
                tg.BackButton.hide();
            }
        });
        
        // Обработчик для навигации с учетом кнопки "Назад"
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', function() {
                const sectionId = this.getAttribute('data-section');
                
                // Если переходим на страницу, отличную от дневника, показываем кнопку "Назад"
                if (sectionId !== 'diary-section') {
                    tg.BackButton.show();
                } else {
                    tg.BackButton.hide();
                }
            });
        });
        
        // Функция для отправки данных в бот
        window.sendDataToBot = function(data) {
            tg.sendData(JSON.stringify(data));
        };
        
        // Обработчик для кнопки "Добавить приём пищи"
        document.addEventListener('click', function(e) {
            if (e.target.closest('.btn-primary') && e.target.closest('.btn-primary').textContent.includes('Добавить приём пищи')) {
                // Отправляем команду боту для добавления приема пищи
                window.sendDataToBot({
                    action: 'add_meal',
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Обработчик для кнопок "Подробнее" в рецептах
        document.addEventListener('click', function(e) {
            if (e.target.closest('.btn-outline-primary') && e.target.closest('.btn-outline-primary').textContent.includes('Подробнее')) {
                const recipeCard = e.target.closest('.card');
                const recipeTitle = recipeCard.querySelector('.card-title').textContent;
                
                // Отправляем команду боту для получения подробной информации о рецепте
                window.sendDataToBot({
                    action: 'get_recipe_details',
                    recipe: recipeTitle
                });
            }
        });
    } else {
        console.log('Telegram WebApp API не доступен');
        // Если API не доступен, можно добавить заглушку для тестирования
        document.body.insertAdjacentHTML('afterbegin', 
            '<div class="alert alert-warning m-2" role="alert">' +
            'Приложение запущено вне Telegram. Некоторые функции могут быть недоступны.' +
            '</div>'
        );
    }
});
