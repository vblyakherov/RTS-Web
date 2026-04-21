/**
 * jest.setup.js — глобальные моки для тестов utils.js.
 *
 * utils.js зависит от:
 *   - глобального объекта `api`  (из api.js)
 *   - глобального объекта `bootstrap` (из Bootstrap CDN)
 *
 * Мы мокируем их здесь, до загрузки тестируемого кода.
 */

// Мок api.js
global.api = {
    getToken:           jest.fn(() => null),
    setToken:           jest.fn(),
    removeToken:        jest.fn(),
    getUser:            jest.fn(() => null),
    setUser:            jest.fn(),
    getCurrentProject:  jest.fn(() => null),
    setCurrentProject:  jest.fn(),
    clearCurrentProject: jest.fn(),
    me:                 jest.fn(),
    getProjects:        jest.fn(),
};

// Мок Bootstrap Toast
global.bootstrap = {
    Toast: jest.fn().mockImplementation(() => ({
        show: jest.fn(),
    })),
    Dropdown: {
        getOrCreateInstance: jest.fn(() => ({
            toggle: jest.fn(),
        })),
    },
};

// localStorage mock (jest-environment-jsdom предоставляет его нативно)
