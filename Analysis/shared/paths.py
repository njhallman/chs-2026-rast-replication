"""
Detect repo root and derive standard directory paths.
Works whether run from any subdirectory.
"""
import os


def _find_repo_dir():
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):
        if os.path.isdir(os.path.join(current, 'LaTeX', 'Tables')):
            return current
        current = os.path.dirname(current)
    raise RuntimeError(
        "Could not find repo root (looked for LaTeX/Tables/ directory). "
        "Are you running from inside the replication repository?"
    )


REPO_DIR = _find_repo_dir()
data_dir = os.path.join(REPO_DIR, 'Analysis', 'Data')
output_dir = os.environ.get('CHS_OUTPUT_DIR')
if output_dir:
    output_dir = os.path.abspath(output_dir)
    tables_dir = os.path.join(output_dir, 'Tables')
    figures_dir = os.path.join(output_dir, 'Figures')
else:
    tables_dir = os.path.join(REPO_DIR, 'LaTeX', 'Tables')
    figures_dir = os.path.join(REPO_DIR, 'LaTeX', 'Figures')

if __name__ == '__main__':
    print(f'REPO_DIR:    {REPO_DIR}')
    print(f'data_dir:    {data_dir}')
    print(f'tables_dir:  {tables_dir}')
    print(f'figures_dir: {figures_dir}')
