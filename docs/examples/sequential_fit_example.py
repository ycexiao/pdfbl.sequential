from pathlib import Path

from pdfbl.sequential.sequential_cmi_runner import SequentialCMIRunner


def main():
    working_dir = Path(__file__).parent
    input_files_folder = working_dir / "input_files"
    output_folder = working_dir / "results"
    input_files_folder.mkdir(exist_ok=True)
    output_folder.mkdir(exist_ok=True)
    sts = SequentialCMIRunner()
    sts.load_inputs(
        input_data_dir=str(input_files_folder),
        structure_path=str(working_dir / "Ni.cif"),
        output_result_dir=str(output_folder),
        filename_order_pattern=r"(\d+)K\.gr",
        refinable_variable_names=[
            "a_phase_1",
            "s0",
            "Uiso_phase_1_atom_1",
            "delta2_phase_1",
            "qdamp",
            "qbroad",
        ],
        initial_variable_values={
            "s0": 0.4,
            "qdamp": 0.04,
            "qbroad": 0.02,
            "a_phase_1": 3.52,
            "Uiso_phase_1_atom_1": 0.005,
            "delta2_phase_1": 2,
        },
        xmin=1.5,
        xmax=25.0,
        dx=0.01,
        qmax=25,
        qmin=0.1,
        # whether_plot_y=True,
        # whether_plot_ycalc=True,
        # plot_variable_names=["a_1"],
        # plot_result_names=["residual"],
        plot_intermediate_result_names=["residual"],
    )

    # Uncomment when "Ni_PDF_20250922-222655_ca8ae7_14K_result.json" is
    # available
    # sts.set_start_input_file(
    #     "Ni_PDF_20250922-222655_ca8ae7_14K.gr",
    #     input_filename_to_result_filename=lambda input_filename: input_filename.replace(  # noqa E501
    #         ".gr", "_result.json"
    #     ),
    # )
    sts.run(mode="stream")


if __name__ == "__main__":
    main()
