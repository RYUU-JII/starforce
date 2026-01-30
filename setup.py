from setuptools import setup, Extension
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "starforce_sim_core",
        [
            "app/core/extension/bindings.cpp",
            "app/core/extension/src/deck.cpp",
            "app/core/extension/src/sim_rigged.cpp",
            "app/core/extension/src/sim_sticky.cpp",
            "app/core/extension/src/sim_markov.cpp",
            "app/core/extension/src/sim_fair.cpp",
        ],
        # Example: passing in the version to the C++ code
        # define_macros = [('VERSION_INFO', __version__)],
    ),
]

setup(
    name="starforce_sim_core",
    version="0.1.0",
    author="Antigravity",
    description="Accelerated C++ core for Starforce Simulator",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.7",
)
