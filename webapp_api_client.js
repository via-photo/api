/**
 * Клиент API для взаимодействия с бэкендом Telegram бота
 */

class TelegramBotApiClient {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl || 'https://your-api-url.com/api';
        this.apiKey = 'test_api_key'; // В реальном приложении должен быть получен безопасным способом
    }

    /**
     * Получение данных дневника питания пользователя
     * @param {string} userId - ID пользователя в Telegram
     * @returns {Promise<Object>} - Данные дневника питания
     */
    async getDiary(userId) {
        try {
            const response = await this._fetchWithAuth(`${this.apiBaseUrl}/diary/${userId}`);
            return response.data;
        } catch (error) {
            console.error('Ошибка при получении данных дневника:', error);
            throw error;
        }
    }

    /**
     * Получение статистики пользователя
     * @param {string} userId - ID пользователя в Telegram
     * @returns {Promise<Object>} - Данные статистики
     */
    async getStats(userId) {
        try {
            const response = await this._fetchWithAuth(`${this.apiBaseUrl}/stats/${userId}`);
            return response.data;
        } catch (error) {
            console.error('Ошибка при получении статистики:', error);
            throw error;
        }
    }

    /**
     * Получение рецептов для пользователя
     * @param {string} userId - ID пользователя в Telegram
     * @returns {Promise<Object>} - Данные рецептов
     */
    async getRecipes(userId) {
        try {
            const response = await this._fetchWithAuth(`${this.apiBaseUrl}/recipes/${userId}`);
            return response.data;
        } catch (error) {
            console.error('Ошибка при получении рецептов:', error);
            throw error;
        }
    }

    /**
     * Добавление приема пищи
     * @param {Object} mealData - Данные о приеме пищи
     * @returns {Promise<Object>} - Результат операции
     */
    async addMeal(mealData) {
        try {
            const response = await this._fetchWithAuth(`${this.apiBaseUrl}/meal`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(mealData)
            });
            return response;
        } catch (error) {
            console.error('Ошибка при добавлении приема пищи:', error);
            throw error;
        }
    }

    /**
     * Вспомогательный метод для выполнения запросов с аутентификацией
     * @param {string} url - URL для запроса
     * @param {Object} options - Опции запроса
     * @returns {Promise<Object>} - Результат запроса
     * @private
     */
    async _fetchWithAuth(url, options = {}) {
        const headers = {
            'X-API-Key': this.apiKey,
            ...(options.headers || {})
        };

        const response = await fetch(url, {
            ...options,
            headers
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API запрос не удался: ${response.status} ${response.statusText} - ${errorText}`);
        }

        return await response.json();
    }
}

// Экспорт для использования в других скриптах
window.TelegramBotApiClient = TelegramBotApiClient;
