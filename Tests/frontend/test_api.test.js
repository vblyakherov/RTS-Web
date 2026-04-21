const path = require('path');
const fs = require('fs');

const apiCode = fs.readFileSync(
    path.resolve(__dirname, '../../frontend/js/api.js'),
    'utf8'
);
eval(`${apiCode}\nglobalThis.__apiUnderTest = api;`); // eslint-disable-line no-eval
const apiUnderTest = globalThis.__apiUnderTest;

describe('formatApiErrorDetail', () => {
    test('разворачивает массив ошибок в читаемый текст', () => {
        const detail = [
            {
                loc: ['body', 'email'],
                msg: 'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.',
            },
        ];

        expect(formatApiErrorDetail(detail)).toContain('body.email');
        expect(formatApiErrorDetail(detail)).toContain('value is not a valid email address');
    });

    test('сохраняет строковую ошибку как есть', () => {
        expect(formatApiErrorDetail('Username already exists')).toBe('Username already exists');
    });
});

describe('reports api helpers', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('getReports проксирует запрос к /reports/ с project_id', async () => {
        const fetchSpy = jest.spyOn(apiUnderTest, 'fetch').mockResolvedValueOnce([{ key: 'status_overview' }]);

        const result = await apiUnderTest.getReports(42);

        expect(fetchSpy).toHaveBeenCalledWith('/reports/?project_id=42');
        expect(result).toEqual([{ key: 'status_overview' }]);
    });

    test('getReport проксирует запрос к detail-эндпоинту отчета', async () => {
        const payload = { key: 'milestone_readiness', title: 'Вехи УЦН' };
        const fetchSpy = jest.spyOn(apiUnderTest, 'fetch').mockResolvedValueOnce(payload);

        const result = await apiUnderTest.getReport(7, 'milestone_readiness');

        expect(fetchSpy).toHaveBeenCalledWith('/reports/milestone_readiness?project_id=7');
        expect(result).toEqual(payload);
    });
});
