/**
 * test_utils.test.js — unit-тесты для frontend/js/utils.js
 *
 * Покрытые сценарии:
 *
 * Маршрутизация (getProjectRoute / openProject):
 *   - ucn_sites_v1 → /sites.html?project_id=<id>
 *   - placeholder   → /project.html?id=<id>
 *   - null / undefined → /index.html
 *
 * moduleLabel:
 *   - ucn_sites_v1   → 'Модуль УЦН'
 *   - placeholder    → 'Архитектурный контейнер'
 *   - unknown key    → 'Архитектурный контейнер'
 *
 * escHtml (XSS-защита):
 *   - &, <, > экранируются
 *   - null/undefined → ''
 *
 * renderNavbar:
 *   - На экране выбора проекта (activePage='index') нет пунктов меню "Объекты"
 *   - На внутренней странице проекта есть пункт "Отчеты"
 *   - На внутренней странице (activePage='sites') с ucn-проектом есть "Объекты"
 *   - На экране index нет "Сменить большой проект" в меню
 *   - На внутренней странице есть "Сменить большой проект"
 *   - Нет отдельного верхнего пункта "Проекты" в navbar-nav me-auto
 *   - Admin на внутренней странице видит "Управление проектами" (в dropdown)
 *   - Viewer/Manager не видят "Управление проектами"
 *   - Manager не видит "Справочники" в верхнем меню
 *   - На экране index видна кнопка brand "RTKS Tracker"
 *
 * statusBadge:
 *   - Возвращает span с корректным классом и русским названием
 *
 * roleBadge:
 *   - Возвращает span с корректными данными роли
 */

const path = require('path');
const fs   = require('fs');

// Загружаем utils.js в jsdom-контекст как глобальные переменные
const utilsCode = fs.readFileSync(
    path.resolve(__dirname, '../../frontend/js/utils.js'),
    'utf8'
);
eval(utilsCode);  // eslint-disable-line no-eval

// ── Тестовые данные ───────────────────────────────────────────────────────────

const UCN_PROJECT = {
    id:         42,
    name:       'УЦН 2.0 2026 год',
    code:       'ucn-2026',
    module_key: 'ucn_sites_v1',
    is_configured: true,
    description: 'Проект UCN',
};

const PH_PROJECT = {
    id:         7,
    name:       'ТСПУ',
    code:       'tspu',
    module_key: 'placeholder',
    is_configured: false,
    description: 'Placeholder',
};

const ADMIN_USER = {
    id:        1,
    username:  'admin',
    full_name: 'Иван Администратор',
    role:      'admin',
    email:     'admin@example.com',
};

const MANAGER_USER = {
    id:        2,
    username:  'manager',
    full_name: 'Пётр Менеджер',
    role:      'manager',
    email:     'manager@example.com',
};

const VIEWER_USER = {
    id:        3,
    username:  'viewer',
    full_name: 'Сергей Просмотр',
    role:      'viewer',
    email:     'viewer@example.com',
};


// ════════════════════════════════════════════════════════════════════════════
// getProjectRoute
// ════════════════════════════════════════════════════════════════════════════

describe('getProjectRoute', () => {
    test('ucn_sites_v1 → /sites.html?project_id=<id>', () => {
        expect(getProjectRoute(UCN_PROJECT)).toBe('/sites.html?project_id=42');
    });

    test('placeholder → /project.html?id=<id>', () => {
        expect(getProjectRoute(PH_PROJECT)).toBe('/project.html?id=7');
    });

    test('null → /index.html', () => {
        expect(getProjectRoute(null)).toBe('/index.html');
    });

    test('undefined → /index.html', () => {
        expect(getProjectRoute(undefined)).toBe('/index.html');
    });
});


// ════════════════════════════════════════════════════════════════════════════
// moduleLabel
// ════════════════════════════════════════════════════════════════════════════

describe('moduleLabel', () => {
    test('ucn_sites_v1 → "Модуль УЦН"', () => {
        expect(moduleLabel('ucn_sites_v1')).toBe('Модуль УЦН');
    });

    test('placeholder → "Архитектурный контейнер"', () => {
        expect(moduleLabel('placeholder')).toBe('Архитектурный контейнер');
    });

    test('unknown key → "Архитектурный контейнер" (fallback)', () => {
        expect(moduleLabel('unknown_module')).toBe('Архитектурный контейнер');
    });
});


// ════════════════════════════════════════════════════════════════════════════
// escHtml
// ════════════════════════════════════════════════════════════════════════════

describe('escHtml', () => {
    test('& → &amp;', () => {
        expect(escHtml('A & B')).toBe('A &amp; B');
    });

    test('< → &lt;', () => {
        expect(escHtml('<script>')).toBe('&lt;script&gt;');
    });

    test('> → &gt;', () => {
        expect(escHtml('a > b')).toBe('a &gt; b');
    });

    test('null → ""', () => {
        expect(escHtml(null)).toBe('');
    });

    test('undefined → ""', () => {
        expect(escHtml(undefined)).toBe('');
    });

    test('plain string passes through unchanged', () => {
        expect(escHtml('Привет мир')).toBe('Привет мир');
    });

    test('XSS payload is fully escaped', () => {
        const xss = '<img src=x onerror="alert(1)">';
        const escaped = escHtml(xss);
        expect(escaped).not.toContain('<img');
        expect(escaped).toContain('&lt;img');
    });
});


// ════════════════════════════════════════════════════════════════════════════
// renderNavbar — общая структура
// ════════════════════════════════════════════════════════════════════════════

describe('renderNavbar — index (выбор проекта)', () => {
    let html;

    beforeEach(() => {
        // На экране index нет текущего проекта
        api.getCurrentProject.mockReturnValue(null);
        html = renderNavbar(ADMIN_USER, 'index');
    });

    test('Содержит brand "RTKS Tracker"', () => {
        expect(html).toContain('RTKS Tracker');
    });

    test('НЕ содержит ссылку "Объекты" в главном меню', () => {
        // На экране index нет showSitesLink
        // Проверяем, что нет nav-item с текстом "Объекты" в основном меню
        // (navbar-nav me-auto)
        const navSection = html.split('navbar-nav me-auto')[1]?.split('navbar-nav')[0] || html;
        expect(navSection).not.toContain('>Объекты<');
    });

    test('НЕ содержит "Сменить большой проект" (мы уже на index)', () => {
        expect(html).not.toContain('Сменить большой проект');
    });

    test('Admin сразу видит "Пользователи" и "Логи" в верхнем меню', () => {
        expect(html).toContain('Пользователи');
        expect(html).toContain('Логи');
    });

    test('На index у admin ещё нет "Справочники"', () => {
        expect(html).not.toContain('Справочники');
    });

    test('На index нет "Отчеты" без выбранного проекта', () => {
        expect(html).not.toContain('Отчеты');
    });

    test('Содержит пункт "Мой профиль" в dropdown', () => {
        expect(html).toContain('Мой профиль');
    });

    test('НЕ содержит отдельный пункт "Проекты" в основном navbar-nav', () => {
        // "Проекты" как отдельный nav-item должен отсутствовать
        // (Управление проектами находится в dropdown, а не в верхней навигации)
        const mainNavSection = html.split('navbar-nav me-auto')[1]?.split('</ul>')[0] || '';
        expect(mainNavSection).not.toMatch(/nav-link[^>]*>Проекты</);
    });
});


describe('renderNavbar — внутренняя страница (sites) с UCN-проектом', () => {
    let html;

    beforeEach(() => {
        api.getCurrentProject.mockReturnValue(UCN_PROJECT);
        html = renderNavbar(ADMIN_USER, 'sites');
    });

    test('Содержит ссылку "Объекты"', () => {
        expect(html).toContain('Объекты');
    });

    test('Содержит ссылку "Отчеты"', () => {
        expect(html).toContain('Отчеты');
    });

    test('Содержит "Сменить большой проект"', () => {
        expect(html).toContain('Сменить большой проект');
    });

    test('Admin видит "Управление проектами" в dropdown', () => {
        expect(html).toContain('Управление проектами');
    });

    test('Admin внутри проекта видит "Пользователи", "Логи" и "Справочники"', () => {
        expect(html).toContain('Пользователи');
        expect(html).toContain('Логи');
        expect(html).toContain('Справочники');
    });

    test('Dropdown содержит ссылку на профиль', () => {
        expect(html).toContain('/profile.html');
    });

    test('Dropdown-тогглеры рендерятся как button, а не hash-ссылки', () => {
        expect(html).toContain('id="navbarUserToggle"');
        expect(html).toContain('type="button"');
        expect(html).toContain('data-nav-dropdown-toggle="true"');
        expect(html).not.toContain('href="#" data-bs-toggle="dropdown"');
    });

    test('НЕ содержит отдельный верхний пункт "Проекты" в основном navbar-nav', () => {
        // Верхняя навигация не должна иметь пункт "Проекты" как самостоятельный nav-item.
        // Управление проектами доступно только через dropdown пользователя.
        const mainNavSection = html.split('navbar-nav me-auto')[1]?.split('</ul>')[0] || '';
        expect(mainNavSection).not.toMatch(/nav-link[^>]*>\s*Проекты\s*</);
    });
});

describe('mountNavbar', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="navbar-container"></div>';
        api.getCurrentProject.mockReturnValue(UCN_PROJECT);
    });

    test('Монтирует navbar и открывает dropdown по клику', () => {
        mountNavbar(ADMIN_USER, 'sites');

        const toggle = document.getElementById('navbarUserToggle');
        const menu = document.querySelector('[data-nav-dropdown-menu][aria-labelledby="navbarUserToggle"]');

        expect(document.getElementById('navbar-container').innerHTML).toContain('Мой профиль');
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        expect(menu.classList.contains('show')).toBe(false);

        toggle.click();
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(menu.classList.contains('show')).toBe(true);
    });
});


describe('renderNavbar — manager на внутренней странице', () => {
    let html;

    beforeEach(() => {
        api.getCurrentProject.mockReturnValue(UCN_PROJECT);
        html = renderNavbar(MANAGER_USER, 'sites');
    });

    test('Manager НЕ видит "Управление проектами"', () => {
        expect(html).not.toContain('Управление проектами');
    });

    test('Manager видит "Сменить большой проект"', () => {
        expect(html).toContain('Сменить большой проект');
    });

    test('Manager НЕ видит раздел "Справочники"', () => {
        expect(html).not.toContain('Справочники');
    });
});


describe('renderNavbar — viewer на внутренней странице', () => {
    let html;

    beforeEach(() => {
        api.getCurrentProject.mockReturnValue(UCN_PROJECT);
        html = renderNavbar(VIEWER_USER, 'sites');
    });

    test('Viewer НЕ видит "Управление проектами"', () => {
        expect(html).not.toContain('Управление проектами');
    });

    test('Viewer НЕ видит "Справочники"', () => {
        // canManage = false для viewer
        expect(html).not.toContain('Справочники');
    });

    test('Viewer видит "Сменить большой проект"', () => {
        expect(html).toContain('Сменить большой проект');
    });
});


describe('renderNavbar — placeholder-проект', () => {
    test('На placeholder-проекте нет ссылки "Объекты"', () => {
        api.getCurrentProject.mockReturnValue(PH_PROJECT);
        const html = renderNavbar(ADMIN_USER, 'project');
        // showSitesLink = module_key === 'ucn_sites_v1' — для placeholder false
        expect(html).not.toContain('>Объекты<');
    });

    test('На placeholder-проекте есть ссылка "Отчеты"', () => {
        api.getCurrentProject.mockReturnValue(PH_PROJECT);
        const html = renderNavbar(ADMIN_USER, 'project');
        expect(html).toContain('Отчеты');
    });
});


// ════════════════════════════════════════════════════════════════════════════
// statusBadge
// ════════════════════════════════════════════════════════════════════════════

describe('statusBadge', () => {
    test('planned → содержит "Запланирован"', () => {
        expect(statusBadge('planned')).toContain('Запланирован');
    });

    test('accepted → содержит "Принят"', () => {
        expect(statusBadge('accepted')).toContain('Принят');
    });

    test('cancelled → содержит "Отменён"', () => {
        expect(statusBadge('cancelled')).toContain('Отменён');
    });

    test('unknown status → отображает исходное значение', () => {
        expect(statusBadge('unknown_xyz')).toContain('unknown_xyz');
    });

    test('Возвращает HTML-тег <span>', () => {
        expect(statusBadge('planned')).toMatch(/<span/);
    });
});


// ════════════════════════════════════════════════════════════════════════════
// roleBadge
// ════════════════════════════════════════════════════════════════════════════

describe('roleBadge', () => {
    test('admin → "Администратор"', () => {
        expect(roleBadge('admin')).toContain('Администратор');
    });

    test('manager → "Менеджер"', () => {
        expect(roleBadge('manager')).toContain('Менеджер');
    });

    test('viewer → "Просмотр"', () => {
        expect(roleBadge('viewer')).toContain('Просмотр');
    });

    test('contractor → "Подрядчик"', () => {
        expect(roleBadge('contractor')).toContain('Подрядчик');
    });
});


// ════════════════════════════════════════════════════════════════════════════
// rememberProject + currentProjectFromStorage
// ════════════════════════════════════════════════════════════════════════════

describe('rememberProject / currentProjectFromStorage', () => {
    beforeEach(() => {
        api.getCurrentProject.mockClear();
        api.setCurrentProject.mockClear();
    });

    test('rememberProject вызывает api.setCurrentProject', () => {
        rememberProject(UCN_PROJECT);
        expect(api.setCurrentProject).toHaveBeenCalledWith(UCN_PROJECT);
    });

    test('rememberProject(null) не вызывает api.setCurrentProject', () => {
        rememberProject(null);
        expect(api.setCurrentProject).not.toHaveBeenCalled();
    });

    test('currentProjectFromStorage возвращает то, что отдаёт api.getCurrentProject', () => {
        api.getCurrentProject.mockReturnValue(UCN_PROJECT);
        expect(currentProjectFromStorage()).toEqual(UCN_PROJECT);
    });
});
