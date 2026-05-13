with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Remove CSS class
html = html.replace('.transition-all { transition: all 0.3s ease; }', '')

# Remove from divs
html = html.replace('class="col-xl-9 col-lg-8 col-12 d-flex flex-column h-100 transition-all"', 'class="col-xl-9 col-lg-8 col-12 d-flex flex-column h-100"')
html = html.replace('class="offcanvas-lg offcanvas-end col-xl-3 col-lg-4 transition-all"', 'class="offcanvas-lg offcanvas-end col-xl-3 col-lg-4"')

# Replace JS logic
old_js = """        window.toggleActivityPanel = () => {
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

new_js = """        window.toggleActivityPanel = () => {
            const mainCol = document.getElementById('main-content-col');
            const activityCol = document.getElementById('activity-panel-col');
            
            if (window.innerWidth < 992) {
                // Mobile: toggle offcanvas
                const bsOffcanvas = bootstrap.Offcanvas.getInstance(activityCol) || new bootstrap.Offcanvas(activityCol);
                bsOffcanvas.toggle();
            } else {
                // Desktop: toggle grid columns
                if (activityCol.style.display === 'none') {
                    // Show
                    activityCol.style.setProperty('display', '', '');
                    mainCol.className = 'col-xl-9 col-lg-8 col-12 d-flex flex-column h-100';
                } else {
                    // Hide
                    activityCol.style.setProperty('display', 'none', 'important');
                    mainCol.className = 'col-12 d-flex flex-column h-100';
                }
            }
        };"""

html = html.replace(old_js, new_js)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
