/**
 * Main Application Bootstrapper
 * Inicialización de componentes, eventos de navegación y gráficos
 */

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar fecha de hoy en formulario
    const fechaInput = document.getElementById('op-fecha');
    if (fechaInput && !fechaInput.value) {
        fechaInput.valueAsDate = new Date();
    }

    // Cargar datos principales
    if (typeof window.cargarOperaciones === 'function') {
        window.cargarOperaciones();
    }
    if (typeof window.cargarFire === 'function') {
        window.cargarFire();
    }

    // Auto-resize de gráficos Chart.js al cambiar de pestaña
    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(tabBtn => {
        tabBtn.addEventListener('shown.bs.tab', (e) => {
            if (e.target.id === 'resumen-tab') {
                if (window.equityCurveChartInstance) window.equityCurveChartInstance.resize();
                if (window.allocationChartInstance) window.allocationChartInstance.resize();
                if (window.currencyChartInstance) window.currencyChartInstance.resize();
            } else if (e.target.id === 'fire-tab') {
                if (window.fireChartInstance) window.fireChartInstance.resize();
                if (typeof window.cargarFire === 'function') window.cargarFire();
            }
        });
    });

    // Cerrar dialogos al hacer clic fuera (excepto opModal)
    document.querySelectorAll('dialog').forEach(dialog => {
        dialog.addEventListener('click', (e) => {
            if (dialog.id === 'opModal') return;
            const rect = dialog.getBoundingClientRect();
            if (e.clientY < rect.top || e.clientY > rect.bottom || e.clientX < rect.left || e.clientX > rect.right) {
                dialog.close();
            }
        });
    });

    // Tooltips Bootstrap
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Cargar hora de última actualización
    if (window.UI && typeof window.UI.loadLastRefreshTime === 'function') {
        window.UI.loadLastRefreshTime();
    }
});
