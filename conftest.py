"""Conftest: coloca src/ no path para os testes importarem os módulos."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
