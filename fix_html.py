with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
clean_lines = []
for line in lines:
    if 'window.toggleActivityPanel = () => {' in line:
        break
    clean_lines.append(line)

# Now add exactly the block we want at the end
final_block = """        window.toggleActivityPanel = () => {
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

        // Initialize defaults
        document.addEventListener('DOMContentLoaded', () => {
            const today = new Date();
            const fechaInput = document.getElementById('op-fecha');
            if(fechaInput) fechaInput.valueAsDate = today;
        });

    </script>
</body>
</html>
"""

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)
    f.write(final_block)
