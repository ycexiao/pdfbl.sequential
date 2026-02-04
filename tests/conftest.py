import pytest


@pytest.fixture
def user_filesystem(tmp_path):
    base_dir = tmp_path
    empty_folder = base_dir / "empty_folder"
    empty_folder.mkdir()
    input_data_folder = base_dir / "input_data_dir"
    input_data_folder.mkdir()
    for i in range(5):
        input_file = input_data_folder / f"Ni_PDF_{(i+1)*10}K.gr"
        input_file.write_text("Sample data content")
    yield base_dir
