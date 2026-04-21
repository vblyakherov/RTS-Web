const STATUS_LABELS = {
    planned:      'Запланирован',
    survey:       'Обследование',
    design:       'Проектирование',
    permitting:   'Разрешения',
    construction: 'Строительство',
    testing:      'Тестирование',
    accepted:     'Принят',
    cancelled:    'Отменён',
};

const STATUS_COLORS = {
    planned:      'secondary',
    survey:       'info',
    design:       'primary',
    permitting:   'warning',
    construction: 'orange',
    testing:      'cyan',
    accepted:     'success',
    cancelled:    'danger',
};

const ROLE_LABELS = {
    admin:      'Администратор',
    manager:    'Менеджер',
    contractor: 'Подрядчик',
    viewer:     'Просмотр',
};

const ROLE_COLORS = {
    admin:      'danger',
    manager:    'primary',
    contractor: 'warning',
    viewer:     'secondary',
};

const ACTION_LABELS = {
    login:         'Вход',
    project_create:'Создание проекта',
    project_update:'Изменение проекта',
    project_delete:'Удаление проекта',
    user_create:   'Создание пользователя',
    user_update:   'Изменение пользователя',
    user_delete:   'Удаление пользователя',
    site_create:   'Создание объекта',
    site_update:   'Изменение объекта',
    site_delete:   'Удаление объекта',
    excel_export:  'Экспорт Excel',
    excel_import:  'Импорт Excel',
    rollback:      'Откат изменений',
};

function statusBadge(status) {
    const label = STATUS_LABELS[status] || status;
    const color = STATUS_COLORS[status] || 'secondary';
    // custom colors handled via CSS classes
    return `<span class="badge status-${status}">${label}</span>`;
}

function roleBadge(role) {
    const label = ROLE_LABELS[role] || role;
    const color = ROLE_COLORS[role] || 'secondary';
    return `<span class="badge bg-${color}">${label}</span>`;
}

function escHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatDate(dt) {
    if (!dt) return '—';
    return new Date(dt).toLocaleDateString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
    });
}

function formatDateTime(dt) {
    if (!dt) return '—';
    return new Date(dt).toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function toDateInputValue(dt) {
    if (!dt) return '';
    return new Date(dt).toISOString().split('T')[0];
}

function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) return;
    const id = 'toast-' + Date.now();
    const icon = type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-triangle' : 'info-circle';
    const bg = type === 'success' ? 'bg-success' : type === 'danger' ? 'bg-danger' : 'bg-warning';
    container.insertAdjacentHTML('beforeend', `
        <div id="${id}" class="toast align-items-center text-white ${bg} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-${icon} me-2"></i>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `);
    const el = document.getElementById(id);
    const toast = new bootstrap.Toast(el, { delay: 4000 });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
}

function getProjectRoute(project) {
    if (!project) return '/index.html';
    if (project.module_key === 'ucn_sites_v1') {
        return `/sites.html?project_id=${project.id}`;
    }
    return `/project.html?id=${project.id}`;
}

function getProjectReportsRoute(project) {
    if (!project) return '/index.html';
    return `/reports.html?project_id=${project.id}`;
}

function rememberProject(project) {
    if (project) {
        api.setCurrentProject(project);
    }
}

function currentProjectFromStorage() {
    return api.getCurrentProject();
}

function moduleLabel(moduleKey) {
    if (moduleKey === 'ucn_sites_v1') return 'Модуль УЦН';
    return 'Архитектурный контейнер';
}

async function checkAuth() {
    const token = api.getToken();
    if (!token) {
        window.location.href = '/login.html';
        return null;
    }
    let user = api.getUser();
    if (!user) {
        try {
            user = await api.me();
            api.setUser(user);
        } catch {
            api.removeToken();
            window.location.href = '/login.html';
            return null;
        }
    }
    return user;
}

function renderNavbar(user, activePage) {
    const currentProject = currentProjectFromStorage();
    const isAdmin   = user?.role === 'admin';
    const displayName = user?.full_name || user?.username || '';
    const projectLink = currentProject ? getProjectRoute(currentProject) : '/index.html';
    const reportsLink = currentProject ? getProjectReportsRoute(currentProject) : '/index.html';
    const isProjectSelectionScreen = activePage === 'index';
    const showSitesLink = !isProjectSelectionScreen && currentProject?.module_key === 'ucn_sites_v1';
    const showReportsLink = !isProjectSelectionScreen && !!currentProject;
    const showDirectories = !isProjectSelectionScreen && isAdmin;
    const showAdminTools = isAdmin;
    const directoriesToggleId = 'navbarDirectoriesToggle';
    const userToggleId = 'navbarUserToggle';
    return `
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold d-flex align-items-center gap-2" href="/index.html">
                <i class="bi bi-broadcast-pin text-primary"></i>
                <span>RTKS Tracker</span>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="mainNav">
                <ul class="navbar-nav me-auto">
                    ${showSitesLink ? `
                    <li class="nav-item">
                        <a class="nav-link ${activePage === 'sites' ? 'active' : ''}" href="${projectLink}">
                            <i class="bi bi-table me-1"></i>Объекты
                        </a>
                    </li>` : ''}
                    ${showReportsLink ? `
                    <li class="nav-item">
                        <a class="nav-link ${activePage === 'reports' ? 'active' : ''}" href="${reportsLink}">
                            <i class="bi bi-bar-chart-line me-1"></i>Отчеты
                        </a>
                    </li>` : ''}
                    ${showDirectories ? `
                    <li class="nav-item dropdown">
                        <button class="nav-link dropdown-toggle bg-transparent border-0 ${['contractors','regions'].includes(activePage) ? 'active' : ''}"
                                type="button"
                                id="${directoriesToggleId}"
                                data-nav-dropdown-toggle="true"
                                aria-expanded="false">
                            <i class="bi bi-card-list me-1"></i>Справочники
                        </button>
                        <ul class="dropdown-menu" data-nav-dropdown-menu="true" aria-labelledby="${directoriesToggleId}">
                            <li>
                                <a class="dropdown-item ${activePage === 'contractors' ? 'active' : ''}" href="/contractors.html">
                                    <i class="bi bi-building me-2"></i>Подрядчики
                                </a>
                            </li>
                            <li>
                                <a class="dropdown-item ${activePage === 'regions' ? 'active' : ''}" href="/regions.html">
                                    <i class="bi bi-geo-alt me-2"></i>Регионы
                                </a>
                            </li>
                        </ul>
                    </li>` : ''}
                    ${showAdminTools ? `
                    <li class="nav-item">
                        <a class="nav-link ${activePage === 'users' ? 'active' : ''}" href="/users.html">
                            <i class="bi bi-people me-1"></i>Пользователи
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link ${activePage === 'logs' ? 'active' : ''}" href="/logs.html">
                            <i class="bi bi-journal-text me-1"></i>Логи
                        </a>
                    </li>` : ''}
                </ul>
                <ul class="navbar-nav">
                    <li class="nav-item dropdown">
                        <button class="nav-link dropdown-toggle d-flex align-items-center gap-2 bg-transparent border-0"
                                type="button"
                                id="${userToggleId}"
                                data-nav-dropdown-toggle="true"
                                aria-expanded="false">
                            <i class="bi bi-person-circle"></i>
                            <span>${displayName}</span>
                            ${roleBadge(user?.role)}
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end" data-nav-dropdown-menu="true" aria-labelledby="${userToggleId}">
                            ${currentProject ? `
                            <li>
                                <span class="dropdown-item-text small text-muted">
                                    Проект: ${currentProject.name}
                                </span>
                            </li>
                            <li>
                                <span class="dropdown-item-text small text-muted">
                                    ${moduleLabel(currentProject.module_key)}
                                </span>
                                </li>
                            <li><hr class="dropdown-divider"></li>` : ''}
                            <li>
                                <a class="dropdown-item ${activePage === 'profile' ? 'active' : ''}" href="/profile.html">
                                    <i class="bi bi-person-gear me-2"></i>Мой профиль
                                </a>
                            </li>
                            <li><hr class="dropdown-divider"></li>
                            ${!isProjectSelectionScreen ? `
                            <li>
                                <a class="dropdown-item" href="/index.html">
                                    <i class="bi bi-grid-1x2 me-2"></i>Сменить большой проект
                                </a>
                            </li>
                            ${isAdmin ? `
                            <li>
                                <a class="dropdown-item" href="/projects.html">
                                    <i class="bi bi-sliders me-2"></i>Управление проектами
                                </a>
                            </li>` : ''}
                            <li><hr class="dropdown-divider"></li>` : ''}
                            <li><span class="dropdown-item-text text-muted small">${user?.email || ''}</span></li>
                            <li><hr class="dropdown-divider"></li>
                            <li>
                                <a class="dropdown-item text-danger" href="#" onclick="logout(event)">
                                    <i class="bi bi-box-arrow-right me-2"></i>Выйти
                                </a>
                            </li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>`;
}

function setNavbarDropdownState(toggle, menu, isOpen) {
    if (toggle) {
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        toggle.classList.toggle('show', isOpen);
    }
    if (menu) {
        menu.classList.toggle('show', isOpen);
    }
}

function closeNavbarDropdowns(scope = document) {
    scope.querySelectorAll('[data-nav-dropdown-menu].show').forEach(menu => {
        const toggleId = menu.getAttribute('aria-labelledby');
        const toggle = toggleId ? document.getElementById(toggleId) : null;
        setNavbarDropdownState(toggle, menu, false);
    });
}

function bindNavbarDropdowns(container) {
    if (!container) return;

    container.querySelectorAll('[data-nav-dropdown-toggle]').forEach(toggle => {
        toggle.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();

            const menu = container.querySelector(
                `[data-nav-dropdown-menu][aria-labelledby="${toggle.id}"]`
            );
            if (!menu) return;

            const willOpen = !menu.classList.contains('show');
            closeNavbarDropdowns(document);
            if (willOpen) {
                setNavbarDropdownState(toggle, menu, true);
            }
        });
    });

    container.querySelectorAll('[data-nav-dropdown-menu]').forEach(menu => {
        menu.addEventListener('click', event => {
            event.stopPropagation();
            if (event.target.closest('a[href], button')) {
                closeNavbarDropdowns(document);
            }
        });
    });

    const globalScope = typeof window !== 'undefined' ? window : globalThis;
    if (globalScope.__rtksNavbarDropdownsBound) return;

    document.addEventListener('click', () => {
        closeNavbarDropdowns(document);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeNavbarDropdowns(document);
        }
    });
    globalScope.__rtksNavbarDropdownsBound = true;
}

function getBootstrapModal(target) {
    const element = typeof target === 'string'
        ? document.getElementById(target)
        : target;
    if (!element || typeof bootstrap === 'undefined' || !bootstrap?.Modal) {
        return null;
    }

    if (typeof bootstrap.Modal.getOrCreateInstance === 'function') {
        return bootstrap.Modal.getOrCreateInstance(element);
    }

    if (typeof bootstrap.Modal.getInstance === 'function') {
        const existing = bootstrap.Modal.getInstance(element);
        if (existing) return existing;
    }

    return new bootstrap.Modal(element);
}

function getModalElement(target) {
    return typeof target === 'string'
        ? document.getElementById(target)
        : target;
}

function ensureAppModalBackdrop() {
    let backdrop = document.querySelector('[data-app-modal-backdrop="true"]');
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop fade show';
        backdrop.dataset.appModalBackdrop = 'true';
        document.body.appendChild(backdrop);
    }
    return backdrop;
}

function cleanupAppModalBackdrop() {
    if (document.querySelector('.modal.show')) return;
    document.querySelectorAll('[data-app-modal-backdrop="true"]').forEach(el => el.remove());
    document.body.classList.remove('modal-open');
}

function showAppModal(target) {
    const element = getModalElement(target);
    if (!element) return false;

    const modal = getBootstrapModal(element);
    if (modal?.show) {
        try {
            modal.show();
        } catch {}
    }

    const isShown = element.classList.contains('show') || element.style.display === 'block';
    if (!isShown) {
        element.style.display = 'block';
        element.removeAttribute('aria-hidden');
        element.setAttribute('aria-modal', 'true');
        element.setAttribute('role', 'dialog');
        element.classList.add('show');
    }

    document.body.classList.add('modal-open');
    if (!document.querySelector('.modal-backdrop')) {
        ensureAppModalBackdrop();
    }
    return true;
}

function hideAppModal(target) {
    const element = getModalElement(target);
    if (!element) return false;

    const modal = getBootstrapModal(element);
    if (modal?.hide) {
        try {
            modal.hide();
        } catch {}
    }

    element.classList.remove('show');
    element.style.display = 'none';
    element.setAttribute('aria-hidden', 'true');
    element.removeAttribute('aria-modal');
    if (!document.querySelector('.modal.show')) {
        document.querySelectorAll('.modal-backdrop').forEach(backdrop => backdrop.remove());
        cleanupAppModalBackdrop();
    }
    return true;
}

function bindAppModalDismissals(scope = document) {
    scope.querySelectorAll('[data-bs-dismiss="modal"]').forEach(button => {
        if (button.dataset.appModalDismissBound === 'true') return;
        button.dataset.appModalDismissBound = 'true';
        button.addEventListener('click', event => {
            event.preventDefault();
            const modal = button.closest('.modal');
            hideAppModal(modal);
        });
    });
}

function setPageFlash(key, message, type = 'success') {
    if (!key || !message) return;
    try {
        sessionStorage.setItem(key, JSON.stringify({ message, type }));
    } catch {}
}

function consumePageFlash(key) {
    if (!key) return;
    try {
        const raw = sessionStorage.getItem(key);
        if (!raw) return;
        sessionStorage.removeItem(key);
        const flash = JSON.parse(raw);
        if (flash?.message) {
            showToast(flash.message, flash.type || 'success');
        }
    } catch {}
}

function mountNavbar(user, activePage, containerId = 'navbar-container') {
    const container = typeof containerId === 'string'
        ? document.getElementById(containerId)
        : containerId;
    if (!container) return null;

    closeNavbarDropdowns(document);
    container.innerHTML = renderNavbar(user, activePage);
    bindNavbarDropdowns(container);

    return container;
}

function logout(e) {
    if (e) e.preventDefault();
    api.removeToken();
    window.location.href = '/login.html';
}
