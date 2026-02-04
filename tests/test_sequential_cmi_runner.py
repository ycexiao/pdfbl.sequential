from pathlib import Path

import pytest

from pdfbl.sequential.sequential_cmi_runner import SequentialCMIRunner


def test_load_inputs_bad(user_filesystem):
    non_existing_folder = user_filesystem / "non_existing_folder"
    result_folder = user_filesystem / "empty_folder"
    input_data_folder = Path(__file__).parent / "data" / "input_data_dir"
    structure_path = Path(__file__).parent / "data" / "Ni.cif"
    # C1: non-existing input folder.
    #   Expect FileNotFoundError.
    runner = SequentialCMIRunner()
    with pytest.raises(FileNotFoundError) as excinfo:
        runner.load_inputs(
            input_data_dir=str(non_existing_folder),
            structure_path=str(structure_path),
            output_result_dir=str(result_folder),
        )
    expected_error_msg = (
        f"Path '{str(non_existing_folder)}' for "
        "'input_data_dir' does not exist. Please check the "
        "provided path."
    )
    actual_error_msg = str(excinfo.value)
    assert actual_error_msg == expected_error_msg
    # C2: wrong pattern to extract the order to refine data files.
    #   Expect ValueError.
    runner = SequentialCMIRunner()
    with pytest.raises(ValueError) as excinfo:
        runner.load_inputs(
            input_data_dir=str(input_data_folder),
            structure_path=str(structure_path),
            output_result_dir=str(result_folder),
            filename_order_pattern=r"(\d+)K\.txt",  # wrong pattern
        )
    # C3: variable name not exists in recipe.
    #   Expect ValueError.
    runner = SequentialCMIRunner()
    with pytest.raises(ValueError) as excinfo:
        runner.load_inputs(
            input_data_dir=str(input_data_folder),
            structure_path=str(structure_path),
            output_result_dir=str(result_folder),
            refinable_variable_names=["non_existing_variable"],
        )
    expected_error_msg = (
        "Refinable variable 'non_existing_variable' not found in the "
        "recipe. Please choose from the existing variables: "
    )
    actual_error_msg = str(excinfo.value)
    assert expected_error_msg in actual_error_msg


def test_run_sequential_cmi_runner(user_filesystem):
    # C1: run the sequential CMI runner in batch mode.
    #   Expect result files are generated in the output folder.
    result_folder = user_filesystem / "empty_folder"
    input_data_folder = Path(__file__).parent / "data" / "input_data_dir"
    structure_path = Path(__file__).parent / "data" / "Ni.cif"
    refinable_variable_names = [
        "a_1",
        "s0",
        "Uiso_0_1",
        "delta2_1",
        "qdamp",
        "qbroad",
    ]
    initial_variable_values = {
        "s0": 0.4,
        "qdamp": 0.04,
        "qbroad": 0.02,
        "a_1": 3.52,
        "Uiso_0_1": 0.005,
        "delta2_1": 2,
    }
    runner = SequentialCMIRunner()
    runner.load_inputs(
        input_data_dir=str(input_data_folder),
        structure_path=str(structure_path),
        output_result_dir=str(result_folder),
        filename_order_pattern=r"(\d+)K\.gr",
        refinable_variable_names=refinable_variable_names,
        initial_variable_values=initial_variable_values,
        xmin=1.5,
        xmax=25.0,
        dx=0.01,
        qmax=25,
        qmin=0.1,
    )
    runner.run(mode="batch")
    result_file_path = (
        Path(result_folder) / "Ni_PDF_20250923-065606_148a45_300K_result.json"
    )
    print(list(result_folder.iterdir()))
    assert result_file_path.exists()
