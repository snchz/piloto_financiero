import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. CSS
if '.transition-all' not in html:
    html = html.replace('</style>', '    .transition-all { transition: all 0.3s ease; }\n    </style>')

# 2. Main Col
html = html.replace('<div class="col-xl-9 d-flex flex-column h-100">', '<div id="main-content-col" class="col-xl-9 col-lg-8 col-12 d-flex flex-column h-100 transition-all">')

# 3. Header Toggle Button
header_buttons_str = '''                <div class="d-flex align-items-center gap-3">
                    <button class="action-btn" onclick="abrirConfig()" title="Configuración" style="font-size: 1.25rem;">⚙️</button>'''

header_buttons_new = '''                <div class="d-flex align-items-center gap-3">
                    <button class="action-btn d-xl-none" onclick="toggleActivityPanel()" title="Alternar Actividad Reciente" style="font-size: 1.25rem;">🔔</button>
                    <button class="action-btn" onclick="abrirConfig()" title="Configuración" style="font-size: 1.25rem;">⚙️</button>'''
html = html.replace(header_buttons_str, header_buttons_new)

# Add a button in the right place inside the UI to let desktop users hide it too
header_buttons_desktop_new = '''                <div class="d-flex align-items-center gap-3">
                    <button class="action-btn" onclick="toggleActivityPanel()" title="Alternar Actividad Reciente" style="font-size: 1.25rem;">🔔</button>
                    <button class="action-btn" onclick="abrirConfig()" title="Configuración" style="font-size: 1.25rem;">⚙️</button>'''
html = html.replace(header_buttons_new, header_buttons_desktop_new)

# 4. End of main col
html = html.replace('</div> <!-- End col-xl-9 -->', '</div> <!-- End main-content-col -->')

# 5. Side Col
# Initially visible on large screens, hidden on small screens?
# Actually, the user says "puede ser desplegada o no segun se prefiera"
# So let's make it standard display. We can add a class that hides it on mobile by default, but wait, the toggle button handles everything.
# Let's hide it by default on mobile, show on desktop.
html = html.replace('<div class="col-xl-3 d-flex flex-column h-100">', '<div id="activity-panel-col" class="col-xl-3 col-lg-4 col-12 d-flex flex-column h-100 transition-all d-none d-lg-flex">')

# 6. JS Function
js_code = '''
        window.toggleActivityPanel = () => {
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
        };

        // Initialize defaults'''

html = html.replace('// Initialize defaults', js_code)

# 7. Add offcanvas/responsiveness to table
if '<table class="table table-borderless align-middle">' in html:
    html = html.replace('<table class="table table-borderless align-middle">', '<div class="table-responsive"><table class="table table-borderless align-middle" style="min-width: 800px;">')
    html = html.replace('</table>\n                    </div>\n                </div>', '</table></div>\n                    </div>\n                </div>')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
