/**
 * 统一的API响应处理工具
 */

class ApiResponse {
    /**
     * 处理API响应
     * @param {Object} response - API响应对象
     * @param {Function} onSuccess - 成功回调函数，接收data参数
     * @param {Function} onError - 错误回调函数，接收message参数
     */
    static handle(response, onSuccess, onError) {
        if (response.code === 0) {
            // 成功响应
            if (typeof onSuccess === 'function') {
                onSuccess(response.data || {});
            }
        } else {
            // 错误响应
            if (typeof onError === 'function') {
                onError(response.message || '未知错误');
            } else {
                // 默认错误处理：显示错误消息
                console.error('API错误:', response.message);
                if (typeof showMessage === 'function') {
                    showMessage(response.message, 'error');
                } else {
                    alert(response.message);
                }
            }
        }
    }

    /**
     * 检查响应是否成功
     * @param {Object} response - API响应对象
     * @returns {boolean} - 是否成功
     */
    static isSuccess(response) {
        return response && response.code === 0;
    }

    /**
     * 获取响应数据
     * @param {Object} response - API响应对象
     * @returns {*} - 响应数据
     */
    static getData(response) {
        return response && response.code === 0 ? response.data : null;
    }

    /**
     * 获取错误消息
     * @param {Object} response - API响应对象
     * @returns {string} - 错误消息
     */
    static getErrorMessage(response) {
        return response && response.code !== 0 ? response.message : null;
    }

    /**
     * 创建成功响应
     * @param {*} data - 响应数据
     * @param {string} message - 可选消息
     * @returns {Object} - 响应对象
     */
    static success(data = {}, message = null) {
        return {
            code: 0,
            message: message,
            data: data
        };
    }

    /**
     * 创建错误响应
     * @param {string} message - 错误消息
     * @param {*} data - 可选数据
     * @returns {Object} - 响应对象
     */
    static error(message, data = null) {
        return {
            code: -1,
            message: message,
            data: data
        };
    }
}

/**
 * 封装fetch请求，自动处理响应格式
 */
class ApiClient {
    /**
     * 发送GET请求
     * @param {string} url - 请求URL
     * @param {Object} options - 请求选项
     * @returns {Promise<Object>} - 响应对象
     */
    static async get(url, options = {}) {
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * 发送POST请求
     * @param {string} url - 请求URL
     * @param {*} data - 请求数据
     * @param {Object} options - 请求选项
     * @returns {Promise<Object>} - 响应对象
     */
    static async post(url, data = null, options = {}) {
        try {
            const isFormData = data instanceof FormData;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    ...(isFormData ? {} : {'Content-Type': 'application/json'}),
                    ...options.headers
                },
                body: isFormData ? data : JSON.stringify(data),
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * 发送PUT请求
     * @param {string} url - 请求URL
     * @param {*} data - 请求数据
     * @param {Object} options - 请求选项
     * @returns {Promise<Object>} - 响应对象
     */
    static async put(url, data = null, options = {}) {
        try {
            const isFormData = data instanceof FormData;
            const response = await fetch(url, {
                method: 'PUT',
                headers: {
                    ...(isFormData ? {} : {'Content-Type': 'application/json'}),
                    ...options.headers
                },
                body: isFormData ? data : JSON.stringify(data),
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            return ApiResponse.error(error.message);
        }
    }

    /**
     * 发送DELETE请求
     * @param {string} url - 请求URL
     * @param {Object} options - 请求选项
     * @returns {Promise<Object>} - 响应对象
     */
    static async delete(url, options = {}) {
        try {
            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            return ApiResponse.error(error.message);
        }
    }
}

// 导出到全局作用域
window.ApiResponse = ApiResponse;
window.ApiClient = ApiClient; 