import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add CSS for active tabs
if '.nav-tabs .nav-link.active' not in html:
    html = html.replace('</style>', '''
        .nav-tabs .nav-link {
            border-bottom: 2px solid transparent !important;
            color: var(--text-secondary) !important;
        }
        .nav-tabs .nav-link.active {
            border-bottom-color: var(--accent) !important;
            color: var(--text-primary) !important;
        }
    </style>''')

# 2. Remove the bell button
header_buttons_desktop_new = '''                <div class="d-flex align-items-center gap-3">
                    <button class="action-btn" onclick="toggleActivityPanel()" title="Alternar Actividad Reciente" style="font-size: 1.25rem;">🔔</button>
                    <button class="action-btn" onclick="abrirConfig()" title="Configuración" style="font-size: 1.25rem;">⚙️</button>'''

header_buttons_clean = '''                <div class="d-flex align-items-center gap-3">
                    <button class="action-btn" onclick="abrirConfig()" title="Configuración" style="font-size: 1.25rem;">⚙️</button>'''
html = html.replace(header_buttons_desktop_new, header_buttons_clean)

# 3. Rewrite tabs
old_tabs = '''            <ul class="nav nav-tabs border-bottom-0 gap-2" id="myTab" role="tablist">
              <li class="nav-item" role="presentation">
                <button class="nav-link active bg-transparent border-0 text-secondary px-0 pb-3 fw-semibold" id="alertas-tab" data-bs-toggle="tab" data-bs-target="#nav-alertas" type="button" role="tab" style="border-bottom: 2px solid var(--accent) !important; color: var(--text-primary) !important;" onclick="this.style.color='var(--text-primary)';this.style.borderBottomColor='var(--accent)!important';document.getElementById('operaciones-tab').style.color='var(--text-secondary)';document.getElementById('operaciones-tab').style.borderBottomColor='transparent!important';">Monitores y Alertas</button>
              </li>
              <li class="nav-item ms-4" role="presentation">
                <button class="nav-link bg-transparent border-0 text-secondary px-0 pb-3 fw-semibold" id="operaciones-tab" data-bs-toggle="tab" data-bs-target="#nav-operaciones" type="button" role="tab" style="border-bottom: 2px solid transparent !important;" onclick="this.style.color='var(--text-primary)';this.style.borderBottomColor='var(--accent)!important';document.getElementById('alertas-tab').style.color='var(--text-secondary)';document.getElementById('alertas-tab').style.borderBottomColor='transparent!important'; cargarOperaciones();">Operaciones y Cartera</button>
              </li>
            </ul>'''

new_tabs = '''            <ul class="nav nav-tabs border-bottom-0 gap-2" id="myTab" role="tablist">
              <li class="nav-item" role="presentation">
                <button class="nav-link active bg-transparent border-0 px-0 pb-3 fw-semibold" id="actividad-tab" data-bs-toggle="tab" data-bs-target="#nav-actividad" type="button" role="tab">Actividad Reciente</button>
              </li>
              <li class="nav-item ms-4" role="presentation">
                <button class="nav-link bg-transparent border-0 px-0 pb-3 fw-semibold" id="alertas-tab" data-bs-toggle="tab" data-bs-target="#nav-alertas" type="button" role="tab">Monitores y Alertas</button>
              </li>
              <li class="nav-item ms-4" role="presentation">
                <button class="nav-link bg-transparent border-0 px-0 pb-3 fw-semibold" id="operaciones-tab" data-bs-toggle="tab" data-bs-target="#nav-operaciones" type="button" role="tab" onclick="cargarOperaciones();">Operaciones y Cartera</button>
              </li>
            </ul>'''
html = html.replace(old_tabs, new_tabs)

# Fix possible case where single quotes were different
html = re.sub(r'<ul class="nav nav-tabs border-bottom-0 gap-2" id="myTab" role="tablist">.*?</ul>', new_tabs, html, flags=re.DOTALL)

# 4. Extract Actividad Reciente Block
activity_panel_match = re.search(r'<!-- Panel Lateral Actividad Reciente -->(.*?)</div> <!-- End row -->', html, re.DOTALL)
if activity_panel_match:
    html = html.replace(activity_panel_match.group(0), '</div> <!-- End row -->')

# 5. Make main content full width
html = html.replace('<div id="main-content-col" class="col-xl-9 col-lg-8 col-12 d-flex flex-column h-100">', '<div id="main-content-col" class="col-12 d-flex flex-column h-100">')
# Just in case the replace above failed due to class order
html = re.sub(r'<div id="main-content-col" class="[^"]+">', '<div id="main-content-col" class="col-12 d-flex flex-column h-100">', html)


# 6. Add tab panes
# The current tabs start at:
# <div class="tab-pane fade show active h-100" id="nav-alertas" role="tabpanel" aria-labelledby="alertas-tab">
# Change nav-alertas to not be active anymore
html = html.replace('<div class="tab-pane fade show active h-100" id="nav-alertas" role="tabpanel" aria-labelledby="alertas-tab">', '<div class="tab-pane fade h-100" id="nav-alertas" role="tabpanel" aria-labelledby="alertas-tab">')

new_tab_pane = '''        <div class="tab-content h-100" id="nav-tabContent">
            <!-- Tab Actividad -->
            <div class="tab-pane fade show active h-100" id="nav-actividad" role="tabpanel" aria-labelledby="actividad-tab">
                <main class="row g-4 h-100">
                    <div class="col-12 d-flex flex-column">
                        <div class="glass-panel p-4 d-flex flex-column flex-grow-1">
                            <div class="d-flex justify-content-between align-items-center mb-4">
                                <h5 class="m-0 fs-6 text-uppercase text-secondary" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                            </div>
                            <div id="alerts-feed" class="alerts-feed flex-grow-1 overflow-auto" style="max-height: none;">
                                <div class="text-secondary small">Sin actividad reciente</div>
                            </div>
                        </div>
                    </div>
                </main>
            </div>
            
            <div class="tab-pane fade h-100" id="nav-alertas" role="tabpanel" aria-labelledby="alertas-tab">'''
            
html = html.replace('''        <div class="tab-content h-100" id="nav-tabContent">
            <div class="tab-pane fade h-100" id="nav-alertas" role="tabpanel" aria-labelledby="alertas-tab">''', new_tab_pane)


# 7. Remove toggle function
toggle_js = re.search(r'window\.toggleActivityPanel = \(\) => \{.*?\};\n\n', html, re.DOTALL)
if toggle_js:
    html = html.replace(toggle_js.group(0), '')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
