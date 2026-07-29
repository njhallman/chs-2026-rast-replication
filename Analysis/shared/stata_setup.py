"""
Initialize Stata via pystata and optionally install Stata packages.
"""
import os
import platform
import time


def init_stata(install_packages=False):
    """
    Configure and return the pystata stata module.

    Parameters
    ----------
    install_packages : bool
        If True, install required Stata packages (estout, reghdfe, etc.).
        Only needed on first run or after a Stata reinstall.
    """
    if platform.system() == 'Darwin':
        STATA_DIR = '/Applications/Stata/'
        STATA_EDITION = 'se'
        if not os.path.isdir(STATA_DIR):
            raise FileNotFoundError(
                'Stata not found at /Applications/Stata/. Please install Stata SE for macOS.'
            )
    else:
        # Linux: assume Stata already installed
        STATA_DIR = '/usr/local/stata'
        STATA_EDITION = 'se'
        if not os.path.isdir(STATA_DIR):
            raise FileNotFoundError(
                f'Stata not found at {STATA_DIR}. Install and license Stata first.'
            )

    try:
        import stata_setup
    except ImportError as exc:
        raise RuntimeError(
            "The stata_setup package is missing. Install the pinned project "
            "dependencies before running the analysis."
        ) from exc
    stata_setup.config(STATA_DIR, STATA_EDITION, splash=False)
    from pystata import stata

    if install_packages:
        packages = ['estout', 'require', 'reghdfe', 'ftools', 'outreg2', 'coefplot', 'ppmlhdfe']
        for package in packages:
            try:
                _run_stata_command(stata, f'ssc install {package}, replace')
            except Exception as e:
                print(f'Note: {package} install returned: {e}')

    return stata


def _run_stata_command(stata, cmd, max_retries=3):
    for attempt in range(max_retries):
        try:
            stata.run(cmd)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)
