Refactor the given file into a module of the same name.

## Example

Take the following `commands.py` file as an example.

```python
CONSTANT_1 = "Constant 1"
CONSTANT_2 = "Constant 2"

class MyCommand:
    pass

class MyOtherCommand:
    pass

class YetAnotherCommand:
    pass
```

### Classes

1. Create a `commands` directory.
2. For each class in the original `commands.py` file, create a file and place the corresponding class there.

### Constants

1. Create a `commands/config.py` file.
2. Move all constants into the `config.py` file. Update each file to import the constants from the `config.py` file.

### **init**.py

1. Create a `commands/__init__.py` file.
2. Export the items in this module using `__all__`.

The `__init__.py` file should look like this:

```python
from .config import CONSTANT_1, CONSTANT_2
from .my-command import MyCommand
from .my-other-command import MyOtherCommand
from .yet-another-command import YetAnotherCommand

__all__ = [
    "CONSTANT_1",
    "CONSTANT_2",
    "MyCommand",
    "MyOtherCommand",
    "YetAnotherCommand",
]
```

### Final file structure

The final file structure should look like this:

```
commands/                   # `commands` module directory, same name as given file
- __init__.py               # Init file to expose other items within this module
- config.py                 # Config file for constants
- my-command.py             # For MyCommand
- my-other-command.py       # For MyOtherCommand
- yet-another-command.py    # For YetAnotherCommand
```
