import pathlib

def rmtree(path):
    for child in path.iterdir():
        if child.is_file():
            child.unlink()
        else:
            rmtree(child)
    path.rmdir()
