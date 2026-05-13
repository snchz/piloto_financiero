import re

def refactor_operaciones_form():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Extract the form HTML
    form_start = html.find('<!-- Formulario de Operaciones -->')
    form_end = html.find('<!-- Resumen Cartera -->')
    
    if form_start == -1 or form_end == -1:
        print("Could not find form")
        return
        
    form_html = html[form_start:form_end]
    
    # Remove it from the original place
    html = html.replace(form_html, '')
    
    # 2. Add an "Añadir Operación" button to the Resumen Cartera or above it
    resumen_target = '<!-- Resumen Cartera -->'
    resumen_replacement = '''<!-- Resumen Cartera -->
                    <button class="btn btn-primary w-100 mb-4 py-2 fw-semibold shadow-sm" data-bs-toggle="modal" data-bs-target="#opModal">
                        ➕ Añadir Operación
                    </button>
                    '''
    html = html.replace(resumen_target, resumen_replacement)
    
    # 3. Create the Modal HTML
    # We need to extract the actual <form> tag from form_html
    form_content_match = re.search(r'(<form id="op-form" class="row g-3">.*?</form>)', form_html, re.DOTALL)
    if form_content_match:
        form_content = form_content_match.group(1)
        
        modal_html = f'''
    <!-- Operacion Modal -->
    <div class="modal fade" id="opModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content glass-panel" style="background: var(--bg-surface);">
                <div class="modal-header border-bottom-0">
                    <h5 class="modal-title">➕ Registrar Operación</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body pt-0">
                    {form_content}
                </div>
            </div>
        </div>
    </div>
'''
        # Insert before Config Modal
        config_modal_idx = html.find('<!-- Config Modal -->')
        html = html[:config_modal_idx] + modal_html + '\n    ' + html[config_modal_idx:]
    
    # 4. In JS, hide the modal after submitting successfully
    # Look for UI.showToast('Operación registrada');
    js_target = "UI.showToast('Operación registrada');"
    js_replacement = "UI.showToast('Operación registrada');\n                bootstrap.Modal.getInstance(document.getElementById('opModal'))?.hide();"
    
    html = html.replace(js_target, js_replacement)
    
    # Add a global initialization for opModal just in case
    # Actually Bootstrap auto-initializes if we just use getInstance or we can just hide it
    # But to be safe:
    js_init_target = "editModal = new bootstrap.Modal(document.getElementById('editModal'));"
    js_init_replacement = js_init_target + "\n            new bootstrap.Modal(document.getElementById('opModal'));"
    html = html.replace(js_init_target, js_init_replacement)

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    refactor_operaciones_form()
