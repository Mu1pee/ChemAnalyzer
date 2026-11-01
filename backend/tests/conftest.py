import sys
from pathlib import Path

# Чтобы `import app` работал при запуске pytest из любой папки.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
