import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Modify container
html = html.replace('<div class="container py-5">', 
                    '<div class="container-fluid py-4 px-4 h-100 d-flex flex-column" style="min-height: 100vh;">\n        <div class="row h-100 g-4 flex-grow-1">\n            <div class="col-xl-9 d-flex flex-column h-100">')

# 2. Extract and remove Actividad Reciente block from nav-alertas
html = re.sub(r'<div class="col-xl-4">\s*<div class="glass-panel p-4 h-100">\s*<h5[^>]*>Actividad Reciente.*?</div>\s*</div>\s*</div>', '', html, flags=re.DOTALL)

# 3. Clean up the col-xl-8 from nav-alertas so it uses full width
html = html.replace('<div class="col-xl-8">', '<div class="d-flex flex-column h-100">')

# 4. We need to add an extra closing div for col-xl-9 and then add the new right panel before the config modal.
# Find the end of the tab-content which is before config modal
right_panel = """            </div> <!-- End col-xl-9 -->
            
            <!-- Panel Lateral Actividad Reciente -->
            <div class="col-xl-3 d-flex flex-column h-100">
                <div class="glass-panel p-4 d-flex flex-column h-100">
                    <h5 class="mb-4 fs-6 text-uppercase text-secondary" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                    <div id="alerts-feed" class="alerts-feed flex-grow-1 overflow-auto">
                        <div class="text-secondary small">Sin actividad reciente</div>
                    </div>
                </div>
            </div>
        </div> <!-- End row -->
    </div> <!-- End container-fluid -->
"""

html = html.replace('        </div>\n    </div>\n\n    <!-- Config Modal -->', f'        </div>\n{right_panel}\n\n    <!-- Config Modal -->')

# 5. Fix Javascript for date and time layout in recent activity
html = html.replace('const html = alertas.map(a => `\n                    <div class="alert-item">\n                        <span class="opacity-75 font-monospace me-2" style="font-size:0.75rem">[${a.time}]</span>',
                    'const html = alertas.map(a => `\n                    <div class="alert-item">\n                        <div class="opacity-75 font-monospace mb-1" style="font-size:0.75rem">[${a.time}]</div>')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
