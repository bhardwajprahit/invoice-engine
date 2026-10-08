import hashlib
from pathlib import Path


def calculate_file_hash(file_path):
    """
    Create a unique fingerprint for a file based on its contents.
    """

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def find_duplicate_files(files):
    """
    Find files that contain exactly the same data.

    Returns:
        unique_files
        duplicate_files
    """

    hashes = {}
    unique_files = []
    duplicate_files = []

    for file_path in files:

        file_hash = calculate_file_hash(
            file_path
        )

        if file_hash in hashes:

            duplicate_files.append(
                {
                    "file_name": file_path.name,
                    "duplicate_of": hashes[file_hash],
                    "hash": file_hash
                }
            )

        else:

            hashes[file_hash] = file_path.name
            unique_files.append(file_path)

    return unique_files, duplicate_files
