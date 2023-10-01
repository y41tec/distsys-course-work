import pathlib

def rmtree(path):
    for child in path.iterdir():
        if child.is_file():
            child.unlink()
        else:
            rmtree(child)
    path.rmdir()

def get_body_chunks(stream, chunk_size, size):
    while size > 0:
        yield stream.read(min(size, chunk_size))
        size -= chunk_size