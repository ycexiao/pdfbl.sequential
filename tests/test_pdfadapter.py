import sys
from pathlib import Path

import numpy
from scipy.optimize import least_squares

from pdfbl.sequential.pdfadapter import PDFAdapter

sys.path.append(str(Path(__file__).parent / "diffpycmi_scripts.py"))
from diffpycmi_scripts import make_recipe  # noqa: E402


def test_pdfadapter():
    # C1: Run the same fit with pdfadapter and diffpy_cmi
    #   Expect the refined parameters to be the same within 1e-5
    # diffpy_cmi fitting
    structure_path = Path(__file__).parent / "data" / "Ni.cif"
    profile_path = Path(__file__).parent / "data" / "Ni.gr"
    diffpycmi_recipe = make_recipe(str(structure_path), str(profile_path))
    diffpycmi_recipe.fithooks[0].verbose = 0
    diffpycmi_recipe.fix("all")
    tags = ["lat", "scale", "adp", "d2", "all"]
    for tag in tags:
        diffpycmi_recipe.free(tag)
        least_squares(
            diffpycmi_recipe.residual,
            diffpycmi_recipe.values,
            x_scale="jac",
        )
    diffpy_pv_dict = {}
    for pname, parameter in diffpycmi_recipe._parameters.items():
        diffpy_pv_dict[pname] = parameter.value
    # pdfadapter fitting
    adapter = PDFAdapter()
    adapter.initialize_profile(
        str(profile_path), xmin=1.5, xmax=50, dx=0.01, qmax=25, qmin=0.1
    )
    adapter.initialize_structures([str(structure_path)])
    adapter.initialize_contribution()
    adapter.initialize_recipe()
    initial_pdfadapter_pv_dict = {
        "s0": 0.4,
        "qdamp": 0.04,
        "qbroad": 0.02,
        "a_1": 3.52,
        "Uiso_0_1": 0.005,
        "delta2_1": 2,
    }
    adapter.set_initial_variable_values(initial_pdfadapter_pv_dict)
    adapter.refine_variables(
        [
            "a_1",
            "s0",
            "Uiso_0_1",
            "delta2_1",
            "qdamp",
            "qbroad",
        ]
    )
    diffpyname_to_adaptername = {
        "fcc_Lat": "a_1",
        "s1": "s0",
        "fcc_ADP": "Uiso_0_1",
        "Ni_Delta2": "delta2_1",
        "Calib_Qdamp": "qdamp",
        "Calib_Qbroad": "qbroad",
    }
    pdfadapter_pv_dict = {}
    for pname, parameter in adapter.recipe._parameters.items():
        pdfadapter_pv_dict[pname] = parameter.value
    for diffpy_pname, adapter_pname in diffpyname_to_adaptername.items():
        assert numpy.isclose(
            diffpy_pv_dict[diffpy_pname],
            pdfadapter_pv_dict[adapter_pname],
            atol=1e-5,
        )
