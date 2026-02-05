import json
import tempfile
import warnings
from pathlib import Path
from queue import Queue
from typing import Literal

import numpy
from diffpy.srfit.fitbase import (
    FitContribution,
    FitRecipe,
    FitResults,
    Profile,
)
from diffpy.srfit.pdf import PDFGenerator, PDFParser
from diffpy.srfit.structure import constrainAsSpaceGroup
from diffpy.structure.parsers import getParser
from scipy.optimize import least_squares


class PDFAdapter:
    """Adapter to expose PDF fitting interface. Designed to provide a
    simplified PDF fitting interface for human users and AI agents.

    Attributes
    ----------
    recipe : FitRecipe
        The FitRecipe object managing the fitting process.

    Methods
    -------
    init_profile(profile_path, qmin=None, qmax=None, xmin=None, xmax=None, dx=None)
        Load and initialize the PDF profile from the given file path with
        some optional parameters.
    init_structures(structure_paths : list[str], run_parallel=True)
        Load and initialize the structures from the given file paths, and
        generate corresponding PDFGenerator objects.
    init_contribution(equation_string=None)
        Initialize the FitContribution object combining the PDF generators and
        the profile.
    init_recipe()
        Initialize the FitRecipe object for the fitting process.
    set_initial_variable_values(variable_name_to_value : dict)
        Update parameter values from the provided dictionary.
    refine_variables(variable_names: list[str])
        Refine the parameters specified in the list and in that order.
    get_variable_names()
        Get the names of all variables in the recipe.
    save_results(mode: str, filename: str=None)
        Save the fitting results.
    """  # noqa: E501

    def __init__(self):
        self.intermediate_results = {}
        self.iter_count = 0

    def moniter_intermediate_results(
        self, key: str, step: int = 10, queue: Queue = None
    ):
        """Store an intermediate result during the fitting process.

        Parameters
        ----------
        key : str
            The key to identify the intermediate result.
        step : int
            The step interval to store the intermediate result.
        queue : Queue
            The queue to store the intermediate results.
        """
        if queue is None:
            queue = Queue()
        self.intermediate_results[(key, step)] = queue

    def init_profile(
        self,
        profile_path: str,
        qmin=None,
        qmax=None,
        xmin=None,
        xmax=None,
        dx=None,
    ):
        """Load and initialize the PDF profile from the given file path
        with some optional parameters.

        The target output, FitRecipe, requires a profile object, multiple
        PDFGenerator objects, and a FitContribution object combining them. This
        method initializes the profile object.

        Parameters
        ----------
        profile_path : str
            The path to the experimental PDF profile file.
        qmin : float
            The minimum Q value for PDF calculation. The default value is
            the one parsed from the profile file.
        qmax : float
            The maximum Q value for PDF calculation. The default value is the
            one parsed from the profile file.
        xmin : float
            The minimum r value for PDF calculation. The default value is the
            one parsed from the profile file.
        xmax : float
            The maximum r value for PDF calculation. The default value is the
            one parsed from the profile file.
        dx : float
            The r step size for PDF calculation. The default value is the
            one parsed from the profile file.
        """
        profile = Profile()
        parser = PDFParser()
        parser.parseString(Path(profile_path).read_text())
        profile.loadParsedData(parser)
        if qmin:
            profile.meta["qmin"] = qmin
        if qmax:
            profile.meta["qmax"] = qmax
        profile.setCalculationRange(xmin=xmin, xmax=xmax, dx=dx)
        self.profile = profile

    def init_structures(self, structure_paths: list[str], run_parallel=True):
        """Load and initialize the structures from the given file paths,
        and generate corresponding PDFGenerator objects.

        The target output, FitRecipe, requires a profile object, multiple
        PDFGenerator objects, and a FitContribution object combining them. This
        method creates the PDFGenerator objects from the structure files.

        Must be called after init_profile.

        Parameters
        ----------
        structure_paths : list of str
            The list of paths to the structure files (CIF format).

        Notes
        -----
        Planned features:
            - Support cif file manipulation.
                - Add/Remove atoms.
                - symmetry operations?
        """
        if isinstance(structure_paths, str):
            structure_paths = [structure_paths]
        structures = []
        spacegroups = []
        pdfgenerators = []
        if run_parallel:
            try:
                import multiprocessing
                from multiprocessing import Pool

                import psutil

                syst_cores = multiprocessing.cpu_count()
                cpu_percent = psutil.cpu_percent()
                avail_cores = numpy.floor(
                    (100 - cpu_percent) / (100.0 / syst_cores)
                )
                ncpu = int(numpy.max([1, avail_cores]))
                pool = Pool(processes=ncpu)
                self.pool = pool
            except ImportError:
                warnings.warn(
                    "\nYou don't appear to have the necessary packages for "
                    "parallelization. Proceeding without parallelization."
                )
                run_parallel = False
        for i, structure_path in enumerate(structure_paths):
            stru_parser = getParser("cif")
            structure = stru_parser.parse(Path(structure_path).read_text())
            sg = getattr(stru_parser, "spacegroup", None)
            spacegroup = sg.short_name if sg is not None else "P1"
            structures.append(structure)
            spacegroups.append(spacegroup)
            pdfgenerator = PDFGenerator(f"G{i+1}")
            pdfgenerator.setStructure(structure)
            if run_parallel:
                pdfgenerator.parallel(ncpu=ncpu, mapfunc=self.pool.map)
            pdfgenerators.append(pdfgenerator)
        self.spacegroups = spacegroups
        self.pdfgenerators = pdfgenerators

    def init_contribution(self, equation_string=None):
        """Initialize the FitContribution object combining the PDF
        generators and the profile.

        The target output, FitRecipe, requires a profile object, multiple
        PDFGenerator objects, and a FitContribution object combining them. This
        method creates the FitContribution object combining the profile and PDF
        generators.

        Must be called after init_profile and init_structures.

        Parameters
        ----------
        equation_string : str
            The equation string defining the contribution. The default
            equation will be generated based on the number of phases.
            e.g.
            for one phase: "s0*G1",
            for two phases: "s0*(s1*G1+(1-s1)*G2)",
            for three phases: "s0*(s1*G1+s2*G2+(1-(s1+s2))*G3)",
            ...

        Notes
        -----
        Planned features:
            - Support registerFunction for custom equations.
        """
        contribution = FitContribution("pdfcontribution")
        contribution.setProfile(self.profile)
        for pdfgenerator in self.pdfgenerators:
            contribution.addProfileGenerator(pdfgenerator)
        number_of_phase = len(self.pdfgenerators)
        if equation_string is None:
            if number_of_phase == 1:
                equation_string = "s0*G1"
            else:
                equation_string = (
                    "s0*("
                    + "+".join(
                        [f"s{i+1}*G{i+1}" for i in range(number_of_phase - 1)]
                    )
                    + f"+(1-({'+'.join([f's{i+1}' for i in range(1, number_of_phase)])}))*G{number_of_phase}"  # noqa: E501
                    + ")"
                )
        contribution.setEquation(equation_string)
        self.contribution = contribution
        return self.contribution

    def init_recipe(
        self,
    ):
        """Initialize the FitRecipe object for the fitting process.

        The target output, FitRecipe, requires a profile object, multiple
        PDFGenerator objects, and a FitContribution object combining them. This
        method creates the FitRecipe object combining the profile, PDF
        generators, and contribution.

        Must be called after init_contribution.

        Notes
        -----
        Planned features:
            - support instructions to
                - add variables
                - constrain variables of the scatters
                - change symmetry constraints
        """
        recipe = FitRecipe()
        recipe.addContribution(self.contribution)
        qdamp = recipe.newVar("qdamp", fixed=False, value=0.04)
        qbroad = recipe.newVar("qbroad", fixed=False, value=0.02)
        for i, (pdfgenerator, spacegroup) in enumerate(
            zip(self.pdfgenerators, self.spacegroups)
        ):
            for pname in [
                "delta1",
                "delta2",
            ]:
                par = getattr(pdfgenerator, pname)
                recipe.addVar(par, name=pname + f"_{i+1}", fixed=False)
            if len(self.pdfgenerators) > 1:
                recipe.addVar(
                    getattr(self.contribution, f"s{i+1}"),
                    name=f"s{i+1}",
                    fixed=False,
                )
                recipe.restrain(f"s{i+1}", lb=0.0, ub=1.0)
            recipe.constrain(pdfgenerator.qdamp, qdamp)
            recipe.constrain(pdfgenerator.qbroad, qbroad)
            stru_parset = pdfgenerator.phase
            spacegroupparams = constrainAsSpaceGroup(stru_parset, spacegroup)
            for par in spacegroupparams.xyzpars:
                recipe.addVar(par, name=par.name + f"_{i+1}", fixed=False)
            for par in spacegroupparams.latpars:
                recipe.addVar(par, name=par.name + f"_{i+1}", fixed=False)
            for par in spacegroupparams.adppars:
                recipe.addVar(par, name=par.name + f"_{i+1}", fixed=False)
        recipe.addVar(self.contribution.s0, name="s0", fixed=False)
        recipe.fix("all")
        recipe.fithooks[0].verbose = 0
        self.recipe = recipe

    def set_initial_variable_values(self, variable_name_to_value: dict):
        """Update parameter values from the provided dictionary.

        Parameters
        ----------
        variable_name_to_value : dict
            A dictionary mapping variable names to their new values.
        """
        for vname, vvalue in variable_name_to_value.items():
            self.recipe._parameters[vname].setValue(vvalue)

    def residual(self, p=[]):
        """Wrapper for the recipe residual function to store
        intermediate results if needed.

        Parameters
        ----------
        p : list
            List of parameter values.

        Returns
        -------
        numpy.ndarray
            The residual array.
        """
        residual = self.recipe.residual(p)
        fitresults = FitResults(self.recipe)
        for (key, step), values in self.intermediate_results.items():
            if (self.iter_count % step) == 0:
                value = getattr(fitresults, key)
                values.put(value)
        self.iter_count += 1
        return residual

    def refine_variables(self, variable_names: list[str]):
        """Refine the parameters specified in the list and in that
        order. Must be called after init_recipe.

        Parameters
        ----------
        variable_names : list of str
            The names of the variables to refine.
        """
        for vname in variable_names:
            if vname not in self.recipe._parameters:
                raise ValueError(
                    f"Variable {vname} not found in the recipe. "
                    "Please choose from the existing variables: "
                    f"{list(self.recipe._parameters.keys())}"
                )
        for vname in variable_names:
            self.recipe.free(vname)
            least_squares(
                self.residual,
                self.recipe.values,
                x_scale="jac",
            )

    def get_variable_names(self) -> list[str]:
        """Get the names of all variables in the recipe.

        Returns
        -------
        list of str
            A list of variable names.
        """
        return list(self.recipe._parameters.keys())

    def save_results(
        self, mode: Literal["str", "dict"] = "str", filename=None
    ):
        """Save the fitting results. Must be called after
        refine_parameters.

        Parameters
        ----------
        mode : str
            The format to save the results. Options are:
                "str" - Save results as a formatted text string.
                "dict" - Save results as a JSON-compatible dictionary.
        filename : str
            The path to the output file. If None, results will not be saved to
            a file.

        Returns
        -------
        str or dict
            The fitting results in the specified format.
        """
        fit_results = FitResults(self.recipe)
        if mode == "str":
            if filename is None:
                tmp_directory = tempfile.TemporaryDirectory()
                temp_file = Path(tmp_directory.name) / "data.txt"
                filename = str(temp_file)
            fit_results.saveResults(filename)
            with open(filename, "r") as f:
                results_str = f.read()
            if filename is None:
                tmp_directory.cleanup()
            return results_str

        elif mode == "dict":
            results_dict = {}
            results_dict["residual"] = fit_results.residual
            results_dict["contributions"] = (
                fit_results.residual - fit_results.penalty
            )
            results_dict["restraints"] = fit_results.penalty
            results_dict["chi2"] = fit_results.chi2
            results_dict["reduced_chi2"] = fit_results.rchi2
            results_dict["rw"] = fit_results.rw
            # variables
            results_dict["variables"] = {}
            for name, val, unc in zip(
                fit_results.varnames, fit_results.varvals, fit_results.varunc
            ):
                results_dict["variables"][name] = {
                    "value": val,
                    "uncertainty": unc,
                }
            # fixed variables
            results_dict["fixed_variables"] = {}
            if fit_results.fixednames is not None:
                for name, val in zip(
                    fit_results.fixednames, fit_results.fixedvals
                ):
                    results_dict["fixed_variables"][name] = {"value": val}
            # constraints
            results_dict["constraints"] = {}
            if fit_results.connames and fit_results.showcon:
                for con in fit_results.conresults.values():
                    for i, loc in enumerate(con.conlocs):
                        names = [obj.name for obj in loc]
                        name = ".".join(names)
                        val = con.convals[i]
                        unc = con.conuncs[i]
                        results_dict["constraints"][name] = {
                            "value": val,
                            "uncertainty": unc,
                        }
            # covariance matrix
            results_dict["covariance_matrix"] = fit_results.cov.tolist()
            # certainty
            certain = True
            for con in fit_results.conresults.values():
                if (con.dy == 1).all():
                    certain = False
            results_dict["certain"] = certain
            if filename is not None:
                with open(filename, "w") as f:
                    json.dump(results_dict, f, indent=2)
            return results_dict

        else:
            raise ValueError(
                f"Unsupported mode: {mode}. Please use 'json' or 'txt'."
            )
