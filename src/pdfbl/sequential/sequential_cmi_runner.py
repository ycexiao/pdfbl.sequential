import json
import re
import threading
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Literal

from bg_mpl_stylesheets.styles import all_styles
from diffpy.srfit.fitbase import FitResults
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
        self.data_for_plot = {}

    def validate_inputs(self):
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
        for tmp_file_path in Path(self.inputs["input_data_dir"]).glob("*"):
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
        tmp_adatper.init_profile(str(tmp_file_path))
        tmp_adatper.init_structures([self.inputs["structure_path"]])
        tmp_adatper.init_contribution()
        tmp_adatper.init_recipe()
        allowed_variable_names = list(tmp_adatper.recipe._parameters.keys())
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
        allowed_result_entry_names = [
            "residual",
            "contributions",
            "restraints",
            "chi2",
            "reduced_chi2",
        ]
        for entry_name in self.inputs.get("plot_result_entry_names", []):
            if entry_name not in allowed_result_entry_names:
                raise ValueError(
                    f"Result entry '{entry_name}' is not a valid entry to "
                    "plot. Please choose from the following entries: "
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
        plot_result_entry_names=None,
        refinable_variable_names=None,
        initial_variable_values=None,
        xmin=None,
        xmax=None,
        dx=None,
        qmin=None,
        qmax=None,
        show_plot=True,
    ):
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
            "plot_result_entry_names": plot_result_entry_names or [],
        }
        self.show_plot = show_plot
        self.validate_inputs()
        if self.show_plot:
            self.init_plots()

    def init_plots(self):
        if not self.show_plot:
            return
        whether_plot_y = self.inputs["whether_plot_y"]
        whether_plot_ycalc = self.inputs["whether_plot_ycalc"]
        plot_variable_names = self.inputs["plot_variable_names"]
        plot_result_entry_names = self.inputs["plot_result_entry_names"]
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
                self.data_for_plot[label[i]] = {
                    "line": line,
                    "xdata": Queue(),
                    "ydata": Queue(),
                }
            fig.legend()
        if plot_variable_names:
            self.data_for_plot["variables"] = {}
            for var_name in plot_variable_names:
                fig, ax = plt.subplots()
                (line,) = ax.plot([], [], label=var_name, marker="o")
                self.data_for_plot["variables"][var_name] = {
                    var_name: {"line": line, "buffer": [], "ydata": Queue()}
                }
                fig.suptitle(f"Variable: {var_name}")
        if plot_result_entry_names:
            self.data_for_plot["result_entries"] = {}
            for entry_name in plot_result_entry_names:
                fig, ax = plt.subplots()
                (line,) = ax.plot([], [], label=entry_name, marker="o")
                self.data_for_plot["result_entries"][entry_name] = {
                    entry_name: {"line": line, "buffer": [], "ydata": Queue()}
                }
                fig.suptitle(f"Result Entry: {entry_name}")

    def update_plot(self):
        if not self.show_plot:
            return
        for key, plot_pack in self.data_for_plot.items():
            if key in ["ycalc", "y"]:
                line = plot_pack["line"]
                if not plot_pack["xdata"].empty():
                    xdata = plot_pack["xdata"].get()
                    ydata = plot_pack["ydata"].get()
                    line.set_xdata(xdata)
                    line.set_ydata(ydata)
                    line.axes.relim()
                    line.axes.autoscale_view()
            elif key == "variables":
                for var_name, var_pack in plot_pack.items():
                    line = var_pack[var_name]["line"]
                    buffer = var_pack[var_name]["buffer"]
                    if not var_pack[var_name]["ydata"].empty():
                        new_y = var_pack[var_name]["ydata"].get()
                        buffer.append(new_y)
                        xdata = list(range(1, len(buffer) + 1))
                        ydata = buffer
                        line.set_xdata(xdata)
                        line.set_ydata(ydata)
                        line.axes.relim()
                        line.axes.autoscale_view()
            elif key == "result_entries":
                for entry_name, entry_pack in plot_pack.items():
                    line = entry_pack[entry_name]["line"]
                    buffer = entry_pack[entry_name]["buffer"]
                    if not entry_pack[entry_name]["ydata"].empty():
                        new_y = entry_pack[entry_name]["ydata"].get()
                        buffer.append(new_y)
                        xdata = list(range(1, len(buffer) + 1))
                        ydata = buffer
                        line.set_xdata(xdata)
                        line.set_ydata(ydata)
                        line.axes.relim()
                        line.axes.autoscale_view()

    def check_for_new_data(self):
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
        self.check_for_new_data()
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

    def run_one_cycle(self, stop_event=SimpleNamespace(is_set=lambda: False)):
        self.check_for_new_data()
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
            self.adapter.init_profile(
                str(input_file),
                xmin=xmin,
                xmax=xmax,
                dx=dx,
                qmin=qmin,
                qmax=qmax,
            )
            self.adapter.init_structures([structure_path])
            self.adapter.init_contribution()
            self.adapter.init_recipe()
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
            if "ycalc" in self.data_for_plot:
                xdata = self.adapter.recipe.pdfcontribution.profile.x
                ydata = self.adapter.recipe.pdfcontribution.profile.ycalc
                self.data_for_plot["ycalc"]["xdata"].put(xdata)
                self.data_for_plot["ycalc"]["ydata"].put(ydata)
            if "y" in self.data_for_plot:
                xdata = self.adapter.recipe.pdfcontribution.profile.x
                ydata = self.adapter.recipe.pdfcontribution.profile.y
                self.data_for_plot["y"]["xdata"].put(xdata)
                self.data_for_plot["y"]["ydata"].put(ydata)
            for var_name in self.data_for_plot.get("variables", {}):
                new_value = self.adapter.recipe._parameters[var_name].value
                self.data_for_plot["variables"][var_name][var_name][
                    "ydata"
                ].put(new_value)
            for entry_name in self.data_for_plot.get("result_entries", {}):
                fit_results = FitResults(self.adapter.recipe)
                entry_value = getattr(fit_results, entry_name)
                self.data_for_plot["result_entries"][entry_name][entry_name][
                    "ydata"
                ].put(entry_value)
            print("Completed!")
        self.input_files_running = []

    def run(self, mode: Literal["batch", "stream"]):

        if mode == "batch":
            self.run_one_cycle()
        elif mode == "stream":
            stop_event = threading.Event()
            session = PromptSession()
            if self.data_for_plot is not None:
                plt.ion()
                plt.pause(1)  # Update plot every 1s

            def stream_loop():
                while not stop_event.is_set():
                    self.run_one_cycle(stop_event)
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

            input_thread = threading.Thread(target=input_loop)
            input_thread.start()
            fit_thread = threading.Thread(target=stream_loop)
            fit_thread.start()
            while not stop_event.is_set():
                self.update_plot()
                plt.pause(1)  # Update plot every 1s
            fit_thread.join()
            input_thread.join()
        else:
            raise ValueError(f"Unknown mode: {mode}")
