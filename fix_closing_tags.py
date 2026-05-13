with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

target = '''            </main>
        </div>
        </div>
            </div> <!-- End main-content-col -->

            </div> <!-- End row -->
    </div> <!-- End container-fluid -->'''

replacement = '''            </main>
        </div> <!-- End nav-operaciones -->
    </div> <!-- End nav-tabContent -->
    </div> <!-- End main-content-col -->
  </div> <!-- End row -->
</div> <!-- End container-fluid -->'''

html = html.replace(target, replacement)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
