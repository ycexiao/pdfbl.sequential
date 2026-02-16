import json
import re
import threading
import time
import warnings
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Literal

from bg_mpl_stylesheets.styles import all_styles
from matplotlib import pyplot as plt
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from pdfbl.sequential.pdfadapter import PDFAdapter

plt.style.use(all_styles["bg-style"])


class SequentialCMIRunner:
    def __init__(self):
        self.input_files_known = []
        self.input_files_completed = []
        self.input_files_running = []
        self.adapter = PDFAdapter()
        self.visualization_data = {}

    def _validate_inputs(self):
        for path_name in [
            "input_data_dir",
            "output_result_dir",
        ]:
            if not Path(self.inputs[path_name]).exists():
                raise FileNotFoundError(
                    f"Path '{self.inputs[path_name]}' for "
                    f"'{path_name}' does not exist. Please check the "
                    "provided path."
                )
            if not Path(self.inputs[path_name]).is_dir():
                raise NotADirectoryError(
                    f"Path '{self.inputs[path_name]}' for "
                    f"'{path_name}' is not a directory. Please check the "
                    "provided path."
                )
        if not Path(self.inputs["structure_path"]).exists():
            raise FileNotFoundError(
                f"Structure file '{self.inputs['structure_path']}' does not "
                "exist. Please check the provided path."
            )
        profile_files = list(Path(self.inputs["input_data_dir"]).glob("*"))
        if len(profile_files) > 0:  # skip variable checking if no input files
            for tmp_file_path in profile_files:
                matches = re.findall(
                    self.inputs["filename_order_pattern"], tmp_file_path.name
                )
                if len(matches) == 0:
                    raise ValueError(
                        f"Input file '{tmp_file_path}' does not match the "
                        "filename order pattern. Please check the pattern "
                        "or the input files."
                    )
            tmp_adatper = PDFAdapter()
            tmp_adatper.initialize_profile(str(tmp_file_path))
            tmp_adatper.initialize_structures([self.inputs["structure_path"]])
            tmp_adatper.initialize_contribution()
            tmp_adatper.initialize_recipe()
            allowed_variable_names = list(
                tmp_adatper.recipe._parameters.keys()
            )
            for var_name in self.inputs["refinable_variable_names"]:
                if var_name not in allowed_variable_names:
                    raise ValueError(
                        f"Refinable variable '{var_name}' not found in the "
                        "recipe. Please choose from the existing variables: "
                        f"{allowed_variable_names}"
                    )
            for var_name in self.inputs.get("plot_variable_names", []):
                if var_name not in allowed_variable_names:
                    raise ValueError(
                        f"Variable '{var_name}' is not found in the recipe. "
                        "Please choose from the existing variables: "
                        f"{allowed_variable_names}"
                    )
        else:
            warnings.warn(
                "No input profile files found in the input data directory. "
                "Skipping variable name validation."
            )
        allowed_result_entry_names = [
            "residual",
            "contributions",
            "restraints",
            "chi2",
            "reduced_chi2",
        ]
        for entry_name in self.inputs.get("plot_result_names", []):
            if entry_name not in allowed_result_entry_names:
                raise ValueError(
                    f"Result entry '{entry_name}' is not a valid entry to "
                    "plot. Please choose from the following entries: "
                    f"{allowed_result_entry_names}"
                )
        for entry_name in self.inputs.get(
            "plot_intermediate_result_names", []
        ):
            if entry_name not in allowed_result_entry_names:
                raise ValueError(
                    f"Intermediate result '{entry_name}' is not a valid "
                    "entry to plot. Please choose from the following "
                    "entries: "
                    f"{allowed_result_entry_names}"
                )

    def load_inputs(
        self,
        input_data_dir,
        structure_path,
        output_result_dir="results",
        filename_order_pattern=r"(\d+)K\.gr",
        whether_plot_y=False,
        whether_plot_ycalc=False,
        plot_variable_names=None,
        plot_result_names=None,
        plot_intermediate_result_names=None,
        refinable_variable_names=None,
        initial_variable_values=None,
        xmin=None,
        xmax=None,
        dx=None,
        qmin=None,
        qmax=None,
        show_plot=True,
    ):
        """Load and validate input configuration for sequential PDF
        refinement.

        This method initializes the sequential CMI runner with input data,
        structure information, and refinement parameters, and the plotting
        configuration.

        Parameters
        ----------
        input_data_dir : str
            The path to the directory containing input PDF profile files.
        structure_path : str
            The path to the structure file (e.g., CIF format) used for
            refinement.
        output_result_dir : str
            The path to the directory for storing refinement results.
            Default is "results".
        filename_order_pattern : str
            The regular expression pattern to extract ordering information
            from filenames.
            Default is r"(\d+)K\.gr" to extract temperature values from
            filenames.
        refinable_variable_names : list of str
            The list of variable names to refine.
            Must exist in the recipe.
            Default variable names are all possible variables that can
            be created from the input structure and profile.
        initial_variable_values : dict
            The dictionary mapping variable names to their initial values.
            Default is None.
        xmin : float
            The minimum x-value for the PDF profile.
            Default is the value parsed from the input file.
        xmax : float
            The maximum x-value for the PDF profile.
            Default is the value parsed from the input file.
        dx : float
            The step size for the PDF profile.
            Default is the value parsed from the input file.
        qmin : float
            The minimum q-value for the PDF profile.
            Default is the value parsed from the input file.
        qmax : float
            The maximum q-value for the PDF profile.
            Default is the value parsed from the input file.
        show_plot : bool
            Whether to display plots during refinement. Default is True.
        whether_plot_y : bool
            Whether to plot the experimental PDF data (y). Default is False.
        whether_plot_ycalc : bool
            Whether to plot the calculated PDF data (ycalc). Default is False.
        plot_variable_names : list of str
            The list of variable names to plot during refinement.
            Default is None.
        plot_result_names : list of str
            The list of fit result entries to plot.
            Allowed values: "residual", "contributions", "restraints", "chi2",
            "reduced_chi2". Default is None.
        plot_intermediate_result_names : list of str
            The list of intermediate result entries to plot during refinement.
            Allowed values: "residual", "contributions", "restraints", "chi2",
            "reduced_chi2". Default is None.

        Raises
        ------
        FileNotFoundError
            If the input data directory, output result directory, or structure
            file does not exist.
        NotADirectoryError
            If input_data_dir or output_result_dir is not a directory.
        ValueError
            If a refinable variable name is not found in the recipe, or if a
            plot result name is not valid.

        Examples
        --------
        >>> runner = SequentialCMIRunner()
        >>> runner.load_inputs(
        ...     input_data_dir="./data",
        ...     structure_path="./structure.cif",
        ...     output_result_dir="./results",
        ...     refinable_variable_names=["a", "all"],
        ...     plot_variable_names=["a"],
        ...     plot_result_names=["chi2"],
        ...     plot_intermediate_result_names=["residual"],
        ... )
        """  # noqa: W605
        self.inputs = {
            "input_data_dir": input_data_dir,
            "structure_path": structure_path,
            "output_result_dir": output_result_dir,
            "filename_order_pattern": filename_order_pattern,
            "xmin": xmin,
            "xmax": xmax,
            "dx": dx,
            "qmin": qmin,
            "qmax": qmax,
            "refinable_variable_names": refinable_variable_names or [],
            "initial_variable_values": initial_variable_values or {},
            "whether_plot_y": whether_plot_y,
            "whether_plot_ycalc": whether_plot_ycalc,
            "plot_variable_names": plot_variable_names or [],
            "plot_result_names": plot_result_names or [],
            "plot_intermediate_result_names": plot_intermediate_result_names
            or [],
        }
        self.show_plot = show_plot
        self._validate_inputs()
        self._initialize_plots()

    def _initialize_plots(self):
        whether_plot_y = self.inputs["whether_plot_y"]
        whether_plot_ycalc = self.inputs["whether_plot_ycalc"]
        plot_variable_names = self.inputs["plot_variable_names"]
        plot_result_names = self.inputs["plot_result_names"]
        plot_intermediate_result_names = self.inputs[
            "plot_intermediate_result_names"
        ]
        if whether_plot_y and whether_plot_ycalc:
            fig, _ = plt.subplots(2, 1)
            label = ["ycalc", "y"]
        elif whether_plot_ycalc or whether_plot_y:
            fig, _ = plt.subplots()
            if whether_plot_ycalc:
                label = ["ycalc"]
            else:
                label = ["y"]
        else:
            fig = None
        if fig:
            axes = fig.axes
            lines = []
            for i in range(len(axes)):
                (line,) = axes[i].plot(
                    [],
                    [],
                    label=label[i],
                    color=plt.rcParams["axes.prop_cycle"].by_key()["color"][i],
                )
                lines.append(line)
                self.visualization_data[label[i]] = {
                    "line": line,
                    "xdata": Queue(),
                    "ydata": Queue(),
                }
            fig.legend()
        names = ["variables", "results", "intermediate_results"]
        plot_tasks = [
            plot_variable_names,
            plot_result_names,
            plot_intermediate_result_names,
        ]
        for i in range(len(plot_tasks)):
            if plot_tasks[i] is not None:
                self.visualization_data[names[i]] = {}
                for var_name in plot_tasks[i]:
                    fig, ax = plt.subplots()
                    (line,) = ax.plot([], [], label=var_name, marker="o")
                    self.visualization_data[names[i]][var_name] = {
                        "line": line,
                        "buffer": [],
                        "ydata": Queue(),
                    }
                    fig.suptitle(f"{names[i].capitalize()}: {var_name}")
        if plot_intermediate_result_names is not None:
            for var_name in plot_intermediate_result_names:
                self.adapter.monitor_intermediate_results(
                    var_name,
                    step=10,
                    queue=self.visualization_data["intermediate_results"][
                        var_name
                    ]["ydata"],
                )

    def _update_plot(self):
        for key, plot_pack in self.visualization_data.items():
            if key in ["ycalc", "y"]:
                if not plot_pack["xdata"].empty():
                    line = plot_pack["line"]
                    xdata = plot_pack["xdata"].get()
                    ydata = plot_pack["ydata"].get()
                    line.set_xdata(xdata)
                    line.set_ydata(ydata)
                    line.axes.relim()
                    line.axes.autoscale_view()
            elif (
                key == "variables"
                or key == "results"
                or key == "intermediate_results"
            ):
                for _, data_pack in plot_pack.items():
                    if not data_pack["ydata"].empty():
                        line = data_pack["line"]
                        buffer = data_pack["buffer"]
                        new_y = data_pack["ydata"].get()
                        buffer.append(new_y)
                        xdata = list(range(1, len(buffer) + 1))
                        ydata = buffer
                        line.set_xdata(xdata)
                        line.set_ydata(ydata)
                        line.axes.relim()
                        line.axes.autoscale_view()

    def _check_for_new_data(self):
        input_data_dir = self.inputs["input_data_dir"]
        filename_order_pattern = self.inputs["filename_order_pattern"]
        files = [file for file in Path(input_data_dir).glob("*")]
        sorted_file = sorted(
            files,
            key=lambda file: int(
                re.findall(filename_order_pattern, file.name)[0]
            ),
        )
        if (
            self.input_files_known
            != sorted_file[: len(self.input_files_known)]
        ):
            raise RuntimeError(
                "Wrong order to run sequential toolset is detected. "
                "This is likely due to files appearing in the input directory "
                "in the wrong order. Please restart the sequential toolset."
            )
        if self.input_files_known == sorted_file:
            return
        self.input_files_known = sorted_file
        self.input_files_running = [
            f
            for f in self.input_files_known
            if f not in self.input_files_completed
        ]
        print(f"{[str(f) for f in self.input_files_running]} detected.")

    def set_start_input_file(
        self, input_filename, input_filename_to_result_filename
    ):
        """Set the starting input file for sequential refinement and
        continue the interrupted sequential refinement from that point.

        Parameters
        ----------
        input_filename : str
            The name of the input file to start from. This file must be in the
            input data directory.
        input_filename_to_result_filename : function
            The function that takes an input filename and returns the
            corresponding result filename. This is used to locate the last
            result file for loading variable values.
        """
        self._check_for_new_data()
        input_file_path = Path(self.inputs["input_data_dir"]) / input_filename
        if input_file_path not in self.input_files_known:
            raise ValueError(
                f"Input file {input_filename} not found in known input files."
            )
        start_index = self.input_files_known.index(input_file_path)
        self.input_files_completed = self.input_files_known[:start_index]
        self.input_files_running = self.input_files_known[start_index:]
        last_result_file = input_filename_to_result_filename(
            self.input_files_completed[-1].name
        )
        last_result_file = (
            Path(self.inputs["output_result_dir"]) / last_result_file
        )
        if not Path(last_result_file).exists():
            raise FileNotFoundError(
                f"Result file {last_result_file} not found. "
                "Cannot load last result variable values. "
                "Please check the provided function or use "
                "an earlier input file."
            )
        last_result_variables_values = json.load(open(last_result_file, "r"))[
            "variables"
        ]
        last_result_variables_values = {
            name: pack["value"]
            for name, pack in last_result_variables_values.items()
        }
        self.last_result_variables_values = last_result_variables_values
        print(f"Starting from input file: {self.input_files_running[0].name}")

    def _run_one_cycle(self, stop_event=SimpleNamespace(is_set=lambda: False)):
        self._check_for_new_data()
        xmin = self.inputs["xmin"]
        xmax = self.inputs["xmax"]
        dx = self.inputs["dx"]
        qmin = self.inputs["qmin"]
        qmax = self.inputs["qmax"]
        structure_path = self.inputs["structure_path"]
        output_result_dir = self.inputs["output_result_dir"]
        initial_variable_values = self.inputs["initial_variable_values"]
        refinable_variable_names = self.inputs["refinable_variable_names"]
        if not self.input_files_running:
            return None
        for input_file in self.input_files_running:
            if stop_event.is_set():
                break
            print(f"Processing {input_file.name}...")
            self.adapter.initialize_profile(
                str(input_file),
                xmin=xmin,
                xmax=xmax,
                dx=dx,
                qmin=qmin,
                qmax=qmax,
            )
            self.adapter.initialize_structures([structure_path])
            self.adapter.initialize_contribution()
            self.adapter.initialize_recipe()
            if not hasattr(self, "last_result_variables_values"):
                self.last_result_variables_values = initial_variable_values
            self.adapter.set_initial_variable_values(
                self.last_result_variables_values
            )
            if refinable_variable_names is None:
                refinable_variable_names = list(initial_variable_values.keys())
            self.adapter.refine_variables(refinable_variable_names)
            results = self.adapter.save_results(
                filename=str(
                    Path(output_result_dir) / f"{input_file.stem}_result.json"
                ),
                mode="dict",
            )
            self.last_result_variables_values = {
                name: pack["value"]
                for name, pack in results["variables"].items()
            }
            self.input_files_completed.append(input_file)
            if "ycalc" in self.visualization_data:
                xdata = self.adapter.recipe.pdfcontribution.profile.x
                ydata = self.adapter.recipe.pdfcontribution.profile.ycalc
                self.visualization_data["ycalc"]["xdata"].put(xdata)
                self.visualization_data["ycalc"]["ydata"].put(ydata)
            if "y" in self.visualization_data:
                xdata = self.adapter.recipe.pdfcontribution.profile.x
                ydata = self.adapter.recipe.pdfcontribution.profile.y
                self.visualization_data["y"]["xdata"].put(xdata)
                self.visualization_data["y"]["ydata"].put(ydata)
            for var_name in self.visualization_data.get("variables", {}):
                new_value = self.adapter.recipe._parameters[var_name].value
                self.visualization_data["variables"][var_name]["ydata"].put(
                    new_value
                )
            for entry_name in self.visualization_data.get("results", {}):
                fitresults_dict = self.adapter.save_results(mode="dict")
                entry_value = fitresults_dict.get(entry_name, None)
                self.visualization_data["results"][entry_name]["ydata"].put(
                    entry_value
                )
            print("Completed!")
        self.input_files_running = []

    def run(self, mode: Literal["batch", "stream"]):
        """Run the sequential refinement process in either batch or
        streaming mode.

        Parameters
        ----------
        mode : str
            The mode to run the sequential refinement. Must be either "batch"
            or "stream". In "batch" mode, the toolset will run through all
            available input files once and then stop. In "stream" mode, the
            runner will continuously monitor the input data directory for new
            files and process them as they appear, until the user decides
            to stop the process.
        """
        if mode == "batch":
            self._run_one_cycle()
            self._update_plot()
        elif mode == "stream":
            stop_event = threading.Event()
            session = PromptSession()
            if (self.visualization_data is not None) and self.show_plot:
                plt.ion()
                plt.pause(0.01)

            def stream_loop():
                while not stop_event.is_set():
                    self._run_one_cycle(stop_event)
                    stop_event.wait(1)  # Check for new data every 1s

            def input_loop():
                with patch_stdout():
                    print("=== COMMANDS ===")
                    print("Type STOP to exit")
                    print("================")
                    while not stop_event.is_set():
                        cmd = session.prompt("> ")
                        if cmd.strip() == "STOP":
                            stop_event.set()
                            print(
                                "Stopping the streaming sequential toolset..."
                            )
                        else:
                            print(
                                "Unrecognized input. "
                                "Please type 'STOP' to end."
                            )
                    visualization_data = {}
                    for (
                        category_name,
                        data_pack,
                    ) in self.visualization_data.items():
                        for var_name, var_pack in data_pack.items():
                            if "buffer" in var_pack:
                                visualization_data[category_name] = {
                                    var_name: var_pack["buffer"]
                                }
                    with open("visualization_data.json", "w") as f:
                        json.dump(visualization_data, f, indent=2)

            input_thread = threading.Thread(target=input_loop)
            input_thread.start()
            fit_thread = threading.Thread(target=stream_loop)
            fit_thread.start()
            while not stop_event.is_set():
                self._update_plot()
                plt.pause(0.01)
                time.sleep(1)
            fit_thread.join()
            input_thread.join()
        else:
            raise ValueError(f"Unknown mode: {mode}")
