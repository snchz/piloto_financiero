with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update the HTML structure of the activity panel to use Bootstrap's offcanvas-lg
old_panel = """            <!-- Panel Lateral Actividad Reciente -->
            <div id="activity-panel-col" class="col-xl-3 col-lg-4 col-12 d-flex flex-column h-100 transition-all d-none d-lg-flex">
                <div class="glass-panel p-4 d-flex flex-column h-100">
                    <h5 class="mb-4 fs-6 text-uppercase text-secondary" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                    <div id="alerts-feed" class="alerts-feed flex-grow-1 overflow-auto">
                        <div class="text-secondary small">Sin actividad reciente</div>
                    </div>
                </div>
            </div>"""

new_panel = """            <!-- Panel Lateral Actividad Reciente -->
            <div id="activity-panel-col" class="offcanvas-lg offcanvas-end col-xl-3 col-lg-4 transition-all" tabindex="-1">
                <div class="offcanvas-header d-lg-none glass-panel border-bottom-0 rounded-bottom-0 mb-0 pb-0" style="background: var(--bg-surface);">
                    <h5 class="offcanvas-title text-secondary fs-6 text-uppercase" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas" data-bs-target="#activity-panel-col"></button>
                </div>
                <div class="offcanvas-body p-0 d-flex flex-column h-100">
                    <div class="glass-panel p-4 d-flex flex-column h-100 border-top-0 w-100">
                        <h5 class="mb-4 fs-6 text-uppercase text-secondary d-none d-lg-block" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                        <div id="alerts-feed" class="alerts-feed flex-grow-1 overflow-auto">
                            <div class="text-secondary small">Sin actividad reciente</div>
                        </div>
                    </div>
                </div>
            </div>"""

html = html.replace(old_panel, new_panel)

# 2. Update the Javascript logic
old_js = """        window.toggleActivityPanel = () => {
            const mainCol = document.getElementById('main-content-col');
            const activityCol = document.getElementById('activity-panel-col');
            
            // Toggle classes
            if (activityCol.classList.contains('d-none')) {
                // Show
                activityCol.classList.remove('d-none');
                activityCol.classList.add('d-flex');
                
                // Update main col classes
                mainCol.className = 'col-xl-9 col-lg-8 col-12 d-flex flex-column h-100 transition-all';
            } else {
                // Hide
                activityCol.classList.remove('d-flex', 'd-lg-flex');
                activityCol.classList.add('d-none');
                
                // Expand main col
                mainCol.className = 'col-12 d-flex flex-column h-100 transition-all';
            }
        };"""

new_js = """        window.toggleActivityPanel = () => {
            const mainCol = document.getElementById('main-content-col');
            const activityCol = document.getElementById('activity-panel-col');
            
            if (window.innerWidth < 992) {
                // Mobile: toggle offcanvas
                const bsOffcanvas = bootstrap.Offcanvas.getInstance(activityCol) || new bootstrap.Offcanvas(activityCol);
                bsOffcanvas.toggle();
            } else {
                // Desktop: toggle grid columns
                if (activityCol.classList.contains('d-lg-none')) {
                    // Show
                    activityCol.classList.remove('d-lg-none');
                    mainCol.className = 'col-xl-9 col-lg-8 col-12 d-flex flex-column h-100 transition-all';
                } else {
                    // Hide
                    activityCol.classList.add('d-lg-none');
                    mainCol.className = 'col-12 d-flex flex-column h-100 transition-all';
                }
            }
        };"""

html = html.replace(old_js, new_js)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
